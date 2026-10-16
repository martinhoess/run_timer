"""Constants for run_timer."""

DOMAIN = "run_timer"

CONF_DEFAULT_MINUTES = "default_minutes"
CONF_ON_ACTION = "on_action"

DEFAULT_MINUTES_MIN = 0  # 0: no automatic switch-off
DEFAULT_MINUTES_MAX = 1440

STORAGE_VERSION = 1

ATTR_MINUTES = "minutes"
ATTR_AT = "at"
ATTR_DURATION = "duration"
ATTR_WHAT = "what"

SERVICE_EXTEND = "extend"
SERVICE_OFF_IN = "off_in"
SERVICE_OFF_AT = "off_at"
SERVICE_ON_IN = "on_in"
SERVICE_ON_AT = "on_at"
SERVICE_CANCEL = "cancel"
