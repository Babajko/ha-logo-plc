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

YAML configuration is also accepted and imported into a config entry.

## License

MIT. See [LICENSE](LICENSE).
