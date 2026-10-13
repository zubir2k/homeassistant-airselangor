"""Binary sensors for Air Selangor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AirSelangorConfigEntry
from .entity import AirSelangorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSelangorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        PaymentDueSensor(coordinator, number) for number in coordinator.data
    )


class PaymentDueSensor(AirSelangorEntity, BinarySensorEntity):
    """On when there is an outstanding amount to pay."""

    _attr_translation_key = "payment_due"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, account_number: str) -> None:
        super().__init__(coordinator, account_number, "payment_due")

    @property
    def is_on(self) -> bool | None:
        data = self.account_data
        if data is None or data.outstanding_rm is None:
            return None
        return data.outstanding_rm > 0

    @property
    def extra_state_attributes(self):
        data = self.account_data
        if data is None:
            return None
        overdue = bool(
            data.due_date
            and data.outstanding_rm
            and data.outstanding_rm > 0
            and dt_util.now().date() > data.due_date
        )
        return {
            "amount_rm": data.outstanding_rm,
            "due_date": data.due_date.isoformat() if data.due_date else None,
            "overdue": overdue,
            "payment_status": data.overdue_status,
        }
