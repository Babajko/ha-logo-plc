"""Async Modbus TCP wrapper for a single Siemens LOGO! PLC.

Pure Python — no Home Assistant imports — so it can be driven from the
standalone probe script as well as from the integration.

LOGO! 8 Modbus TCP is known to drop connections under continuous
polling. To cope, every request runs under a lock, with a per-request
timeout, and a single reconnect-and-retry: on a connection error the
stale socket is closed and the request is tried once more on a fresh
connection. Closing the dead socket also avoids leaking one of the
LOGO!'s limited (8) connection slots.

pymodbus renamed the unit-id keyword from ``slave`` to ``device_id``
across 3.x, so the raw calls try ``slave`` first and fall back to
``device_id``. The LOGO! default unit id is 1, which is both keywords'
default too.
"""

from __future__ import annotations

import asyncio
import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)

# Errors that mean "connection trouble" and are worth one reconnect+retry.
_CONNECTION_ERRORS = (ModbusException, asyncio.TimeoutError, OSError)


class LogoError(Exception):
    """Base error for LOGO! Modbus operations."""


class LogoConnectionError(LogoError):
    """The PLC could not be reached."""


class LogoReadError(LogoError):
    """A Modbus request returned an error response."""


class LogoHub:
    """Owns one Modbus TCP connection to a LOGO! and serialises access."""

    def __init__(
        self,
        host: str,
        port: int = 502,
        slave: int = 1,
        timeout: float = 3.0,
        reconnect_delay: float = 1.0,
    ) -> None:
        self._host = host
        self._port = port
        self._slave = slave
        self._reconnect_delay = reconnect_delay
        self._client = AsyncModbusTcpClient(host, port=port, timeout=timeout)
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def reconnect_delay(self) -> float:
        return self._reconnect_delay

    async def connect(self) -> None:
        """Open the connection, raising LogoConnectionError on failure."""
        async with self._lock:
            await self._ensure_connected()

    async def close(self) -> None:
        async with self._lock:
            self._safe_close()

    async def read_coils(self, address: int, count: int = 1) -> list[bool]:
        """Read ``count`` coils starting at ``address`` (FC01)."""
        result = await self._request(
            lambda: self._read_coils_raw(address, count),
            f"read_coils(address={address}, count={count})",
        )
        return list(result.bits[:count])

    async def read_coil(self, address: int) -> bool:
        return (await self.read_coils(address, 1))[0]

    async def write_coil(self, address: int, value: bool) -> None:
        """Write a single coil (FC05)."""
        await self._request(
            lambda: self._write_coil_raw(address, value),
            f"write_coil(address={address}, value={value})",
        )

    async def pulse(self, address: int, duration: float = 1.0) -> None:
        """Impulse a coil: set true, hold ``duration`` seconds, set false.

        The lock is released between the two writes, so state reads can
        still run while the pulse is held.
        """
        await self.write_coil(address, True)
        try:
            await asyncio.sleep(duration)
        finally:
            await self.write_coil(address, False)

    # -- internals -------------------------------------------------------

    async def _request(self, call, desc: str):
        """Run one Modbus call with a single reconnect-and-retry."""
        async with self._lock:
            last_err: Exception | None = None
            for attempt in (1, 2):
                if attempt > 1:
                    # This LOGO! holds a single Modbus connection, so give
                    # it time to release the old slot before reconnecting.
                    await asyncio.sleep(self._reconnect_delay)
                try:
                    await self._ensure_connected()
                    result = await call()
                except _CONNECTION_ERRORS as err:
                    last_err = err
                    self._safe_close()
                    continue
                if result is None or result.isError():
                    # A data-level error (e.g. illegal address) won't be
                    # fixed by retrying, so surface it directly.
                    raise LogoReadError(f"{desc}: {result}")
                return result
        raise LogoConnectionError(f"{desc} failed after retry: {last_err}")

    async def _ensure_connected(self) -> None:
        if self._client.connected:
            return
        # Some pymodbus versions return None (not True) from connect(),
        # so trust the `connected` property rather than the return value.
        await self._client.connect()
        if not self._client.connected:
            raise LogoConnectionError(f"cannot connect to {self._host}:{self._port}")

    def _safe_close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 - close is best effort
            pass

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
