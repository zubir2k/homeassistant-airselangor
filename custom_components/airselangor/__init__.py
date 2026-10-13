"""The Air Selangor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import AirSelangorClient
from .const import CONF_ACCOUNTS, CONF_LOGIN_ID, DOMAIN, PLATFORMS
from .coordinator import AirSelangorCoordinator
from .services import async_setup_services

type AirSelangorConfigEntry = ConfigEntry[AirSelangorCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AirSelangorConfigEntry) -> bool:
    """Set up Air Selangor from a config entry."""
    client = AirSelangorClient(
        async_create_clientsession(hass),
        entry.data[CONF_LOGIN_ID],
        entry.data[CONF_PASSWORD],
    )
    coordinator = AirSelangorCoordinator(
        hass, entry, client, entry.data.get(CONF_ACCOUNTS, [])
    )
    # Fetches immediately when the account is added (and on every HA start),
    # then once a day after that.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AirSelangorConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.logout()
    return unloaded


async def _async_update_listener(
    hass: HomeAssistant, entry: AirSelangorConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
