"""Constants for the Air Selangor integration."""

from datetime import timedelta
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "airselangor"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

CONF_LOGIN_ID = "login_id"
CONF_ACCOUNTS = "accounts"
CONF_ACCOUNT_ID = "account_id"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_DISPLAY_NAME = "display_name"

# Bills are monthly and balances change on payment, so poll once a day.
# Use the airselangor.refresh action or the Refresh button for an ad-hoc update.
DEFAULT_SCAN_INTERVAL = timedelta(hours=24)


class AirSelangorService(StrEnum):
    """Actions registered by the Air Selangor integration."""

    REFRESH = "refresh"


SERVICE_REFRESH = AirSelangorService.REFRESH

MANUFACTURER = "Pengurusan Air Selangor Sdn Bhd"
MODEL = "Water account"
CURRENCY_RM = "MYR"

# Air Selangor bills are dated in Malaysian local time.
TIME_ZONE = "Asia/Kuala_Lumpur"

__all__ = [
    "ATTR_CONFIG_ENTRY_ID",
    "AirSelangorService",
    "CONF_ACCOUNTS",
    "CONF_ACCOUNT_ID",
    "CONF_ACCOUNT_NUMBER",
    "CONF_DISPLAY_NAME",
    "CONF_LOGIN_ID",
    "CURRENCY_RM",
    "DEFAULT_SCAN_INTERVAL",
    "DOMAIN",
    "MANUFACTURER",
    "MODEL",
    "PLATFORMS",
    "SERVICE_REFRESH",
    "TIME_ZONE",
]
