"""Tests for the pymodbus hub wrapper (with a fake client)."""

from unittest.mock import patch

import pytest
from pymodbus.exceptions import ConnectionException

from custom_components.logo_plc.hub import LogoHub, LogoReadError


class FakeResult:
    def __init__(self, bits=None, error=False):
        self.bits = bits if bits is not None else [False] * 8
        self._error = error

    def isError(self):
        return self._error


class FakeClient:
    def __init__(self, host, port=502, timeout=3.0):
        self.connected = False
        self.reads = []
        self.writes = []
        self.read_results = None  # queue of results or exceptions

    async def connect(self):
        self.connected = True
        return True

    def close(self):
        self.connected = False

    async def read_coils(self, address, count=1, slave=1):
        self.reads.append((address, count))
        if self.read_results:
            item = self.read_results.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return FakeResult(bits=[True] * count)

    async def write_coil(self, address, value, slave=1):
        self.writes.append((address, value))
        return FakeResult()


def _hub():
    return LogoHub("host", reconnect_delay=0)


async def test_read_coils_returns_bits():
    with patch("custom_components.logo_plc.hub.AsyncModbusTcpClient", FakeClient):
        hub = _hub()
        assert await hub.read_coils(8192, 4) == [True, True, True, True]


async def test_pulse_writes_true_then_false():
    with patch("custom_components.logo_plc.hub.AsyncModbusTcpClient", FakeClient):
        hub = _hub()
        await hub.pulse(21, 0)
    assert hub._client.writes == [(21, True), (21, False)]


async def test_reconnects_and_retries_once():
    with patch("custom_components.logo_plc.hub.AsyncModbusTcpClient", FakeClient):
        hub = _hub()
        hub._client.read_results = [ConnectionException("drop"), FakeResult(bits=[True])]
        assert await hub.read_coils(0, 1) == [True]


async def test_error_result_raises():
    with patch("custom_components.logo_plc.hub.AsyncModbusTcpClient", FakeClient):
        hub = _hub()
        hub._client.read_results = [FakeResult(error=True)]
        with pytest.raises(LogoReadError):
            await hub.read_coils(0, 1)
