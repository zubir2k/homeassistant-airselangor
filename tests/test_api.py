"""Pure-python tests for the API helpers."""

from datetime import UTC, date, timedelta

from custom_components.airselangor.api import (
    AirSelangorClient,
    _parse_portal_datetime,
    _to_float,
)
from custom_components.airselangor.statistics import spread_bills

from .conftest import make_account_data


def test_parse_both_timestamp_formats():
    iso = _parse_portal_datetime("2025-11-24T22:52:55.091594Z")
    display = _parse_portal_datetime("Tue 2025-11-25 6:52 AM (UTC+08:00)")
    assert iso.tzinfo is not None
    assert display.utcoffset() == timedelta(hours=8)
    assert display.astimezone(UTC).hour == 22
    assert _parse_portal_datetime("garbage") is None


def test_to_float():
    assert _to_float("1,234.50") == 1234.5
    assert _to_float("") is None
    assert _to_float(None) is None


def test_public_token_header():
    client = AirSelangorClient(None, "id", "pw")
    headers = client._headers(authenticated=False)
    assert headers["Authorization"].startswith("Bearer ")
    assert len(headers["Authorization"]) == len("Bearer ") + 64


def test_derived_values():
    data = make_account_data()
    assert data.latest_bill.usage_m3 == 51.0
    assert data.average_usage_m3 == round((39 + 35 + 51) / 3, 2)
    # 51 m3 over 31 days for 7 people
    assert data.usage_per_person_lpd == round(51000 / 31 / 7, 1)
    assert data.last_payment.reference == "R2"


def test_spread_bills_matches_totals():
    data = make_account_data()
    days = spread_bills(data.bills)
    assert round(sum(u for _, u, _ in days), 6) == 39 + 35 + 51
    assert round(sum(c for _, _, c in days), 6) == round(51.35 + 37.30 + 93.45, 6)
    assert days[-1][0] == date(2026, 9, 21)
    assert len({d for d, _, _ in days}) == len(days)
