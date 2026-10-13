"""Setup + entity tests."""

from homeassistant.const import CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airselangor.const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNT_NUMBER,
    CONF_ACCOUNTS,
    CONF_DISPLAY_NAME,
    CONF_LOGIN_ID,
    DOMAIN,
)


async def _setup(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-1",
        data={
            CONF_LOGIN_ID: "820101015555",
            CONF_PASSWORD: "pw",
            CONF_ACCOUNTS: [
                {
                    CONF_ACCOUNT_ID: "acc-guid-1",
                    CONF_ACCOUNT_NUMBER: "3800000001",
                    CONF_DISPLAY_NAME: "Home",
                }
            ],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensors(hass, mock_client):
    await _setup(hass)
    prefix = "sensor.air_selangor_home_"
    assert hass.states.get(prefix + "latest_bill_usage").state == "51.0"
    assert hass.states.get(prefix + "latest_bill_amount").state == "93.45"
    assert hass.states.get(prefix + "outstanding_balance").state == "0.0"
    assert hass.states.get(prefix + "account_credit").state == "93.45"
    assert hass.states.get(prefix + "due_date").state == "2026-10-21"
    assert hass.states.get(prefix + "last_payment_amount").state == "93.45"
    assert hass.states.get(prefix + "usage_per_person").state == "235.0"
    usage = hass.states.get(prefix + "latest_bill_usage")
    assert len(usage.attributes["bill_history"]) == 3
    assert hass.states.get("binary_sensor.air_selangor_home_payment_due").state == "off"


async def test_unload(hass, mock_client):
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    _, init_client = mock_client
    init_client.logout.assert_awaited()


async def test_refresh_action_and_button(hass, mock_client):
    entry = await _setup(hass)
    _, client = mock_client
    calls = client.get_account_data.await_count
    assert calls == 1  # fetched immediately on setup

    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert client.get_account_data.await_count == calls + 1

    await hass.services.async_call(
        DOMAIN, "refresh", {"config_entry_id": entry.entry_id}, blocking=True
    )
    assert client.get_account_data.await_count == calls + 2

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.air_selangor_home_refresh"},
        blocking=True,
    )
    assert client.get_account_data.await_count == calls + 3


async def test_daily_interval(hass, mock_client):
    entry = await _setup(hass)
    assert entry.runtime_data.update_interval.total_seconds() == 86400
