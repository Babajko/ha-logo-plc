"""Binary sensor platform: read-only LOGO! output indicators."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_STATE_ADDRESS,
    CONF_TYPE,
    TYPE_SENSOR,
)
from .coordinator import LogoCoordinator
from .entity import logo_device_info
from .models import entities_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a binary sensor for each read-only indicator."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        LogoBinarySensor(coordinator, entry, item)
        for item in entities_of(entry.options)
        if item[CONF_TYPE] == TYPE_SENSOR
    )


class LogoBinarySensor(CoordinatorEntity[LogoCoordinator], BinarySensorEntity):
    """Reads one Q coil and reports it as on/off."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LogoCoordinator,
        entry: ConfigEntry,
        item: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._address = item[CONF_STATE_ADDRESS]
        self._attr_name = item[CONF_NAME]
        self._attr_unique_id = f"{entry.entry_id}_sensor_{self._address}"
        if item.get(CONF_ICON):
            self._attr_icon = item[CONF_ICON]
        if item.get(CONF_DEVICE_CLASS):
            self._attr_device_class = item[CONF_DEVICE_CLASS]
        self._attr_device_info = logo_device_info(entry)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self._address)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._address in (self.coordinator.data or {})
        )
