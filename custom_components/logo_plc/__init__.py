"""The Siemens LOGO! PLC integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_OUTPUTS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STATE_ADDRESS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
)
from .coordinator import LogoCoordinator
from .hub import LogoError, LogoHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]


@dataclass
class LogoRuntimeData:
    """What we hang off the config entry at runtime."""

    hub: LogoHub
    coordinator: LogoCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a LOGO! PLC from a config entry."""
    hub = LogoHub(
        entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        slave=entry.data.get(CONF_SLAVE, DEFAULT_SLAVE),
    )

    outputs = entry.options.get(CONF_OUTPUTS, [])
    state_addresses = [output[CONF_STATE_ADDRESS] for output in outputs]
    coordinator = LogoCoordinator(
        hass,
        hub,
        state_addresses,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        name=entry.title,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LogoRuntimeData(hub=hub, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime: LogoRuntimeData = entry.runtime_data
        try:
            await runtime.hub.close()
        except LogoError as err:  # pragma: no cover - close is best effort
            _LOGGER.debug("Error closing LOGO! hub: %s", err)
    return unloaded


async def _async_reload_on_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options (outputs) change."""
    await hass.config_entries.async_reload(entry.entry_id)
