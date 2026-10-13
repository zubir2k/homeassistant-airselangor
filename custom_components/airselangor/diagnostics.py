"""Diagnostics for Air Selangor (credentials and personal details redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import AirSelangorConfigEntry
from .const import CONF_LOGIN_ID

TO_REDACT = {
    CONF_PASSWORD,
    CONF_LOGIN_ID,
    "address",
    "methodvalue",
    "billroute",
    "reference",
    "billid",
    "billnumber",
    "bill_number",
    "account_id",
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
