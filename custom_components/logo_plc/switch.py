"""Switch platform: LOGO! outputs presented as generic on/off switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_CLASS, CONF_DOMAIN, DOM_SWITCH
from .coordinator import LogoCoordinator
from .entity import LogoControllableEntity
from .hub import LogoHub
from .models import entities_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        LogoSwitch(runtime.coordinator, runtime.hub, entry, item)
        for item in entities_of(entry.options)
        if item[CONF_DOMAIN] == DOM_SWITCH
    )


class LogoSwitch(LogoControllableEntity, SwitchEntity):
    """A generic on/off switch."""

    def __init__(
        self,
        coordinator: LogoCoordinator,
        hub: LogoHub,
        entry: ConfigEntry,
        item: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, hub, entry, item)
        if item.get(CONF_DEVICE_CLASS):
            self._attr_device_class = item[CONF_DEVICE_CLASS]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
