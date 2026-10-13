"""Fixtures for Air Selangor tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.airselangor.api import (
    AccountData,
    Bill,
    Payment,
    WaterAccount,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]

ACCOUNT = WaterAccount(
    account_id="acc-guid-1",
    account_number="3800000001",
    display_name="Home",
    address="NO 1 JALAN CONTOH, KAJANG",
    status="Active",
    is_smart_meter=False,
    is_ebill=True,
)


def make_account_data() -> AccountData:
    bills = [
        Bill(date(2026, 7, 21), 39.0, 51.35),
        Bill(date(2026, 8, 21), 35.0, 37.30),
        Bill(date(2026, 9, 21), 51.0, 93.45),
    ]
    return AccountData(
        account=WaterAccount(**{s: getattr(ACCOUNT, s) for s in ACCOUNT.__slots__}),
        current_balance_rm=0.0,
        outstanding_rm=0.0,
        overdue_rm=-93.45,
        latest_bill_amount_rm=93.45,
        overdue_status="paid",
        bill_number="111",
        bill_date=date(2026, 9, 21),
        due_date=date(2026, 10, 21),
        last_payment_date=date(2026, 10, 10),
        household_size=7,
        lcd_target_lpcd=180.0,
        bills=bills,
        payments=[
            Payment(
                "R1",
                37.30,
                "Success",
                None,
                "Maybank2U",
                datetime(2026, 8, 21, 23, 39, tzinfo=UTC),
            ),
            Payment(
                "R2",
                93.45,
                "Success",
                None,
                "MAYBANK",
                datetime(2026, 10, 10, 2, 5, tzinfo=UTC),
            ),
        ],
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_client():
    """Patch the API client everywhere it is constructed."""
    with (
        patch("custom_components.airselangor.async_create_clientsession"),
        patch("custom_components.airselangor.config_flow.async_create_clientsession"),
        patch(
            "custom_components.airselangor.AirSelangorClient", autospec=True
        ) as init_cls,
        patch(
            "custom_components.airselangor.config_flow.AirSelangorClient",
            autospec=True,
        ) as flow_cls,
    ):
        for cls in (init_cls, flow_cls):
            client = cls.return_value
            client.get_profile = AsyncMock(return_value={"userid": "user-1"})
            client.get_accounts = AsyncMock(
                side_effect=lambda: [
                    WaterAccount(**{s: getattr(ACCOUNT, s) for s in ACCOUNT.__slots__})
                ]
            )
            client.get_account_data = AsyncMock(
                side_effect=lambda account: make_account_data()
            )
            client.logout = AsyncMock()
        yield flow_cls.return_value, init_cls.return_value
