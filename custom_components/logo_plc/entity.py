"""Shared entity helpers."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def logo_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device grouping every entity of one LOGO! PLC."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Siemens",
        model="LOGO!",
    )
