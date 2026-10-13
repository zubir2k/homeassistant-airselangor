"""DataUpdateCoordinator for Air Selangor."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AccountData,
    AirSelangorAuthError,
    AirSelangorClient,
    AirSelangorError,
)
from .const import CONF_ACCOUNT_NUMBER, DEFAULT_SCAN_INTERVAL, DOMAIN
from .statistics import async_import_bill_statistics

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class AirSelangorCoordinator(DataUpdateCoordinator[dict[str, AccountData]]):
    """Fetch every selected water account in one cycle."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AirSelangorClient,
        accounts: list[dict[str, Any]],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.selected = {str(a[CONF_ACCOUNT_NUMBER]) for a in accounts}

    async def _async_update_data(self) -> dict[str, AccountData]:
        try:
            accounts = await self.client.get_accounts()
            wanted = [a for a in accounts if a.account_number in self.selected]
            result: dict[str, AccountData] = {}
            for account in wanted:
                result[account.account_number] = await self.client.get_account_data(
                    account
                )
        except AirSelangorAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AirSelangorError as err:
            raise UpdateFailed(str(err)) from err

        missing = self.selected - result.keys()
        if missing:
            _LOGGER.warning(
                "Air Selangor accounts no longer linked to this login: %s",
                ", ".join(sorted(missing)),
            )

        for data in result.values():
            try:
                await async_import_bill_statistics(self.hass, data)
            except Exception:  # noqa: BLE001 - statistics must never break polling
                _LOGGER.exception(
                    "Failed to import statistics for %s", data.account.account_number
                )
        return result
