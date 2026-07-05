#!/usr/bin/env python3
"""Check a Siemens LOGO! over Modbus TCP using the integration's hub.

Runs without Home Assistant — it imports hub.py / const.py directly, so
it needs only pymodbus installed:

    python -m venv .venv && source .venv/bin/activate
    pip install pymodbus

Read the output states of one PLC (Q1..Q20 by default):

    python scripts/probe.py 192.168.0.2 --port 504

Pulse one network-input coil (the way an output is toggled), then exit:

    python scripts/probe.py 192.168.0.2 --port 504 --pulse 21 --duration 1

Read an arbitrary coil range:

    python scripts/probe.py 192.168.0.2 --port 504 --base 0 --count 24
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Import hub.py / const.py directly, without loading the HA package
# __init__ (which pulls in Home Assistant).
_PKG = Path(__file__).resolve().parent.parent / "custom_components" / "logo_plc"
sys.path.insert(0, str(_PKG))

from const import LOGO_Q_COIL_BASE, LOGO_Q_COUNT, coil_to_vm  # noqa: E402
from hub import LogoError, LogoHub  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe a Siemens LOGO! over Modbus TCP")
    parser.add_argument("host", help="PLC IP address, e.g. 192.168.0.2")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default 502)")
    parser.add_argument("--slave", type=int, default=1, help="Modbus unit id (default 1)")
    parser.add_argument(
        "--base",
        type=int,
        default=LOGO_Q_COIL_BASE,
        help=f"first coil to read (default Q1 = {LOGO_Q_COIL_BASE})",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=LOGO_Q_COUNT,
        help=f"how many coils to read (default {LOGO_Q_COUNT})",
    )
    parser.add_argument(
        "--pulse",
        type=int,
        metavar="COIL",
        help="pulse this coil (network input) then exit",
    )
    parser.add_argument("--duration", type=float, default=1.0, help="pulse length in seconds")
    return parser


async def _run(args: argparse.Namespace) -> int:
    hub = LogoHub(args.host, port=args.port, slave=args.slave)
    try:
        await hub.connect()
        print(f"connected to {args.host}:{args.port} (unit {args.slave})")

        if args.pulse is not None:
            print(f"pulsing coil {args.pulse} ({coil_to_vm(args.pulse)}) for {args.duration}s")
            await hub.pulse(args.pulse, args.duration)
            print("done")
            return 0

        bits = await hub.read_coils(args.base, args.count)
        for i, on in enumerate(bits):
            addr = args.base + i
            label = f"Q{i + 1}" if args.base == LOGO_Q_COIL_BASE else f"coil {addr}"
            print(f"  {label:>6} (coil {addr}): {'ON' if on else 'off'}")
        return 0
    except LogoError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    finally:
        await hub.close()


def main() -> int:
    return asyncio.run(_run(_build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
