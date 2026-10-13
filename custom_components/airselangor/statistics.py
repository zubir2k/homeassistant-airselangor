"""Long-term statistics for Air Selangor bills.

Air Selangor meters are read monthly, so the API only knows how much water was
used per bill (up to 12 bills back). We spread each bill's usage and cost
evenly over the days of its billing period (previous bill date up to this bill
date) and import them as external statistics:

* ``airselangor:<account>_water``  (m³, usable in the Energy dashboard Water card)
* ``airselangor:<account>_cost``   (MYR)

Day-level values are therefore an even split of the bill, not real daily reads,
but monthly totals match the bills exactly. Imports are incremental: only days
after the last imported one are added, so every poll is cheap and sums never
reset when old bills drop out of the API's 12-month window.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .api import AccountData, Bill
from .const import CURRENCY_RM, DOMAIN, TIME_ZONE

_LOGGER = logging.getLogger(__name__)

DEFAULT_PERIOD_DAYS = 30


def spread_bills(bills: list[Bill]) -> list[tuple[date, float, float]]:
    """Return ``(day, usage_m3, cost_rm)`` per day, oldest first.

    Each bill covers the days after the previous bill date up to and including
    its own bill date.
    """
    days: list[tuple[date, float, float]] = []
    previous: date | None = None
    for bill in sorted(bills, key=lambda b: b.bill_date):
        start = previous or (bill.bill_date - timedelta(days=DEFAULT_PERIOD_DAYS))
        length = (bill.bill_date - start).days
        previous = bill.bill_date
        if length <= 0:
            continue
        for offset in range(1, length + 1):
            days.append(
                (
                    start + timedelta(days=offset),
                    bill.usage_m3 / length,
                    bill.amount_rm / length,
                )
            )
    return days


async def async_import_bill_statistics(hass: HomeAssistant, data: AccountData) -> None:
    """Import usage and cost statistics for one account."""
    if "recorder" not in hass.config.components:
        return
    days = spread_bills(data.bills)
    if not days:
        return
    number = data.account.account_number
    label = data.account.display_name or number
    await _import(
        hass,
        f"{DOMAIN}:{number}_water",
        f"Air Selangor {label} water",
        UnitOfVolume.CUBIC_METERS,
        [(d, usage) for d, usage, _ in days],
    )
    await _import(
        hass,
        f"{DOMAIN}:{number}_cost",
        f"Air Selangor {label} cost",
        CURRENCY_RM,
        [(d, cost) for d, _, cost in days],
    )


async def _import(
    hass: HomeAssistant,
    statistic_id: str,
    name: str,
    unit: str,
    series: list[tuple[date, float]],
) -> None:
    tz = dt_util.get_time_zone(TIME_ZONE)
    last = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    total = 0.0
    last_ts: float | None = None
    if rows := (last or {}).get(statistic_id):
        total = rows[0].get("sum") or 0.0
        last_ts = _as_ts(rows[0].get("start"))

    stats: list[StatisticData] = []
    for day, value in series:
        start = datetime(day.year, day.month, day.day, tzinfo=tz)
        if last_ts is not None and start.timestamp() <= last_ts:
            continue
        total += value
        stats.append(
            StatisticData(start=start, state=round(value, 4), sum=round(total, 4))
        )
    if not stats:
        return

    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name=name,
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_of_measurement=unit,
    )
    async_add_external_statistics(hass, metadata, stats)
    _LOGGER.debug("Imported %d rows into %s", len(stats), statistic_id)


def _as_ts(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return value.timestamp()
