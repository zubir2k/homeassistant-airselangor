"""Refresh button for Air Selangor."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirSelangorConfigEntry
from .entity import AirSelangorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSelangorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        RefreshButton(coordinator, number) for number in coordinator.data
    )


class RefreshButton(AirSelangorEntity, ButtonEntity):
    """Fetch the latest data from Air Selangor now."""

    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, account_number: str) -> None:
        super().__init__(coordinator, account_number, "refresh")

    @property
    def available(self) -> bool:
        # Stay pressable even when the last update failed.
        return self.account_data is not None

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
