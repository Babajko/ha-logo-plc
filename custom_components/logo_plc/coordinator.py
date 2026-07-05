"""Polls a LOGO! for its output states and hands them to the switches."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MAX_BLOCK_READ_SPAN
from .hub import LogoError, LogoHub

_LOGGER = logging.getLogger(__name__)


class LogoCoordinator(DataUpdateCoordinator[dict[int, bool]]):
    """Reads the configured state coils once per interval.

    The Q coils are contiguous, so the common case is a single block
    read covering every configured ``state_address``. If the addresses
    are spread far apart, fall back to reading them one at a time.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        hub: LogoHub,
        state_addresses: Iterable[int],
        scan_interval: int,
        name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._hub = hub
        self._addresses = sorted({int(a) for a in state_addresses})

    async def _async_update_data(self) -> dict[int, bool]:
        if not self._addresses:
            return {}
        try:
            return await self._read_states()
        except LogoError as err:
            raise UpdateFailed(str(err)) from err

    async def _read_states(self) -> dict[int, bool]:
        base = self._addresses[0]
        span = self._addresses[-1] - base + 1
        if span <= MAX_BLOCK_READ_SPAN:
            bits = await self._hub.read_coils(base, span)
            return {addr: bits[addr - base] for addr in self._addresses}
        return {addr: await self._hub.read_coil(addr) for addr in self._addresses}
