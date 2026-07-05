# LOGO! 8 Modbus notes and script retrospective

Research to back the design. Sources at the bottom. The addresses in
the existing YAML line up with the well-known LOGO! 8 map, which is the
main thing this confirms.

## LOGO! 8 Modbus address map

LOGO! 8 (0BA8) is a Modbus TCP **server only** — it never initiates a
request, it answers a master (Home Assistant here). No RTU/ASCII on the
built-in Ethernet port. Up to 8 concurrent TCP connections. Default
port 502.

The internal-resource -> Modbus map (the version that matches the real
addresses in our YAML):

```
I  1-24      -->    0 -   23   (discrete input, FC02)
Q  1-20      --> 8192 - 8211   (coil, FC01 read / FC05 write)
M  1-64      --> 8256 - 8319   (coil)
V  0.0-850.7 -->    0 - 6807   (coil; bit = byte*8 + bit)
AI 1-8       -->    0 -    7   (input register, FC04)
VW 0-850     -->    0 -  424   (holding register, FC03/06/16)
AQ 1-8       -->  512 -  519   (holding register)
AM 1-64      -->  528 -  591   (holding register)
```

Function codes we care about:

- FC01 read coils — read output state Q (8192+) and V-memory bits.
- FC05 write single coil — pulse a V-memory bit (network input).

Note: some third-party "addressing" pages give a different, generic
table (Q1–Q16 starting at coil 0, M1 at 32). That does **not** match a
real LOGO! 8, and it does not match our device. Trust the map above —
it agrees with the working YAML (Q1 reads at 8192).

## How the existing setup actually works

Two different coils per output, which is the whole reason the old YAML
needed a sensor **and** a button:

- **State (read):** `binary_sensor` reads the Q coil, e.g. Q1 -> 8192,
  Q2 -> 8193, ... This is the real relay output the LOGO! program
  drives.
- **Control (write):** the pulse `script` writes a **V-memory bit**
  (a "network input") true, waits 1s, writes false. Those pulse
  addresses in the YAML (6, 7, 8 ... 23) are coils 0–6807, i.e. V0.6,
  V0.7, V1.0 ... V2.7. The LOGO! program wires each of those network
  inputs into an impulse (latching) relay block that toggles the output.

So the flow is: HA pulses a V-memory network input -> the LOGO! program
toggles its impulse relay -> the Q output flips -> HA reads the new Q
state on the next poll. The output coil itself is program-driven;
writing Q directly over Modbus would just get overwritten by the
program, which is exactly why the pulse-to-network-input pattern is
used.

The Q -> network-input mapping is irregular (Q1->V0.6=coil21? no:
Q1 pulse = coil 21 = V2.5; Q3 = coil 7 = V0.7; Q5 = coil 15 = V1.7).
There is no formula — it is whatever the LOGO! program author wired.
This confirms the design decision to configure both addresses per
output by hand.

## Port 504

The LOGO! 8 Modbus default is 502; the YAML uses 504 for both PLCs.
That is fine (it is just whatever port the LOGO! Ethernet connection
was set to, or a forward), but the integration default should be 502
with the port configurable. Worth confirming on the device when we
wire up the config flow, so the default we present matches reality.

## Prior art: nos86/hacs-modbus-logo

There is an existing HACS integration for exactly this class of device:
`nos86/hacs-modbus-logo` (MIT, ~HA 2024.11, pins pymodbus 3.6.8). It is
a fork/extension of Home Assistant's official `modbus` integration
under a `modbus_logo` domain, configured the same way as core modbus
(YAML), and it adds one feature relevant to us: a `sync` flag inside
`verify`.

Their model for a switch:

- `address` = the network-input coil to write (a V-memory bit).
- `verify.address` = the Q coil to read back for the true state.
- `verify.sync: true` = whenever HA's state changes, push it back to
  the PLC network input so HA and PLC stay aligned (with an explicit
  warning about write/read feedback loops).

What this tells us:

- Our read-Q-for-state + write-network-input-to-control model is the
  established correct approach; nos86 does the same with `address` +
  `verify`.
- Their `sync` flag is essentially our "smart toggle": keep the UI and
  the real relay in agreement by reading Q and only acting on genuine
  changes.

Important difference: nos86 writes a **level** to the network input
(set it and, with sync, hold it), which suits a program where the
network input directly represents the desired state. Our LOGO! program
uses **impulse** relays, which need a momentary **pulse** (true -> wait
-> false), not a held level. So nos86's switch would not drive our
impulse relays correctly out of the box — the pulse is our specific
requirement.

### Recommendation

Keep building our own focused integration rather than adopting nos86:

- It is config-flow / UI-first (nos86 is YAML-only, and it re-skins the
  whole core modbus platform — much heavier than we need).
- It models the impulse **pulse** directly, which nos86 does not.
- It stays small: one switch type, one job.

But borrow the good ideas: read Q for authoritative state, and the
"sync"/verify concept becomes our smart-toggle (only pulse when the
requested state differs from the real Q state). Credit nos86 in the
README as prior art. Worth skimming their `switch.py` once for the
verify/sync implementation before we write ours.

## Retrospective — improvements over the old YAML

1. **One entity instead of two.** The switch reads Q for state and
   pulses the network input to toggle, replacing the binary_sensor +
   template button + script trio per output.
2. **Batch the reads.** The Q coils are contiguous (8192–8211), so one
   FC01 read of up to 20 coils per poll replaces 20 separate
   per-sensor polls. Fewer round trips, and LOGO! only allows 8
   connections total, so being frugal matters.
3. **One persistent connection per PLC** via our own pymodbus client,
   instead of the core modbus integration's per-entity access.
4. **Configurable pulse length.** Hardcoded 1s today. An impulse relay
   triggers on the edge, so a shorter pulse (300–500 ms) is usually
   enough; keep 1s as the default (it is known-good) but make it a
   per-output option.
5. **Smart toggle removes the "wrong direction" risk.** Because we read
   the real Q state, turn_on/turn_off can pulse only when needed,
   instead of the old fire-and-forget button that could double-toggle.
6. **Do not write Q directly.** The program owns Q; external writes get
   overwritten. Always write the network input. (Guard against anyone
   later "optimising" the switch to write 8192+.)

### Optional, program-side (only if the user wants to touch the LOGO!)

If the LOGO! program were changed to drive each output from an
RS/latching block controlled by two network inputs (set + reset), or a
level-controlled network input, HA could write the desired state
directly with no pulse and no toggle ambiguity. That is a nicer model
but requires editing and re-downloading the LOGO! program, so it stays
an optional future note — the pulse approach works with the program as
it is today.

## Sources

- nos86/hacs-modbus-logo — https://github.com/nos86/hacs-modbus-logo
- LOGO! 8 Modbus TCP I/O addressing and function codes —
  https://industrialmonitordirect.com/blogs/knowledgebase/siemens-logo-modbus-tcpip-io-addressing-and-function-codes
- Siemens: LOGO! 8 Modbus address table (109478291) and Modbus TCP
  configuration (84957064) — referenced via Siemens Industry Support.
- HA community: Creating Modbus configuration for a Siemens LOGO! —
  https://community.home-assistant.io/t/creating-modbus-configuration-for-a-siemens-logo/535762
