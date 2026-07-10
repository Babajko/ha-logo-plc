# Siemens LOGO! PLC for Home Assistant

A Home Assistant integration for Siemens LOGO! PLCs over Modbus TCP.

Each PLC output (Q) shows up as a switch that reflects the real relay
state and toggles it with a short impulse — the way LOGO! impulse
relays are meant to be driven. Everything is set up from the UI; no
YAML editing of `modbus`, `template` and `script` blocks.

> Status: early development. Not on the default HACS list yet — add it
> as a custom repository (see below).

## Why

The usual way to wire a LOGO! into Home Assistant is a pile of
`modbus` binary_sensors for the output states, `template` buttons, and
`script` sequences that pulse a coil to flip each relay. It works, but
it's a lot of hand-written YAML and the button and the state end up as
two unrelated entities.

This integration folds that into a single switch per output: it reads
the output coil for state and writes the pulse coil when you flip it.

## How it works

LOGO! outputs are often driven as impulse relays: a short pulse on one
coil toggles the relay, and a separate coil reports whether it's on.
The two coils are different Modbus addresses, and the mapping between
an output and its pulse coil isn't regular — so both addresses are
configured per output.

- State: read of the output coil (e.g. 8192 for Q1).
- Control: pulse on the mapped coil (true, wait, false).

## Entity types

Each output is described by two choices, so it becomes exactly the right
kind of entity.

What it is (domain):

- `light` — a lamp, LED strip or sconce. Shows as a proper light.
- `fan` — an exhaust or ventilation fan. Shows as a fan.
- `switch` — a generic on/off load.
- `binary_sensor` — a read-only indicator (an output you only monitor,
  like a lamp with no control coil).
- `button` — a momentary button that fires a pulse.

How it is controlled (for light / fan / switch):

- `impulse` — reads the Q coil for state and toggles an impulse relay
  with a pulse (only pulses when the state needs to change).
- `latching` — reads the Q coil for state and holds a control coil at a
  level (write 1 = on, 0 = off).
- `simple` — writes a control coil and keeps its own state, with no
  reading back from the PLC.

Everything is configurable from the UI (Settings -> Devices & Services
-> the PLC -> Configure): pick the type, then the control mode, then the
addresses — with an icon picker, a Q-output selector and an advanced
section. There's also an "Edit all as YAML" code editor, and plain YAML.

## Requirements

- Home Assistant with HACS installed.
- A LOGO! reachable over Modbus TCP on your network, with Modbus/TCP
  server enabled in LOGO!Soft Comfort.

## Install

1. In HACS, add this repository as a custom repository of type
   *Integration*: `https://github.com/Babajko/ha-logo-plc`.
2. Install "Siemens LOGO! PLC" from HACS.
3. Restart Home Assistant.
4. Go to Settings -> Devices & Services -> Add Integration -> Siemens
   LOGO! PLC, and enter your PLC's host, port and slave id.
5. Add outputs from the integration's options: for each one give a
   name, the state coil address, the pulse coil address and (optionally)
   the pulse length.

## Configuration

One integration entry per PLC. Each output needs:

| Field           | Meaning                                             |
|-----------------|-----------------------------------------------------|
| Name            | Friendly name for the switch                        |
| State address   | Coil to read for the current on/off state           |
| Pulse address   | Coil to pulse to toggle the relay                   |
| Pulse duration  | How long the pulse is held (seconds, default 1)     |
| Icon            | Optional MDI icon                                   |
| Device class    | Optional switch device class                        |

### YAML

Instead of clicking each output into the UI, you can describe the PLCs
in `configuration.yaml`; the entries are imported and kept in sync on
restart:

```yaml
logo_plc:
  - name: LOGO1
    host: 192.168.0.2
    port: 502
    slave: 1
    scan_interval: 1
    outputs:
      - name: Q1
        state_address: 8192   # Q coil to read
        pulse_address: 21     # network-input coil that toggles it
        pulse_duration: 1
```

A full example for a two-PLC setup is in
[docs/example-configuration.yaml](docs/example-configuration.yaml).

To keep `configuration.yaml` clean, move the config to its own file and
pull it in with `!include`:

```yaml
# configuration.yaml
logo_plc: !include logo_plc.yaml
```

```yaml
# logo_plc.yaml — just the list of PLCs (no top-level key)
- name: LOGO1
  host: 192.168.0.2
  port: 502
  slave: 1
  scan_interval: 1
  outputs:
    - name: Q1
      state_address: 8192
      pulse_address: 21
```

Everything is also editable from the UI: Settings -> Devices &
Services -> the PLC -> Configure lets you add, edit and remove outputs
and change the connection, with no file editing. UI edits are stored in
Home Assistant, not in `configuration.yaml`.

## License

MIT. See [LICENSE](LICENSE).
