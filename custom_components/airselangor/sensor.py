"""Sensors for Air Selangor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AirSelangorConfigEntry
from .api import AccountData
from .const import CURRENCY_RM
from .entity import AirSelangorEntity


@dataclass(frozen=True, kw_only=True)
class AirSelangorSensorDescription(SensorEntityDescription):
    value_fn: Callable[[AccountData], StateType | date]
    attrs_fn: Callable[[AccountData], dict[str, Any]] | None = None


def _bill_history(d: AccountData) -> dict[str, Any]:
    return {
        "bill_history": [
            {
                "bill_date": b.bill_date.isoformat(),
                "usage_m3": b.usage_m3,
                "amount_rm": b.amount_rm,
            }
            for b in reversed(d.bills)
        ]
    }


def _latest_bill_attrs(d: AccountData) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "bill_number": d.bill_number,
        "bill_date": d.bill_date.isoformat() if d.bill_date else None,
    }
    if d.previous_bill:
        attrs["previous_bill_usage_m3"] = d.previous_bill.usage_m3
        attrs["previous_bill_amount_rm"] = d.previous_bill.amount_rm
    return attrs


def _payment_attrs(d: AccountData) -> dict[str, Any]:
    p = d.last_payment
    if p is None:
        return {}
    return {
        "reference": p.reference,
        "method": p.method,
        "bank": p.bank,
        "status": p.status,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
    }


SENSORS: tuple[AirSelangorSensorDescription, ...] = (
    AirSelangorSensorDescription(
        key="latest_bill_usage",
        translation_key="latest_bill_usage",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        # No state_class: per-bill values are not a running total. Long-term
        # history comes from the imported airselangor:<acc>_water statistic.
        value_fn=lambda d: d.latest_bill.usage_m3 if d.latest_bill else None,
        attrs_fn=lambda d: {**_latest_bill_attrs(d), **_bill_history(d)},
    ),
    AirSelangorSensorDescription(
        key="latest_bill_amount",
        translation_key="latest_bill_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_RM,
        suggested_display_precision=2,
        value_fn=lambda d: (
            d.latest_bill.amount_rm if d.latest_bill else d.latest_bill_amount_rm
        ),
        attrs_fn=_latest_bill_attrs,
    ),
    AirSelangorSensorDescription(
        key="average_monthly_usage",
        translation_key="average_monthly_usage",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=1,
        value_fn=lambda d: d.average_usage_m3,
        attrs_fn=lambda d: {"bills_counted": len(d.bills)},
    ),
    AirSelangorSensorDescription(
        key="usage_per_person",
        translation_key="usage_per_person",
        native_unit_of_measurement="L/person/day",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:account-water",
        value_fn=lambda d: d.usage_per_person_lpd,
        attrs_fn=lambda d: {
            "household_size": d.household_size,
            "target_l_per_person_day": d.lcd_target_lpcd,
            "above_target": (
                d.usage_per_person_lpd > d.lcd_target_lpcd
                if d.usage_per_person_lpd is not None and d.lcd_target_lpcd
                else None
            ),
        },
    ),
    AirSelangorSensorDescription(
        key="outstanding_balance",
        translation_key="outstanding_balance",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_RM,
        suggested_display_precision=2,
        value_fn=lambda d: d.outstanding_rm,
        attrs_fn=lambda d: {
            "current_balance_rm": d.current_balance_rm,
            "payment_status": d.overdue_status,
        },
    ),
    AirSelangorSensorDescription(
        key="account_credit",
        translation_key="account_credit",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_RM,
        suggested_display_precision=2,
        # API reports credit as a negative overdue amount.
        value_fn=lambda d: (
            round(-d.overdue_rm, 2)
            if d.overdue_rm is not None and d.overdue_rm < 0
            else 0
        ),
    ),
    AirSelangorSensorDescription(
        key="due_date",
        translation_key="due_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: d.due_date,
    ),
    AirSelangorSensorDescription(
        key="bill_date",
        translation_key="bill_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: d.bill_date,
    ),
    AirSelangorSensorDescription(
        key="last_payment_amount",
        translation_key="last_payment_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_RM,
        suggested_display_precision=2,
        value_fn=lambda d: d.last_payment.amount_rm if d.last_payment else None,
        attrs_fn=_payment_attrs,
    ),
    AirSelangorSensorDescription(
        key="last_payment_date",
        translation_key="last_payment_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: (
            d.last_payment_date
            or (d.last_payment.paid_at.date() if d.last_payment else None)
        ),
    ),
    AirSelangorSensorDescription(
        key="account_status",
        translation_key="account_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:water-check",
        value_fn=lambda d: d.account.status,
        attrs_fn=lambda d: {
            "account_number": d.account.account_number,
            "address": d.account.address,
            "smart_meter": d.account.is_smart_meter,
            "e_bill": d.account.is_ebill,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirSelangorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        AirSelangorSensor(coordinator, number, desc)
        for number in coordinator.data
        for desc in SENSORS
    )


class AirSelangorSensor(AirSelangorEntity, SensorEntity):
    entity_description: AirSelangorSensorDescription

    def __init__(self, coordinator, account_number, description) -> None:
        super().__init__(coordinator, account_number, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | date:
        data = self.account_data
        return self.entity_description.value_fn(data) if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.account_data
        if data is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(data)
