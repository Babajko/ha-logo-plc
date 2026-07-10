"""Fan platform: LOGO! outputs presented as on/off fans."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DOMAIN, DOM_FAN
from .entity import LogoControllableEntity
from .models import entities_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        LogoFan(runtime.coordinator, runtime.hub, entry, item)
        for item in entities_of(entry.options)
        if item[CONF_DOMAIN] == DOM_FAN
    )


class LogoFan(LogoControllableEntity, FanEntity):
    """An on/off fan (no speed or presets)."""

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
