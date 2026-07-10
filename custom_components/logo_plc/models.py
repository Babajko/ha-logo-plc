"""Entity config: migration, validation and helpers.

Shared by YAML import, the YAML editor and the config flow. Kept free
of Home Assistant imports so all of those can reuse it.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from .const import (
    ALL_CONTROLS,
    ALL_DOMAINS,
    CONF_AREA,
    CONF_CONTROL,
    CONF_DEVICE_CLASS,
    CONF_DOMAIN,
    CONF_ICON,
    CONF_NAME,
    CONF_OUTPUTS,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_STATE_ADDRESS,
    CONF_TYPE,
    CONF_WRITE_ADDRESS,
    CONTROLLABLE_DOMAINS,
    CTRL_IMPULSE,
    CTRL_LATCHING,
    CTRL_SIMPLE,
    DOM_BINARY_SENSOR,
    DOM_BUTTON,
    DOM_SWITCH,
    TYPE_BUTTON,
    TYPE_IMPULSE_SWITCH,
    TYPE_LATCHING_SWITCH,
    TYPE_SENSOR,
    TYPE_SIMPLE_SWITCH,
)

# Legacy `type` -> (domain, control).
_LEGACY_MAP: dict[str, tuple[str, str | None]] = {
    TYPE_SENSOR: (DOM_BINARY_SENSOR, None),
    TYPE_BUTTON: (DOM_BUTTON, None),
    TYPE_IMPULSE_SWITCH: (DOM_SWITCH, CTRL_IMPULSE),
    TYPE_LATCHING_SWITCH: (DOM_SWITCH, CTRL_LATCHING),
    TYPE_SIMPLE_SWITCH: (DOM_SWITCH, CTRL_SIMPLE),
}

_DEVICE_CLASS_DOMAINS = (DOM_SWITCH, DOM_BINARY_SENSOR)


def _normalize(item: dict[str, Any]) -> dict[str, Any]:
    """Return the item with a domain (migrating a legacy `type` if needed)."""
    item = dict(item)
    if CONF_DOMAIN not in item:
        legacy = item.pop(CONF_TYPE, TYPE_IMPULSE_SWITCH)
        domain, control = _LEGACY_MAP.get(legacy, (DOM_SWITCH, CTRL_IMPULSE))
        item[CONF_DOMAIN] = domain
        if control and CONF_CONTROL not in item:
            item[CONF_CONTROL] = control
    return item


def required_addresses(domain: str, control: str | None) -> tuple[str, ...]:
    """Address fields an entity of this domain/control must have."""
    if domain == DOM_BINARY_SENSOR:
        return (CONF_STATE_ADDRESS,)
    if domain == DOM_BUTTON:
        return (CONF_PULSE_ADDRESS,)
    if control == CTRL_IMPULSE:
        return (CONF_STATE_ADDRESS, CONF_PULSE_ADDRESS)
    if control == CTRL_LATCHING:
        return (CONF_STATE_ADDRESS, CONF_WRITE_ADDRESS)
    return (CONF_WRITE_ADDRESS,)  # CTRL_SIMPLE


def clean_entity(item: dict[str, Any]) -> dict[str, Any]:
    """Build the stored dict, coercing numbers and dropping empty extras."""
    item = _normalize(item)
    domain = item[CONF_DOMAIN]
    control = item.get(CONF_CONTROL) if domain in CONTROLLABLE_DOMAINS else None
    out: dict[str, Any] = {CONF_DOMAIN: domain, CONF_NAME: item[CONF_NAME]}
    if control:
        out[CONF_CONTROL] = control
    for key in (CONF_STATE_ADDRESS, CONF_PULSE_ADDRESS, CONF_WRITE_ADDRESS):
        if item.get(key) is not None:
            out[key] = int(item[key])
    if item.get(CONF_PULSE_DURATION) is not None:
        out[CONF_PULSE_DURATION] = float(item[CONF_PULSE_DURATION])
    if item.get(CONF_ICON):
        out[CONF_ICON] = item[CONF_ICON]
    if item.get(CONF_DEVICE_CLASS) and domain in _DEVICE_CLASS_DOMAINS:
        out[CONF_DEVICE_CLASS] = item[CONF_DEVICE_CLASS]
    if item.get(CONF_AREA):
        out[CONF_AREA] = item[CONF_AREA]
    return out


def validate_entity(item: Any) -> dict[str, Any]:
    """Validate one entity (from YAML or the YAML editor)."""
    if not isinstance(item, dict):
        raise vol.Invalid("each entity must be a mapping")
    item = _normalize(item)
    domain = item.get(CONF_DOMAIN)
    if domain not in ALL_DOMAINS:
        raise vol.Invalid(f"unknown domain: {domain}")
    control = item.get(CONF_CONTROL) if domain in CONTROLLABLE_DOMAINS else None
    if domain in CONTROLLABLE_DOMAINS and control not in ALL_CONTROLS:
        raise vol.Invalid(f"{domain} needs a valid control mode")
    if not str(item.get(CONF_NAME, "")).strip():
        raise vol.Invalid("name is required")
    for key in required_addresses(domain, control):
        if item.get(key) is None:
            raise vol.Invalid(f"{key} is required for {domain}/{control}")
        try:
            int(item[key])
        except (TypeError, ValueError) as err:
            raise vol.Invalid(f"{key} must be a number") from err
    return clean_entity(item)


def entities_of(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Configured entities, each migrated to the domain/control model."""
    return [_normalize(item) for item in options.get(CONF_OUTPUTS, [])]


def read_address(item: dict[str, Any]) -> int | None:
    """Coil this entity needs the coordinator to poll, if any."""
    domain = item[CONF_DOMAIN]
    control = item.get(CONF_CONTROL)
    if domain == DOM_BINARY_SENSOR:
        return item.get(CONF_STATE_ADDRESS)
    if domain in CONTROLLABLE_DOMAINS and control in (CTRL_IMPULSE, CTRL_LATCHING):
        return item.get(CONF_STATE_ADDRESS)
    return None
