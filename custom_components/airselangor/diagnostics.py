"""Diagnostics for Air Selangor (credentials and personal details redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import AirSelangorConfigEntry
from .const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_NUMBER,
    CONF_DISPLAY_NAME,
    CONF_LOGIN_ID,
)

TO_REDACT = {
    CONF_PASSWORD,
    CONF_LOGIN_ID,
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_NUMBER,
    CONF_DISPLAY_NAME,
    "accountnumber",
    "address",
    "bill_number",
    "billid",
    "billnumber",
    "billroute",
    "email",
    "fullname",
    "icno",
    "mailingaddress",
    "methodvalue",
    "mobileno",
    "name",
    "PremiseAddress",
    "reference",
    "referenceno",
    "transactionid",
    "wateraccountid",
    "wateraccountmanageid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirSelangorConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "accounts": {
            number[-4:]: async_redact_data(asdict(data), TO_REDACT)
            for number, data in (coordinator.data or {}).items()
        },
    }
