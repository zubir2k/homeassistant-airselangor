"""Base entity for Air Selangor."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AccountData
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import AirSelangorCoordinator


class AirSelangorEntity(CoordinatorEntity[AirSelangorCoordinator]):
    """An entity tied to one water account (one device per account)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AirSelangorCoordinator, account_number: str, key: str
    ) -> None:
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_unique_id = f"{account_number}_{key}"
        account = coordinator.data[account_number].account
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"Air Selangor {account.display_name}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=account_number,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.airselangor.com/my-water-account",
        )

    @property
    def account_data(self) -> AccountData | None:
        return (self.coordinator.data or {}).get(self._account_number)

    @property
    def available(self) -> bool:
        return super().available and self.account_data is not None
