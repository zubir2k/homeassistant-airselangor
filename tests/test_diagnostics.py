"""Tests for Air Selangor diagnostics."""

from unittest.mock import MagicMock

from custom_components.airselangor.const import CONF_DISPLAY_NAME
from custom_components.airselangor.diagnostics import async_get_config_entry_diagnostics
from homeassistant.core import HomeAssistant


async def test_diagnostics_redaction(hass: HomeAssistant) -> None:
    """Test that sensitive details including display_name are redacted."""
    entry = MagicMock()
    entry.data = {
        "login_id": "secret_user",
        "password": "secret_password",
        "accounts": [
            {
                "account_number": "1234567890",
                CONF_DISPLAY_NAME: "My House",
            }
        ],
    }

    mock_account = MagicMock()
    mock_account.display_name = "My House"
    mock_account.accountnumber = "1234567890"

    coordinator = MagicMock()
    coordinator.data = {"1234567890": mock_account}
    entry.runtime_data = coordinator

    diag = await async_get_config_entry_diagnostics(hass, entry)

    # In entry data, display_name should be redacted
    entry_accounts = diag["entry"]["accounts"]
    assert entry_accounts[0][CONF_DISPLAY_NAME] == "**REDACTED**"
    assert diag["entry"]["login_id"] == "**REDACTED**"
    assert diag["entry"]["password"] == "**REDACTED**"

    # In account data, display_name should be redacted
    account_diag = diag["accounts"]["7890"]
    assert account_diag["display_name"] == "**REDACTED**"
