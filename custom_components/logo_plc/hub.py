"""Async Modbus TCP wrapper for a single Siemens LOGO! PLC.

Pure Python — no Home Assistant imports — so it can be driven from the
standalone probe script as well as from the integration.

pymodbus changed the unit-id keyword from ``slave`` to ``device_id``
across 3.x releases, so the read/write helpers try ``slave`` first and
fall back to ``device_id``. The LOGO! default unit id is 1, which is
also both keywords' default, so this stays correct even on versions
that quietly ignore the argument.
"""

from __future__ import annotations

import asyncio
import logging

from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)


class LogoError(Exception):
    """Base error for LOGO! Modbus operations."""


class LogoConnectionError(LogoError):
    """The PLC could not be reached."""


class LogoReadError(LogoError):
    """A Modbus request returned an error response."""


class LogoHub:
    """Owns one Modbus TCP connection to a LOGO! and serialises access."""

    def __init__(self, host: str, port: int = 502, slave: int = 1) -> None:
        self._host = host
        self._port = port
        self._slave = slave
        self._client = AsyncModbusTcpClient(host, port=port)
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def connect(self) -> None:
        """Open the connection, raising LogoConnectionError on failure."""
        async with self._lock:
            await self._ensure_connected()

    async def close(self) -> None:
        async with self._lock:
            self._client.close()

    async def read_coils(self, address: int, count: int = 1) -> list[bool]:
        """Read ``count`` coils starting at ``address`` (FC01)."""
        async with self._lock:
            await self._ensure_connected()
            result = await self._read_coils_raw(address, count)
        if result is None or result.isError():
            raise LogoReadError(f"read_coils(address={address}, count={count}): {result}")
        return list(result.bits[:count])

    async def read_coil(self, address: int) -> bool:
        return (await self.read_coils(address, 1))[0]

    async def write_coil(self, address: int, value: bool) -> None:
        """Write a single coil (FC05)."""
        async with self._lock:
            await self._ensure_connected()
            result = await self._write_coil_raw(address, value)
        if result is None or result.isError():
            raise LogoReadError(f"write_coil(address={address}, value={value}): {result}")

    async def pulse(self, address: int, duration: float = 1.0) -> None:
        """Impulse a coil: set true, hold ``duration`` seconds, set false.

        The lock is released during the wait, so state reads can still
        run while the pulse is held.
        """
        await self.write_coil(address, True)
        try:
            await asyncio.sleep(duration)
        finally:
            await self.write_coil(address, False)

    # -- internals -------------------------------------------------------

    async def _ensure_connected(self) -> None:
        if self._client.connected:
            return
        # Some pymodbus versions return None (not True) from connect(),
        # so trust the `connected` property rather than the return value.
        await self._client.connect()
        if not self._client.connected:
            raise LogoConnectionError(f"cannot connect to {self._host}:{self._port}")

    async def _read_coils_raw(self, address: int, count: int):
        try:
            return await self._client.read_coils(address, count=count, slave=self._slave)
        except TypeError:
            return await self._client.read_coils(
                address, count=count, device_id=self._slave
            )

    async def _write_coil_raw(self, address: int, value: bool):
        try:
            return await self._client.write_coil(address, value, slave=self._slave)
        except TypeError:
            return await self._client.write_coil(address, value, device_id=self._slave)
