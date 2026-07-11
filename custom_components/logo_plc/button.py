"""Button platform: momentary impulse buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_AREA,
    CONF_DOMAIN,
    CONF_ICON,
    CONF_NAME,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    DEFAULT_ICONS,
    DEFAULT_PULSE_DURATION,
    DOM_BUTTON,
)
from .entity import LogoAreaEntity, entity_unique_id, logo_device_info
from .hub import LogoError, LogoHub
from .models import entities_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = entry.runtime_data.hub
    async_add_entities(
        LogoButton(hub, entry, item)
        for item in entities_of(entry.options)
        if item[CONF_DOMAIN] == DOM_BUTTON
    )


class LogoButton(LogoAreaEntity, ButtonEntity):
    """Fires a pulse on a network-input coil when pressed."""

    _attr_has_entity_name = True

    def __init__(
        self, hub: LogoHub, entry: ConfigEntry, item: dict[str, Any]
    ) -> None:
        self._hub = hub
        self._configured_area = item.get(CONF_AREA)
        self._address = item[CONF_PULSE_ADDRESS]
        self._duration = item.get(CONF_PULSE_DURATION, DEFAULT_PULSE_DURATION)
        self._attr_name = item[CONF_NAME]
        self._attr_unique_id = entity_unique_id(entry, item)
        self._attr_icon = item.get(CONF_ICON) or DEFAULT_ICONS[DOM_BUTTON]
        self._attr_device_info = logo_device_info(entry)

    async def async_press(self) -> None:
        try:
            await self._hub.pulse(self._address, self._duration)
        except LogoError as err:
            raise HomeAssistantError(
                f"Failed to pulse {self._attr_name}: {err}"
            ) from err
