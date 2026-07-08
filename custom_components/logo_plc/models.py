"""Entity type schemas and helpers, shared by setup and the config flow.

Kept free of Home Assistant imports so both YAML import validation and
the config/options flow can reuse the same rules.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from .const import (
    BINARY_SENSOR_DEVICE_CLASSES,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_OUTPUTS,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_STATE_ADDRESS,
    CONF_TYPE,
    CONF_WRITE_ADDRESS,
    DEFAULT_PULSE_DURATION,
    SWITCH_DEVICE_CLASSES,
    TYPE_BUTTON,
    TYPE_IMPULSE_SWITCH,
    TYPE_LATCHING_SWITCH,
    TYPE_SENSOR,
    TYPE_SIMPLE_SWITCH,
)

ENTITY_TYPES = (
    TYPE_SENSOR,
    TYPE_BUTTON,
    TYPE_IMPULSE_SWITCH,
    TYPE_LATCHING_SWITCH,
    TYPE_SIMPLE_SWITCH,
)

_ADDRESS = vol.All(vol.Coerce(int), vol.Range(min=0))
_DURATION = vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10))

# Which optional/typed fields each type accepts (used by clean_entity).
_NUMERIC_FIELDS = (
    CONF_STATE_ADDRESS,
    CONF_PULSE_ADDRESS,
    CONF_WRITE_ADDRESS,
    CONF_PULSE_DURATION,
)
_TEXT_FIELDS = (CONF_ICON, CONF_DEVICE_CLASS)

# Entities whose state comes from reading a coil.
_READ_TYPES = (TYPE_SENSOR, TYPE_IMPULSE_SWITCH, TYPE_LATCHING_SWITCH)


def schema_for_type(entity_type: str) -> vol.Schema:
    """Return the form/validation schema for one entity type (no type key)."""
    name = {vol.Required(CONF_NAME): str}
    icon = {vol.Optional(CONF_ICON): str}
    if entity_type == TYPE_SENSOR:
        return vol.Schema(
            {
                **name,
                vol.Required(CONF_STATE_ADDRESS): _ADDRESS,
                **icon,
                vol.Optional(CONF_DEVICE_CLASS): vol.In(BINARY_SENSOR_DEVICE_CLASSES),
            }
        )
    if entity_type == TYPE_BUTTON:
        return vol.Schema(
            {
                **name,
                vol.Required(CONF_PULSE_ADDRESS): _ADDRESS,
                vol.Optional(
                    CONF_PULSE_DURATION, default=DEFAULT_PULSE_DURATION
                ): _DURATION,
                **icon,
            }
        )
    if entity_type == TYPE_IMPULSE_SWITCH:
        return vol.Schema(
            {
                **name,
                vol.Required(CONF_STATE_ADDRESS): _ADDRESS,
                vol.Required(CONF_PULSE_ADDRESS): _ADDRESS,
                vol.Optional(
                    CONF_PULSE_DURATION, default=DEFAULT_PULSE_DURATION
                ): _DURATION,
                **icon,
                vol.Optional(CONF_DEVICE_CLASS): vol.In(SWITCH_DEVICE_CLASSES),
            }
        )
    if entity_type == TYPE_LATCHING_SWITCH:
        return vol.Schema(
            {
                **name,
                vol.Required(CONF_STATE_ADDRESS): _ADDRESS,
                vol.Required(CONF_WRITE_ADDRESS): _ADDRESS,
                **icon,
                vol.Optional(CONF_DEVICE_CLASS): vol.In(SWITCH_DEVICE_CLASSES),
            }
        )
    if entity_type == TYPE_SIMPLE_SWITCH:
        return vol.Schema(
            {
                **name,
                vol.Required(CONF_WRITE_ADDRESS): _ADDRESS,
                **icon,
                vol.Optional(CONF_DEVICE_CLASS): vol.In(SWITCH_DEVICE_CLASSES),
            }
        )
    raise vol.Invalid(f"unknown entity type: {entity_type}")


def clean_entity(entity_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build a stored entity dict from validated form data."""
    item: dict[str, Any] = {CONF_TYPE: entity_type, CONF_NAME: data[CONF_NAME]}
    for key in _NUMERIC_FIELDS:
        if data.get(key) is not None:
            item[key] = data[key]
    for key in _TEXT_FIELDS:
        if data.get(key):
            item[key] = data[key]
    return item


def validate_entity(item: Any) -> dict[str, Any]:
    """Validate one entity (from YAML or the YAML editor)."""
    if not isinstance(item, dict):
        raise vol.Invalid("each entity must be a mapping")
    data = dict(item)
    entity_type = data.pop(CONF_TYPE, TYPE_IMPULSE_SWITCH)
    if entity_type not in ENTITY_TYPES:
        raise vol.Invalid(f"unknown entity type: {entity_type}")
    validated = schema_for_type(entity_type)(data)
    return clean_entity(entity_type, validated)


def entities_of(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the configured entities, each guaranteed to carry a type.

    Legacy entries without a type default to an impulse switch, which is
    what they were before types existed.
    """
    result: list[dict[str, Any]] = []
    for item in options.get(CONF_OUTPUTS, []):
        result.append({**item, CONF_TYPE: item.get(CONF_TYPE, TYPE_IMPULSE_SWITCH)})
    return result


def read_address(item: dict[str, Any]) -> int | None:
    """Coil this entity needs the coordinator to poll, if any."""
    if item[CONF_TYPE] in _READ_TYPES:
        return item.get(CONF_STATE_ADDRESS)
    return None
