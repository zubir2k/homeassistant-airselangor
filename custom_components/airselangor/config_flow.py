"""Config flow for Air Selangor."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    AirSelangorAuthError,
    AirSelangorClient,
    AirSelangorConnectionError,
    AirSelangorError,
)
from .const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_NUMBER,
    CONF_ACCOUNTS,
    CONF_DISPLAY_NAME,
    CONF_LOGIN_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOGIN_ID): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


async def validate_login(
    hass: HomeAssistant, login_id: str, password: str
) -> tuple[str, list[dict[str, str]]]:
    """Log in and return (user id, linked accounts)."""
    client = AirSelangorClient(async_create_clientsession(hass), login_id, password)
    profile = await client.get_profile()
    accounts = await client.get_accounts()
    await client.logout()
    return (
        str(profile.get("userid") or login_id),
        [
            {
                CONF_ACCOUNT_ID: a.account_id,
                CONF_ACCOUNT_NUMBER: a.account_number,
                CONF_DISPLAY_NAME: a.display_name,
            }
            for a in accounts
        ],
    )


def _error_key(err: Exception) -> str:
    if isinstance(err, AirSelangorAuthError):
        return "invalid_auth"
    if isinstance(err, AirSelangorConnectionError):
        return "cannot_connect"
    return "unknown"


def _accounts_schema(
    accounts: list[dict[str, str]], default: list[str] | None = None
) -> vol.Schema:
    options = [
        selector.SelectOptionDict(
            value=a[CONF_ACCOUNT_NUMBER],
            label=f"{a[CONF_DISPLAY_NAME]} ({a[CONF_ACCOUNT_NUMBER]})",
        )
        for a in accounts
    ]
    return vol.Schema(
        {
            vol.Required(
                CONF_ACCOUNTS,
                default=default
                if default is not None
                else [a[CONF_ACCOUNT_NUMBER] for a in accounts],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=options, multiple=True)
            )
        }
    )


class AirSelangorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Air Selangor."""

    VERSION = 1

    def __init__(self) -> None:
        self._login_id: str = ""
        self._password: str = ""
        self._accounts: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            login_id = user_input[CONF_LOGIN_ID].strip()
            try:
                user_id, accounts = await validate_login(
                    self.hass, login_id, user_input[CONF_PASSWORD]
                )
            except AirSelangorError as err:
                _LOGGER.debug("Login failed: %s", err)
                errors["base"] = _error_key(err)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Air Selangor login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                if not accounts:
                    errors["base"] = "no_accounts"
                else:
                    self._login_id = login_id
                    self._password = user_input[CONF_PASSWORD]
                    self._accounts = accounts
                    if len(accounts) == 1:
                        return self._create(accounts)
                    return await self.async_step_accounts()

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = set(user_input.get(CONF_ACCOUNTS) or [])
            if not chosen:
                errors["base"] = "select_at_least_one"
            else:
                return self._create(
                    [a for a in self._accounts if a[CONF_ACCOUNT_NUMBER] in chosen]
                )
        return self.async_show_form(
            step_id="accounts",
            data_schema=_accounts_schema(self._accounts),
            errors=errors,
        )

    def _create(self, accounts: list[dict[str, str]]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=f"Air Selangor ({self._login_id})",
            data={
                CONF_LOGIN_ID: self._login_id,
                CONF_PASSWORD: self._password,
                CONF_ACCOUNTS: accounts,
            },
        )

    # ----------------------------------------------------------------- reauth
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        self._login_id = entry_data[CONF_LOGIN_ID]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                user_id, _ = await validate_login(
                    self.hass, self._login_id, user_input[CONF_PASSWORD]
                )
            except AirSelangorError as err:
                errors["base"] = _error_key(err)
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            description_placeholders={"login_id": self._login_id},
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AirSelangorOptionsFlow()


class AirSelangorOptionsFlow(OptionsFlow):
    """Change which linked accounts are tracked."""

    def __init__(self) -> None:
        self._accounts: list[dict[str, str]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        data = self.config_entry.data
        if not self._accounts:
            try:
                _, self._accounts = await validate_login(
                    self.hass, data[CONF_LOGIN_ID], data[CONF_PASSWORD]
                )
            except AirSelangorError as err:
                return self.async_abort(reason=_error_key(err))

        if user_input is not None:
            chosen = set(user_input.get(CONF_ACCOUNTS) or [])
            if not chosen:
                errors["base"] = "select_at_least_one"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **data,
                        CONF_ACCOUNTS: [
                            a
                            for a in self._accounts
                            if a[CONF_ACCOUNT_NUMBER] in chosen
                        ],
                    },
                )
                return self.async_create_entry(data={})

        current = [a[CONF_ACCOUNT_NUMBER] for a in data.get(CONF_ACCOUNTS, [])]
        return self.async_show_form(
            step_id="init",
            data_schema=_accounts_schema(self._accounts, current),
            errors=errors,
        )
