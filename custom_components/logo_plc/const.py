"""Constants and small helpers for the logo_plc integration.

Kept free of Home Assistant imports so the standalone probe script can
reuse the helpers.
"""

from __future__ import annotations

DOMAIN = "logo_plc"

# Config entry data (per PLC connection).
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE = "slave"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"

# Config entry options (per entity).
CONF_OUTPUTS = "outputs"  # storage key kept for backward compatibility
CONF_TYPE = "type"
CONF_STATE_ADDRESS = "state_address"
CONF_PULSE_ADDRESS = "pulse_address"
CONF_WRITE_ADDRESS = "write_address"
CONF_PULSE_DURATION = "pulse_duration"
CONF_ICON = "icon"
CONF_DEVICE_CLASS = "device_class"

# Legacy entity types (kept only for migrating old stored config).
TYPE_SENSOR = "sensor"
TYPE_BUTTON = "button"
TYPE_IMPULSE_SWITCH = "impulse_switch"
TYPE_LATCHING_SWITCH = "latching_switch"
TYPE_SIMPLE_SWITCH = "simple_switch"

# Two-axis model: domain (what it is) + control (how it is driven).
CONF_DOMAIN = "domain"
CONF_CONTROL = "control"

DOM_LIGHT = "light"
DOM_FAN = "fan"
DOM_SWITCH = "switch"
DOM_BINARY_SENSOR = "binary_sensor"
DOM_BUTTON = "button"

CTRL_IMPULSE = "impulse"
CTRL_LATCHING = "latching"
CTRL_SIMPLE = "simple"

CONTROLLABLE_DOMAINS = (DOM_LIGHT, DOM_FAN, DOM_SWITCH)
ALL_DOMAINS = (DOM_LIGHT, DOM_FAN, DOM_SWITCH, DOM_BINARY_SENSOR, DOM_BUTTON)
ALL_CONTROLS = (CTRL_IMPULSE, CTRL_LATCHING, CTRL_SIMPLE)

# Default MDI icon per domain (light/fan use HA's own defaults).
DEFAULT_ICONS = {
    DOM_SWITCH: "mdi:light-switch",
    DOM_BUTTON: "mdi:gesture-tap-button",
    # Indicators are usually lamps here; a bulb reads as light and HA
    # tints it amber when on, grey when off.
    DOM_BINARY_SENSOR: "mdi:lightbulb",
}

SWITCH_DEVICE_CLASSES = ["switch", "outlet"]
BINARY_SENSOR_DEVICE_CLASSES = [
    "light",
    "power",
    "running",
    "problem",
    "connectivity",
    "door",
    "window",
    "opening",
    "motion",
    "moisture",
    "heat",
    "smoke",
    "safety",
    "plug",
    "presence",
]

# Defaults.
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 1
DEFAULT_PULSE_DURATION = 1.0

# LOGO! 8 Modbus map (see docs/logo-modbus-notes.md).
# Digital outputs Q1..Q20 report their state on coils 8192..8211.
LOGO_Q_COIL_BASE = 8192
LOGO_Q_COUNT = 20

# Above this span we read state coils one by one instead of in a block,
# to avoid a huge range read if someone mixes far-apart addresses.
MAX_BLOCK_READ_SPAN = 128


def q_to_state_coil(q: int) -> int:
    """Coil address that reports LOGO! output Q<q> (q is 1-based)."""
    if not 1 <= q <= LOGO_Q_COUNT:
        raise ValueError(f"Q index out of range (1..{LOGO_Q_COUNT}): {q}")
    return LOGO_Q_COIL_BASE + (q - 1)


def coil_to_vm(coil: int) -> str:
    """Label a V-memory coil for logs, e.g. 21 -> 'V2.5'."""
    return f"V{coil // 8}.{coil % 8}"
