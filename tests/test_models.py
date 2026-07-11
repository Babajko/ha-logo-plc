"""Tests for entity config migration and validation."""

import pytest
import voluptuous as vol

from custom_components.logo_plc import models
from custom_components.logo_plc.const import (
    CONF_CONTROL,
    CONF_DEVICE_CLASS,
    CONF_DOMAIN,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_STATE_ADDRESS,
    CONF_WRITE_ADDRESS,
    CTRL_IMPULSE,
    CTRL_SIMPLE,
    DOM_BINARY_SENSOR,
    DOM_BUTTON,
    DOM_SWITCH,
)


def test_legacy_impulse_switch_migrates():
    out = models.validate_entity(
        {
            "type": "impulse_switch",
            "name": "Q1",
            "state_address": 8192,
            "pulse_address": 21,
        }
    )
    assert out[CONF_DOMAIN] == DOM_SWITCH
    assert out[CONF_CONTROL] == CTRL_IMPULSE
    assert out[CONF_STATE_ADDRESS] == 8192
    assert out[CONF_PULSE_ADDRESS] == 21


def test_legacy_sensor_migrates():
    out = models.validate_entity(
        {"type": "sensor", "name": "Q11", "state_address": 8202}
    )
    assert out[CONF_DOMAIN] == DOM_BINARY_SENSOR
    assert CONF_CONTROL not in out


def test_light_latching_valid():
    out = models.validate_entity(
        {
            "domain": "light",
            "control": "latching",
            "name": "Hall",
            "state_address": 8192,
            "write_address": 16,
        }
    )
    assert out[CONF_DOMAIN] == "light"
    assert out[CONF_WRITE_ADDRESS] == 16


def test_missing_address_raises():
    with pytest.raises(vol.Invalid):
        models.validate_entity(
            {"domain": "switch", "control": "impulse", "name": "x", "state_address": 8192}
        )


def test_missing_control_raises():
    with pytest.raises(vol.Invalid):
        models.validate_entity(
            {"domain": "light", "name": "x", "state_address": 8192}
        )


def test_unknown_domain_raises():
    with pytest.raises(vol.Invalid):
        models.validate_entity({"domain": "nope", "name": "x"})


def test_clean_coerces_strings():
    out = models.clean_entity(
        {
            "domain": "switch",
            "control": "impulse",
            "name": "x",
            "state_address": "8192",
            "pulse_address": "21",
            "pulse_duration": "1",
        }
    )
    assert out[CONF_STATE_ADDRESS] == 8192
    assert isinstance(out[CONF_STATE_ADDRESS], int)
    assert out[CONF_PULSE_DURATION] == 1.0


def test_device_class_dropped_for_light():
    out = models.clean_entity(
        {
            "domain": "light",
            "control": "impulse",
            "name": "x",
            "state_address": 8192,
            "pulse_address": 21,
            "device_class": "outlet",
        }
    )
    assert CONF_DEVICE_CLASS not in out


def test_read_address():
    assert (
        models.read_address({CONF_DOMAIN: DOM_BINARY_SENSOR, CONF_STATE_ADDRESS: 8202})
        == 8202
    )
    assert (
        models.read_address(
            {
                CONF_DOMAIN: DOM_SWITCH,
                CONF_CONTROL: CTRL_IMPULSE,
                CONF_STATE_ADDRESS: 8192,
            }
        )
        == 8192
    )
    assert (
        models.read_address(
            {CONF_DOMAIN: DOM_SWITCH, CONF_CONTROL: CTRL_SIMPLE, CONF_WRITE_ADDRESS: 16}
        )
        is None
    )
    assert (
        models.read_address({CONF_DOMAIN: DOM_BUTTON, CONF_PULSE_ADDRESS: 10}) is None
    )


def test_entities_of_migrates_list():
    options = {
        "outputs": [
            {
                "type": "impulse_switch",
                "name": "Q1",
                "state_address": 8192,
                "pulse_address": 21,
            }
        ]
    }
    entities = models.entities_of(options)
    assert entities[0][CONF_DOMAIN] == DOM_SWITCH
    assert entities[0][CONF_CONTROL] == CTRL_IMPULSE
