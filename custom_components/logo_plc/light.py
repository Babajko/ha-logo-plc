"""Light platform: LOGO! outputs presented as on/off lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DOMAIN, DOM_LIGHT
from .entity import LogoControllableEntity
from .models import entities_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        LogoLight(runtime.coordinator, runtime.hub, entry, item)
        for item in entities_of(entry.options)
        if item[CONF_DOMAIN] == DOM_LIGHT
    )


class LogoLight(LogoControllableEntity, LightEntity):
    """An on/off light (no brightness)."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
