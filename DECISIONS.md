# Decisions

Running log of design decisions for the `ha-logo-plc` integration.
Read this at the start of every session before touching code. Newest
entries go at the bottom of each section.

## What this is

A Home Assistant custom integration (`custom_components/logo_plc`) that
talks to Siemens LOGO! PLCs over Modbus TCP. It replaces the older
YAML setup, which stitched together `modbus` binary_sensors,
`template` buttons and `script` pulse sequences per output.

Goal: one configurable `switch` entity per LOGO output that shows the
real relay state and toggles it via an impulse.

## Background: the old YAML

- Two Modbus TCP hubs: `siemens_logo1` (192.168.0.2), `siemens_logo2`
  (192.168.0.3), port 504, slave 1.
- `binary_sensors` read coils at 8192+ = the actual output (Q) state
  (Q1 -> 8192, Q2 -> 8193, ...).
- `script.*_pulse` writes a *network* coil (e.g. 21, 23, 7, 22, ...)
  true -> wait 1s -> false. That pulse toggles an impulse relay behind
  the output.
- `template` buttons just call the pulse scripts.

Key facts carried over from the old config:

- The control is impulse-based: the "button" address and the "state"
  address are different Modbus coils.
- The Q -> pulse address mapping is irregular (Q1=21, Q3=7, Q5=15, ...),
  so both addresses must be configurable per output. No formula.
- Pulse length was hardcoded to 1s.
- LOGO2 only declared a subset of outputs, so the set of outputs per
  device has to be flexible.

## Decisions

- **Domain:** `logo_plc`.
- **Entity model:** one `switch` per output.
  - `is_on` reflects the real Q state (read of the state coil).
  - `turn_on` / `turn_off` fire an impulse on the pulse coil
    (true -> pulse_duration -> false).
- **Modbus:** the integration owns its own `pymodbus` client. Not the
  built-in `modbus` integration, because it exposes `modbus.write_coil`
  for writes but has no read service for other integrations to consume,
  so the switch could not read state through it without depending on
  separately-defined binary_sensors. Owning the client keeps the
  integration self-contained. pymodbus is the same library HA's own
  modbus integration wraps.
- **Config:** UI config flow + options flow, plus YAML import so both
  paths work.
  - One config entry = one LOGO device (host, port, slave,
    scan_interval) = one HA device grouping its switches.
  - Per output: name, state_address, pulse_address, pulse_duration,
    icon, device_class. Both addresses entered by hand (irregular map).
- **Distribution:** public GitHub repo `ha-logo-plc`, HACS-installable.
  - Repo root has `custom_components/logo_plc/`, `hacs.json`,
    `manifest.json` with a `version`, README, LICENSE (MIT).
  - HACS is already installed on the Pi5.
  - Dev iteration: `git pull` (or symlink) into
    `/config/custom_components/logo_plc/` on the Pi5 over SSH, restart
    HA. HACS is for tagged releases, not every small change.
- **Writing style:** commits, README and public text read as
  human-written. No AI boilerplate, no marketing filler.

## Environment

- HA runs on a Raspberry Pi 5 on the same LAN as the LOGO PLCs.
- Dev happens on a Windows box with WSL Ubuntu; code lives at
  `~/projects/logo_plc` in WSL.
- Test account / owner: st24kv72@gmail.com.

## Research findings (2026-07-05)

See `docs/logo-modbus-notes.md` for the full write-up. Key points:

- The old YAML addresses match the standard LOGO! 8 map. State reads
  come from the Q coils (8192+, FC01); the pulse writes go to
  V-memory bits (coils 0–6807, FC05) that the LOGO! program wires into
  impulse relays. Confirmed both-addresses-per-output is unavoidable.
- Do **not** write the Q coils directly — the program drives them and
  would overwrite an external write. Always pulse the network input.
- Prior art exists: `nos86/hacs-modbus-logo` (HACS, MIT). It solves the
  same state-vs-input desync with a `verify` + `sync` flag, but it is
  YAML-only, re-skins the whole core modbus platform, and writes a
  level (not a pulse), so it does not drive impulse relays as-is.
  Decision: keep our own focused, config-flow, pulse-based integration;
  borrow the verify/sync idea as our smart-toggle; credit nos86 as
  prior art in the README.
- Read optimisation: the Q coils are contiguous, so poll them in one
  FC01 read per PLC instead of per-output.
- Default port for LOGO! 8 is 502; our YAML uses 504. Config default
  should be 502, port configurable.
- Live read + pulse confirmed 2026-07-05: `scripts/probe.py` read
  Q1..Q20 on both PLCs (192.168.0.2 and .3) and a pulse on a mapped
  LOGO2 network-input coil toggled the output and back. hub.py, the
  addressing and the impulse path are all verified against real
  hardware.
- **LOGO! caps at 8 concurrent Modbus TCP connections.** The running HA
  saturated them and blocked the probe until a slot freed. Keep one
  persistent connection per PLC (we do), and when cutting over remove
  the old YAML modbus so old + new don't compete for slots.

## Open questions

- **turn_on / turn_off semantics.** Two options, decided at
  implementation time:
  1. Smart toggle: read current Q state, only pulse when the requested
     state differs. Behaves like a normal on/off switch despite the
     impulse hardware.
  2. Always pulse: every turn_on and turn_off fires a pulse regardless
     of current state.
  Leaning toward (1). Confirm before writing switch.py.
- Exact Pi5 deploy mechanics (SSH access, symlink vs pull, HA restart
  method) to be pinned down when we first deploy.

## Conventions (borrowed from the vartovyi project)

- Small steps, each ending in a commit and a pause for the user to
  review or test on the live HA.
- Write a prep-doc before any large step instead of pushing through.
- Keep a `LEARNING_LOG.md` with a mistakes ledger, updated each session.
- Start each session with `git log --oneline` and `git status`, and
  read the ledger.
- Nothing is "done" until ruff / mypy / pytest and HA's own checks pass.
