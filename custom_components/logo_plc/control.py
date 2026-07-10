"""Shared on/off control logic for the three control modes.

Used by the light, fan and switch platforms so they behave identically.
"""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_CONTROL,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_STATE_ADDRESS,
    CONF_WRITE_ADDRESS,
    CTRL_IMPULSE,
    CTRL_LATCHING,
    CTRL_SIMPLE,
    DEFAULT_PULSE_DURATION,
)
from .coordinator import LogoCoordinator
from .hub import LogoHub


class LogoControl:
    """Turns an entity's on/off requests into the right Modbus action."""

    def __init__(self, hub: LogoHub, item: dict[str, Any]) -> None:
        self._hub = hub
        self.control = item[CONF_CONTROL]
        self.state_address = item.get(CONF_STATE_ADDRESS)
        self.pulse_address = item.get(CONF_PULSE_ADDRESS)
        self.write_address = item.get(CONF_WRITE_ADDRESS)
        self.pulse_duration = item.get(CONF_PULSE_DURATION, DEFAULT_PULSE_DURATION)
        self._assumed = False

    @property
    def assumed_state(self) -> bool:
        return self.control == CTRL_SIMPLE

    def is_on(self, coordinator: LogoCoordinator) -> bool | None:
        if self.control == CTRL_SIMPLE:
            return self._assumed
        return coordinator.data.get(self.state_address)

    def available(self, base_available: bool, coordinator: LogoCoordinator) -> bool:
        if self.control == CTRL_SIMPLE:
            return True
        return base_available and self.state_address in (coordinator.data or {})

    async def async_set(self, target: bool, coordinator: LogoCoordinator) -> None:
        if self.control == CTRL_IMPULSE:
            current = coordinator.data.get(self.state_address)
            if current is not None and current == target:
                return
            await self._hub.pulse(self.pulse_address, self.pulse_duration)
            await coordinator.async_request_refresh()
        elif self.control == CTRL_LATCHING:
            await self._hub.write_coil(self.write_address, target)
            await coordinator.async_request_refresh()
        else:  # CTRL_SIMPLE
            await self._hub.write_coil(self.write_address, target)
            self._assumed = target
