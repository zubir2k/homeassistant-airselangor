"""Constants for the Air Selangor integration."""

from datetime import timedelta

DOMAIN = "airselangor"
PLATFORMS = ["sensor", "binary_sensor", "button"]

CONF_LOGIN_ID = "login_id"
CONF_ACCOUNTS = "accounts"
CONF_ACCOUNT_ID = "account_id"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_DISPLAY_NAME = "display_name"

# Bills are monthly and balances change on payment, so poll once a day.
# Use the airselangor.refresh action or the Refresh button for an ad-hoc update.
DEFAULT_SCAN_INTERVAL = timedelta(hours=24)

SERVICE_REFRESH = "refresh"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

MANUFACTURER = "Pengurusan Air Selangor Sdn Bhd"
MODEL = "Water account"
CURRENCY_RM = "MYR"

# Air Selangor bills are dated in Malaysian local time.
TIME_ZONE = "Asia/Kuala_Lumpur"
