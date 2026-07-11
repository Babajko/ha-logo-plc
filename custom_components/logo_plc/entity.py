"""Shared entity helpers and base classes."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AREA,
    CONF_CONTROL,
    CONF_DOMAIN,
    CONF_ICON,
    CONF_NAME,
    CONF_PULSE_ADDRESS,
    CONF_STATE_ADDRESS,
    CONF_WRITE_ADDRESS,
    CTRL_IMPULSE,
    DEFAULT_ICONS,
    DOM_BINARY_SENSOR,
    DOM_BUTTON,
    DOM_SWITCH,
    DOMAIN,
)
from .control import LogoControl
from .coordinator import LogoCoordinator
from .hub import LogoError, LogoHub


def logo_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device grouping every entity of one LOGO! PLC."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Siemens",
        model="LOGO!",
    )


def entity_unique_id(entry: ConfigEntry, item: dict[str, Any]) -> str:
    """Unique id for any entity type. Single source used by every platform
    and by the stale-entity cleanup, so they always agree."""
    domain = item[CONF_DOMAIN]
    if domain == DOM_BINARY_SENSOR:
        return f"{entry.entry_id}_sensor_{item[CONF_STATE_ADDRESS]}"
    if domain == DOM_BUTTON:
        return f"{entry.entry_id}_button_{item[CONF_PULSE_ADDRESS]}"
    control = item.get(CONF_CONTROL)
    if domain == DOM_SWITCH and control == CTRL_IMPULSE:
        # Legacy id, kept so pre-existing switch entities survive.
        return f"{entry.entry_id}_{item[CONF_STATE_ADDRESS]}"
    key = (
        item.get(CONF_STATE_ADDRESS)
        or item.get(CONF_WRITE_ADDRESS)
        or item.get(CONF_PULSE_ADDRESS)
    )
    return f"{entry.entry_id}_{domain}_{control or 'x'}_{key}"


class LogoAreaEntity:
    """Assigns the configured area once, on first registration.

    Only applied when the entity has no area yet, so a later manual move
    to another room is respected.
    """

    _configured_area: str | None = None
    hass: Any
    registry_entry: Any
    entity_id: str

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()  # type: ignore[misc]
        area_id = self._configured_area
        if not area_id or self.registry_entry is None or self.registry_entry.area_id:
            return
        if ar.async_get(self.hass).async_get_area(area_id) is None:
            return
        er.async_get(self.hass).async_update_entity(self.entity_id, area_id=area_id)


class LogoControllableEntity(LogoAreaEntity, CoordinatorEntity[LogoCoordinator]):
    """Base for light/fan/switch — delegates on/off to LogoControl."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LogoCoordinator,
        hub: LogoHub,
        entry: ConfigEntry,
        item: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._control = LogoControl(hub, item)
        self._configured_area = item.get(CONF_AREA)
        self._attr_name = item[CONF_NAME]
        self._attr_unique_id = entity_unique_id(entry, item)
        self._attr_assumed_state = self._control.assumed_state
        icon = item.get(CONF_ICON) or DEFAULT_ICONS.get(item[CONF_DOMAIN])
        if icon:
            self._attr_icon = icon
        self._attr_device_info = logo_device_info(entry)

    @property
    def is_on(self) -> bool | None:
        return self._control.is_on(self.coordinator)

    @property
    def available(self) -> bool:
        return self._control.available(super().available, self.coordinator)

    async def _async_set(self, target: bool) -> None:
        try:
            await self._control.async_set(target, self.coordinator)
        except LogoError as err:
            raise HomeAssistantError(
                f"Failed to set {self._attr_name}: {err}"
            ) from err
