"""Switch platform: impulse, latching and simple LOGO! outputs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_STATE_ADDRESS,
    CONF_TYPE,
    CONF_WRITE_ADDRESS,
    DEFAULT_PULSE_DURATION,
    TYPE_IMPULSE_SWITCH,
    TYPE_LATCHING_SWITCH,
    TYPE_SIMPLE_SWITCH,
)
from .coordinator import LogoCoordinator
from .entity import logo_device_info
from .hub import LogoError, LogoHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the right switch class for each configured switch."""
    from .models import entities_of

    runtime = entry.runtime_data
    entities: list[SwitchEntity] = []
    for item in entities_of(entry.options):
        entity_type = item[CONF_TYPE]
        if entity_type == TYPE_IMPULSE_SWITCH:
            entities.append(
                LogoImpulseSwitch(runtime.coordinator, runtime.hub, entry, item)
            )
        elif entity_type == TYPE_LATCHING_SWITCH:
            entities.append(
                LogoLatchingSwitch(runtime.coordinator, runtime.hub, entry, item)
            )
        elif entity_type == TYPE_SIMPLE_SWITCH:
            entities.append(LogoSimpleSwitch(runtime.hub, entry, item))
    async_add_entities(entities)


def _apply_common(entity: SwitchEntity, entry: ConfigEntry, item: dict[str, Any]) -> None:
    entity._attr_name = item[CONF_NAME]
    if item.get(CONF_ICON):
        entity._attr_icon = item[CONF_ICON]
    if item.get(CONF_DEVICE_CLASS):
        entity._attr_device_class = item[CONF_DEVICE_CLASS]
    entity._attr_device_info = logo_device_info(entry)


class LogoImpulseSwitch(CoordinatorEntity[LogoCoordinator], SwitchEntity):
    """Reads Q; toggles an impulse relay via a pulse (smart toggle)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LogoCoordinator,
        hub: LogoHub,
        entry: ConfigEntry,
        item: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._state_address = item[CONF_STATE_ADDRESS]
        self._pulse_address = item[CONF_PULSE_ADDRESS]
        self._pulse_duration = item.get(CONF_PULSE_DURATION, DEFAULT_PULSE_DURATION)
        self._attr_unique_id = f"{entry.entry_id}_{self._state_address}"
        _apply_common(self, entry, item)

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


class LogoLatchingSwitch(CoordinatorEntity[LogoCoordinator], SwitchEntity):
    """Holds a control coil at a level; reads Q for the real state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LogoCoordinator,
        hub: LogoHub,
        entry: ConfigEntry,
        item: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._hub = hub
        self._state_address = item[CONF_STATE_ADDRESS]
        self._write_address = item[CONF_WRITE_ADDRESS]
        self._attr_unique_id = f"{entry.entry_id}_latching_{self._write_address}"
        _apply_common(self, entry, item)

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
        await self._write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(False)

    async def _write(self, target: bool) -> None:
        try:
            await self._hub.write_coil(self._write_address, target)
        except LogoError as err:
            raise HomeAssistantError(
                f"Failed to set {self._attr_name}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()


class LogoSimpleSwitch(SwitchEntity):
    """Writes a control coil and remembers its own (assumed) state."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self, hub: LogoHub, entry: ConfigEntry, item: dict[str, Any]
    ) -> None:
        self._hub = hub
        self._write_address = item[CONF_WRITE_ADDRESS]
        self._is_on = False
        self._attr_unique_id = f"{entry.entry_id}_simple_{self._write_address}"
        _apply_common(self, entry, item)

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(False)

    async def _write(self, target: bool) -> None:
        try:
            await self._hub.write_coil(self._write_address, target)
        except LogoError as err:
            raise HomeAssistantError(
                f"Failed to set {self._attr_name}: {err}"
            ) from err
        self._is_on = target
        self.async_write_ha_state()
