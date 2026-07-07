"""The Siemens LOGO! PLC integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    CONF_OUTPUTS,
    CONF_PORT,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STATE_ADDRESS,
    DEFAULT_PORT,
    DEFAULT_PULSE_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
)
from .coordinator import LogoCoordinator
from .hub import LogoError, LogoHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]

_DEVICE_CLASSES = ["switch", "outlet"]

OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_STATE_ADDRESS): cv.positive_int,
        vol.Required(CONF_PULSE_ADDRESS): cv.positive_int,
        vol.Optional(
            CONF_PULSE_DURATION, default=DEFAULT_PULSE_DURATION
        ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
        vol.Optional(CONF_ICON): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): vol.In(_DEVICE_CLASSES),
    }
)

PLC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=247)
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_OUTPUTS, default=list): [OUTPUT_SCHEMA],
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [PLC_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class LogoRuntimeData:
    """What we hang off the config entry at runtime."""

    hub: LogoHub
    coordinator: LogoCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import any YAML-configured PLCs into config entries."""
    for plc in config.get(DOMAIN, []):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=plc
            )
        )
    return True


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
