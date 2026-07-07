"""Switch platform: one entity per LOGO! output."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_OUTPUTS,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_STATE_ADDRESS,
    DEFAULT_PULSE_DURATION,
    DOMAIN,
)
from .coordinator import LogoCoordinator
from .hub import LogoError, LogoHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a switch for each configured output."""
    runtime = entry.runtime_data
    outputs = entry.options.get(CONF_OUTPUTS, [])
    async_add_entities(
        LogoSwitch(runtime.coordinator, runtime.hub, entry, output)
        for output in outputs
    )


class LogoSwitch(CoordinatorEntity[LogoCoordinator], SwitchEntity):
    """A LOGO! output: reads the Q coil, toggles via an impulse coil."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LogoCoordinator,
        hub: LogoHub,
        entry: ConfigEntry,
        output: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._state_address = output[CONF_STATE_ADDRESS]
        self._pulse_address = output[CONF_PULSE_ADDRESS]
        self._pulse_duration = output.get(
            CONF_PULSE_DURATION, DEFAULT_PULSE_DURATION
        )
        self._attr_name = output[CONF_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{self._state_address}"
        if output.get(CONF_ICON):
            self._attr_icon = output[CONF_ICON]
        if output.get(CONF_DEVICE_CLASS):
            self._attr_device_class = output[CONF_DEVICE_CLASS]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Siemens",
            model="LOGO!",
        )

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self._state_address)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._state_address in (self.coordinator.data or {})
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._apply(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._apply(False)

    async def _apply(self, target: bool) -> None:
        """Smart toggle: only pulse when the real state differs."""
        current = self.coordinator.data.get(self._state_address)
        if current is not None and current == target:
            return
        try:
            await self._hub.pulse(self._pulse_address, self._pulse_duration)
        except LogoError as err:
            raise HomeAssistantError(
                f"Failed to pulse {self._attr_name}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
