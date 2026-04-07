"""Constants for the Petkit BLE integration."""

from __future__ import annotations

DOMAIN = "petkit_ble"

# BLE UUIDs
BLE_WRITE_UUID = "0000aaa2-0000-1000-8000-00805f9b34fb"
BLE_NOTIFY_UUID = "0000aaa1-0000-1000-8000-00805f9b34fb"

# Frame markers
FRAME_HEADER = bytes([0xFA, 0xFC, 0xFD])
FRAME_END = 0xFB

# Frame type bytes
FRAME_TYPE_SEND = 1
FRAME_TYPE_RECV = 2

# Command IDs
CMD_GET_DEVICE_INFO = 213
CMD_AUTH_INIT = 73
CMD_AUTH_VERIFY = 86
CMD_SET_TIME = 84
CMD_GET_STATE = 210
CMD_GET_CONFIG = 211
CMD_GET_BATTERY = 66
CMD_SET_POWER_MODE = 220
CMD_RESET_FILTER = 222

# Config entry keys
CONF_ADDRESS = "address"
CONF_NAME = "name"
CONF_MODEL = "model"

# Device aliases derived from BLE name
ALIAS_CTW3 = "CTW3"
ALIAS_CTW2 = "CTW2"
ALIAS_W5C = "W5C"
ALIAS_W5N = "W5N"
ALIAS_W5 = "W5"
ALIAS_W4XUVC = "W4XUVC"
ALIAS_W4X = "W4X"

# BLE name prefixes used for discovery
PETKIT_NAME_PREFIXES = (
    "Petkit_CTW",
    "Petkit_W4",
    "Petkit_W5",
)

# Aliases that use the CTW3 26-byte state format
CTW3_ALIASES = {ALIAS_CTW3}

# Models that use all-zero device_id for auth secret computation
ZERO_DEVICE_ID_MODELS = {ALIAS_CTW3}

# Poll interval in seconds
POLL_INTERVAL = 60

# Epoch offset: seconds from Unix epoch (1970) to Petkit epoch (2000-01-01 UTC)
PETKIT_EPOCH_OFFSET = 946684800

# Flow rate and divisor per alias for water volume calculation
FLOW_RATE_LPM: dict[str, float] = {
    ALIAS_W5C: 1.3,
}
FLOW_DIVISOR: dict[str, float] = {
    ALIAS_W5C: 1.0,
    ALIAS_W4X: 1.8,
    ALIAS_CTW3: 3.0,
}
DEFAULT_FLOW_RATE_LPM = 1.5
DEFAULT_FLOW_DIVISOR = 2.0

# Power coefficient (watts) for energy calculation
POWER_COEFF_W: dict[str, float] = {
    ALIAS_W5C: 0.182,
}
DEFAULT_POWER_COEFF_W = 0.75

# Filter life base days
FILTER_LIFE_NORMAL_DAYS = 60
FILTER_LIFE_SMART_DAYS = 30

# Auth sleep between commands (seconds)
AUTH_STEP_DELAY = 0.3

# Options
CONF_DEBUG = "debug"
