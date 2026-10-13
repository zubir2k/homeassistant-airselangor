"""Config flow tests."""

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airselangor.api import AirSelangorAuthError
from custom_components.airselangor.const import (
    CONF_ACCOUNTS,
    CONF_LOGIN_ID,
    DOMAIN,
)


async def test_user_flow_single_account(hass, mock_client):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOGIN_ID: " 820101015555 ", CONF_PASSWORD: "pw"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOGIN_ID] == "820101015555"
    assert result["data"][CONF_ACCOUNTS][0]["account_number"] == "3800000001"
    assert result["result"].unique_id == "user-1"


async def test_user_flow_invalid_auth(hass, mock_client):
    flow_client, _ = mock_client
    flow_client.get_profile.side_effect = AirSelangorAuthError("bad")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOGIN_ID: "x", CONF_PASSWORD: "y"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth(hass, mock_client):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-1",
        data={CONF_LOGIN_ID: "820101015555", CONF_PASSWORD: "old", CONF_ACCOUNTS: []},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
