# Architecture prep — logo_plc integration

Design notes to settle before writing code. Read together with
DECISIONS.md. This is the plan, not the truth — verify API details
(pymodbus, HA config-entry helpers) against the installed versions as
we go.

## Goal recap

One Home Assistant `switch` per LOGO! output. The switch reads the
output coil for its on/off state and fires an impulse on a separate
coil to toggle the relay. Configurable from the UI (config flow +
options) and from YAML (imported into a config entry). Distributed as
a HACS custom integration.

## Repo layout

```
ha-logo-plc/
├── custom_components/
│   └── logo_plc/
│       ├── __init__.py          # setup / unload, YAML import, wiring
│       ├── manifest.json        # domain, version, pymodbus requirement
│       ├── const.py             # DOMAIN, CONF_* keys, defaults
│       ├── hub.py               # pymodbus client wrapper (connect/read/pulse)
│       ├── coordinator.py       # DataUpdateCoordinator polling state coils
│       ├── config_flow.py       # UI flow + options flow + import
│       ├── switch.py            # LogoSwitch entity
│       ├── strings.json         # UI strings (source)
│       └── translations/
│           ├── en.json
│           └── uk.json          # optional
├── docs/
│   └── architecture-prep.md     # this file
├── hacs.json
├── manifest is under custom_components/logo_plc/
├── README.md
├── LICENSE
├── DECISIONS.md
└── LEARNING_LOG.md
```

## Data model

**Config entry = one LOGO device.**

`entry.data` (connection, set once in the config flow):

- `host` (str)
- `port` (int, default 502 — note the old YAML used 504)
- `slave` (int, default 1)
- `scan_interval` (int seconds, default 1)
- `name` (str, device name, e.g. "LOGO1")

`entry.options` (editable via options flow): a list of outputs, each:

- `name` (str)
- `state_address` (int) — coil read for on/off, e.g. 8192
- `pulse_address` (int) — coil pulsed to toggle, e.g. 21
- `pulse_duration` (float seconds, default 1.0)
- `icon` (str, optional, e.g. `mdi:lightbulb`)
- `device_class` (str, optional — HA `SwitchDeviceClass`, `switch` or
  `outlet`)

The Q -> pulse-address map is irregular, so both addresses are always
entered by hand. There is no derived formula.

## Modbus access (hub.py)

Own `pymodbus` async client, one per config entry.

- Connect: `AsyncModbusTcpClient(host, port=port)`, `await connect()`.
- Read state: `read_coils(address, count, slave=slave)` (function 1).
- Pulse: `write_coil(pulse_address, True, slave=slave)`, wait
  `pulse_duration`, `write_coil(pulse_address, False, slave=slave)`
  (function 5).

Reads: compute the min and max of all configured `state_address`
values and read the covering span in one `read_coils` call, then index
each output by `state_address - base`. For a LOGO! the state coils are
contiguous (8192..8211) so this is one cheap read per poll. If the span
is ever unreasonably large (sparse addresses), fall back to per-coil
reads. Start simple; optimise only if needed.

### pymodbus version risk (flag)

The pymodbus API has shifted across 3.x (keyword `slave` vs `unit`,
positional vs keyword args, `.bits` on the read result, client
connect/close names). HA also pins a specific pymodbus version for its
own modbus integration. **Before writing hub.py, check the pymodbus
version actually installed in the target HA and match `manifest.json`
requirements to a compatible range** to avoid a dependency clash with
the built-in modbus integration. Don't code against a remembered API —
read the installed package's signatures.

## Coordinator (coordinator.py)

A `DataUpdateCoordinator[dict[int, bool]]`:

- `update_interval = timedelta(seconds=scan_interval)`.
- `_async_update_data`: read the state span via the hub, return a map
  `{state_address: bool}`.
- On a Modbus error, raise `UpdateFailed` so entities go unavailable
  and HA retries.

Switches read their value from `coordinator.data[state_address]`.

## Switch (switch.py)

`LogoSwitch(CoordinatorEntity, SwitchEntity)`:

- `unique_id = f"{entry_id}_{state_address}"` (stable across renames).
- `device_info` ties it to the LOGO device (identifiers
  `(DOMAIN, entry_id)`, name, manufacturer "Siemens", model "LOGO!").
- `is_on = coordinator.data.get(state_address)`.
- `assumed_state = False` — we read the real coil, so state is known.
- `icon`, `device_class` from the output config.
- `async_turn_on` / `async_turn_off`: fire a pulse via the hub, then
  ask the coordinator to refresh so the read reflects the new relay
  state. Consider a short delay before the confirming read (the relay
  needs a moment) and an optional optimistic UI update in between.

### Open decision — turn_on / turn_off semantics

1. **Smart toggle (leaning this way).** Read current state; only pulse
   when the requested state differs from the actual state. Makes the
   switch behave like a real on/off control even though the hardware
   only understands "toggle". Risk: if the state read is stale or
   wrong, a press can be swallowed or doubled.
2. **Always pulse.** Every turn_on and turn_off pulses regardless of
   state. Dumb but predictable; matches the old buttons exactly.

Decide before writing `async_turn_on`. Whichever we pick, keep the
pulse itself (write true / wait / write false) in `hub.py` so the
entity stays thin.

## Config flow (config_flow.py)

**User step (add a LOGO):** form for name, host, port, slave,
scan_interval. Validate by opening a Modbus connection and doing one
read; fail with a clear error if unreachable. `unique_id = host:port`
to prevent duplicates.

**Options flow (manage outputs):** a menu to add / edit / remove
outputs. Each add/edit is a form with the per-output fields above.
Store the resulting list in `entry.options`; reload the entry on save
so switches appear/disappear without an HA restart.

**Import step:** `async_step_import` maps a YAML block to the same
entry shape.

## YAML import (__init__.py)

`async_setup` reads an optional `logo_plc:` block and, for each device,
fires an import flow. Rough shape:

```yaml
logo_plc:
  - name: LOGO1
    host: 192.168.0.2
    port: 504
    slave: 1
    scan_interval: 1
    outputs:
      - name: "Q1"
        state_address: 8192
        pulse_address: 21
        pulse_duration: 1
      - name: "Q3"
        state_address: 8194
        pulse_address: 7
```

Both UI and YAML end up as identical config entries; the switch/coord
code never sees where the config came from.

## manifest.json (planned)

```json
{
  "domain": "logo_plc",
  "name": "Siemens LOGO! PLC",
  "version": "0.1.0",
  "config_flow": true,
  "documentation": "https://github.com/<user>/ha-logo-plc",
  "issue_tracker": "https://github.com/<user>/ha-logo-plc/issues",
  "codeowners": ["@<user>"],
  "iot_class": "local_polling",
  "integration_type": "hub",
  "requirements": ["pymodbus>=3.6,<4"]
}
```

`version` is required by HACS (unlike core integrations). The
`requirements` range is a placeholder — pin it to match the installed
pymodbus (see the version risk above).

## Testing

- `pytest-homeassistant-custom-component` with a mocked pymodbus client
  (no real PLC in unit tests).
- Cover: coordinator maps reads to `{address: bool}` correctly; switch
  `is_on` reflects coordinator data; pulse writes true then false with
  the right address; smart-toggle only pulses when state differs (if we
  pick option 1); config-flow happy path and unreachable-host error;
  YAML import produces the expected entry.
- Static: `ruff check`, `mypy`, and HA `hassfest` (via the HACS/HA
  GitHub Actions or locally). Nothing is "done" until these pass.

## Build order (small steps, each ending in a commit + review)

1. Scaffolding + these docs. *(done)*
2. manifest + const + hub.py + coordinator + minimal `__init__` that
   connects and logs reads. Verify against a real LOGO.
3. switch.py, read-only: states show up as switches (turn_on/off
   no-op). Confirm states track the relays.
4. Add pulse control + settle the toggle-semantics decision.
5. config_flow user step (add a device from the UI).
6. options flow (add / edit / remove outputs).
7. YAML import.
8. strings/translations, tests, tidy.
9. Tag a release; install via HACS on the Pi5 and verify end to end.

## Deployment (Pi5)

Custom integration, so no Docker. During development, get the code onto
the Pi5's `/config/custom_components/logo_plc/` (git pull or a symlink
to a clone) and restart HA. For milestones, tag a GitHub release and
update through HACS. Pin down SSH access and the exact pull/symlink
choice when we first deploy (tracked as an open item in DECISIONS.md).

## CI (optional, later)

A GitHub Actions workflow running `hassfest`, HACS validation and
`ruff` on push keeps the repo releasable. Add once the code exists.
