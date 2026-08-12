"""Constants for the SPRSUN CG248075 Modbus integration."""
from __future__ import annotations

DOMAIN = "sprsun"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 5  # light poll period (HA coordinator update_interval)
DEFAULT_FULL_INTERVAL = 20  # full register_limit map cadence (seconds)
DEFAULT_MESSAGE_WAIT_MS = 350
DEFAULT_FULL_WAIT_MS = 450
DEFAULT_MAX_BLOCK = 125
DEFAULT_REGISTER_LIMIT = 413  # full map; lower if EW11 soak shows high errors
DEFAULT_MODBUS_TIMEOUT = 3.0
MODBUS_CLIENT_RETRIES = 0
MODBUS_RECONNECT_DELAY = 3600.0  # disable pymodbus auto-reconnect spin; we reopen
MAX_BLOCK_RETRIES = 1

CONF_SLAVE = "slave"
CONF_REGISTER_LIMIT = "register_limit"
CONF_MESSAGE_WAIT_MS = "message_wait_milliseconds"
CONF_FULL_INTERVAL = "full_interval"
CONF_FULL_WAIT_MS = "full_wait_milliseconds"
CONF_MAX_BLOCK = "max_block"

# Live-confirmed scales (docs/03-key-registers.md)
SCALE_OVERRIDES = {
    14: 0.1,
    15: 0.1,
    17: 0.5,
    18: 0.1,
    21: 0.5,
    22: 0.5,
    27: 1.0,
}
RAW_ONLY = {47, 48}

GROUP_ORDER = [
    "status",
    "control_flags",
    "temps",
    "machine",
    "failures",
    "setpoints",
    "pressures",
    "info",
    "protect",
    "pressure_protect",
    "defrost",
    "schedule",
    "antilegionella",
    "dcfan",
    "eco",
    "unit",
    "calibration",
    "mv_eev",
    "av_eev",
    "frequency",
    "frequency_eco",
    "frequency_night",
    "frequency_test",
    "misc",
]

ADDR_POWER_MARKER = 50
ADDR_MODE = 54
ADDR_SETPOINT_DHW = 202
ADDR_SETPOINT_COOL = 203
ADDR_SETPOINT_HEAT = 204

# Fast-path addresses — polled every scan_interval.
# Output Symbol 1/3 (4, 6) keep compressor / fan / pumps live.
# Demoted from light (full poll only): EEV1 (28), Comp A (35).
LIGHT_ADDRS = frozenset(
    {
        4,  # Output Symbol 1 — Compressor, Fan
        6,  # Output Symbol 3 — A/C PUMP, Pump
        14,
        15,
        17,
        18,
        21,
        22,
        27,
        30,
        36,
        38,
        ADDR_POWER_MARKER,
        ADDR_MODE,
        ADDR_SETPOINT_DHW,
        ADDR_SETPOINT_COOL,
        ADDR_SETPOINT_HEAT,
    }
)

MODE_OPTIONS = {
    0: "DHW",
    1: "Heating",
    2: "Cooling",
    3: "Heating+DHW",
    4: "Cooling+DHW",
}

DEVICE_CLASS_RUNNING = {(4, 0), (4, 5), (6, 0), (6, 6)}
DEVICE_CLASS_PROBLEM = {(2, 4), (3, 6)}

# Circular live-log (in-memory). UI shows a short tail; dump service writes full buffer.
LIVE_LOG_CAPACITY = 10_000
LIVE_LOG_UI_LINES = 50

# Bit edges to record in the live log when light/full values change.
LIVE_LOG_WATCH_BITS: tuple[tuple[int, int, str], ...] = (
    (4, 0, "Compressor"),
    (4, 5, "Fan"),
    (6, 0, "A/C PUMP"),
    (6, 6, "Pump"),
    (50, 0, "Power"),
)
