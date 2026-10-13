"""Actions for Air Selangor."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_REFRESH

REFRESH_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string])}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register airselangor.refresh."""

    async def _refresh(call: ServiceCall) -> None:
        wanted = call.data.get(ATTR_CONFIG_ENTRY_ID)
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
            and (not wanted or e.entry_id in wanted)
        ]
        if wanted and len(entries) != len(set(wanted)):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="entry_not_loaded"
            )
        for entry in entries:
            await entry.runtime_data.async_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _refresh, schema=REFRESH_SCHEMA
    )
