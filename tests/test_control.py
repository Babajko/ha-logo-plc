"""Tests for the shared on/off control logic."""

from custom_components.logo_plc.const import (
    CONF_CONTROL,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_STATE_ADDRESS,
    CONF_WRITE_ADDRESS,
    CTRL_IMPULSE,
    CTRL_LATCHING,
    CTRL_SIMPLE,
)
from custom_components.logo_plc.control import LogoControl


class FakeHub:
    def __init__(self):
        self.pulses = []
        self.writes = []

    async def pulse(self, address, duration):
        self.pulses.append((address, duration))

    async def write_coil(self, address, value):
        self.writes.append((address, value))


class FakeCoordinator:
    def __init__(self, data):
        self.data = data
        self.refreshed = 0

    async def async_request_refresh(self):
        self.refreshed += 1


async def test_impulse_only_pulses_when_state_differs():
    hub = FakeHub()
    control = LogoControl(
        hub,
        {
            CONF_CONTROL: CTRL_IMPULSE,
            CONF_STATE_ADDRESS: 8192,
            CONF_PULSE_ADDRESS: 21,
            CONF_PULSE_DURATION: 1.0,
        },
    )
    coordinator = FakeCoordinator({8192: True})

    await control.async_set(True, coordinator)
    assert hub.pulses == []  # already on -> no pulse

    await control.async_set(False, coordinator)
    assert hub.pulses == [(21, 1.0)]  # differs -> pulse
    assert coordinator.refreshed == 1


async def test_impulse_pulses_when_state_unknown():
    hub = FakeHub()
    control = LogoControl(
        hub,
        {CONF_CONTROL: CTRL_IMPULSE, CONF_STATE_ADDRESS: 8192, CONF_PULSE_ADDRESS: 21},
    )
    coordinator = FakeCoordinator({})
    await control.async_set(True, coordinator)
    assert len(hub.pulses) == 1


async def test_latching_writes_level_and_refreshes():
    hub = FakeHub()
    control = LogoControl(
        hub,
        {CONF_CONTROL: CTRL_LATCHING, CONF_STATE_ADDRESS: 8192, CONF_WRITE_ADDRESS: 16},
    )
    coordinator = FakeCoordinator({8192: False})
    await control.async_set(True, coordinator)
    assert hub.writes == [(16, True)]
    assert coordinator.refreshed == 1


async def test_simple_keeps_assumed_state():
    hub = FakeHub()
    control = LogoControl(hub, {CONF_CONTROL: CTRL_SIMPLE, CONF_WRITE_ADDRESS: 16})
    coordinator = FakeCoordinator({})
    assert control.assumed_state is True
    assert control.is_on(coordinator) is False
    await control.async_set(True, coordinator)
    assert hub.writes == [(16, True)]
    assert control.is_on(coordinator) is True
    assert coordinator.refreshed == 0
