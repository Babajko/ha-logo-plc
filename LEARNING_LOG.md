# Learning Log

Notes kept alongside the code: what went well, what broke, and the
mistakes worth not repeating. Append an entry after each working
session, even the quiet ones.

Entry template:

```
## YYYY-MM-DD — <one-line summary>

**Goal:** what the session set out to do.

### What worked
- ...

### What didn't work
- symptom / root cause / how it was caught.

### Decisions made
- decided X because Y. Alternatives: Z.

### Next session
- where to start.
```

---

## Mistakes ledger

A plain log of mistakes made while building this, with symptom and root
cause. Kept so the same trap isn't hit twice.

### 2026-07-05 — jumped to a code cause for an environment problem

**Symptom:** `scripts/probe.py` failed with `cannot connect to
192.168.0.2:504`, while a raw socket to both 504 and 502 reported OPEN.

**Wrong hypothesis:** concluded the bug was in `hub.py`'s
`_ensure_connected`, which trusted the truthiness of pymodbus
`connect()`'s return value. Changed it to rely on the `connected`
property instead. That change is a reasonable hardening, but it was
not the cause — the probe still failed after it.

**Actual root cause:** the LOGO! 8 allows only up to 8 concurrent
Modbus TCP connections, and the user's running Home Assistant (the
existing modbus setup) was holding the available slots. Once a slot
freed up, the same probe connected and read Q1..Q20 fine.

**Detection:** user identified it — the probe worked once HA released
the connection.

**Generalization:** OPEN socket + failing client points at the device,
not the client code. Before "fixing" client code on a connection
failure, check for connection-count contention on the target (LOGO!
caps at 8). Related operational note: while migrating, running the old
YAML modbus and this integration at the same time competes for those 8
slots — remove the old config when cutting over.

---

## Sessions

<!-- newest at the top -->

## 2026-07-05 — Home Assistant wiring (config flow + switch)

**Goal:** turn the verified Modbus core into a loadable HA integration.

### What worked
- Live probe first paid off: reads and a pulse were confirmed on both
  PLCs before any HA code, so the switch could be written against known
  addressing with no guesswork.

### Decisions made
- Smart toggle for turn_on/turn_off (pulse only when the real Q state
  differs). Two PLCs, .2 and .3.
- One config entry per PLC; outputs managed in an options flow
  (add / remove / save). Reload on options change so switches appear
  without an HA restart.

### Next session
- Load on the Pi5, verify a switch toggles a relay, record the pymodbus
  version. Then YAML import, tests, CI, and push to GitHub.

## 2026-07-05 — Modbus core + live probe

**Goal:** write the Modbus layer and a way to verify it against a real
LOGO! before wiring Home Assistant.

### What worked
- Split the pymodbus wrapper (`hub.py`) out with no HA imports so a
  standalone `scripts/probe.py` and the HA coordinator can both use it.
  The probe doubles as the "verify on live PLC" step and settles the
  pymodbus version question early.
- Made hub.py tolerate the pymodbus `slave` -> `device_id` kwarg rename
  (try/except) so it survives whichever 3.x version gets installed.

### Decisions made
- Deliver the Modbus core + probe first; wire HA (manifest, config_flow,
  switch) only after the probe confirms reads/pulses on the real PLC.
  Cleaner test boundary given the user runs from WSL by hand.

### Notes
- The VS Code / Claude runtime hit a transient WSL fault this session
  (ext4 auto-remounted read-only via `errors=remount-ro` after an I/O
  glitch -> EROFS, then SIGBUS on the Claude process, likely from a
  truncated `~/.claude.json`). `wsl --shutdown` cleared it; disk/mem
  were healthy afterwards. Not a project issue.

### Next session
- Run `scripts/probe.py` against the real LOGO!; record the pymodbus
  version; then write manifest + __init__ + config_flow + switch.

## 2026-07-05 — project setup and design agreed

**Goal:** turn the old LOGO! Modbus YAML into a plan for a proper
custom integration.

### What worked
- Reading the old YAML made the impulse-relay model clear: the "button"
  coil and the "state" coil are different addresses, and the Q -> pulse
  map is irregular, so both have to be configurable per output.
- Web research confirmed the addressing against the standard LOGO! 8
  map (Q at 8192+ coils, network inputs in the V-memory coil range) and
  turned up prior art, `nos86/hacs-modbus-logo`, which validates the
  read-Q / write-network-input approach. See `docs/logo-modbus-notes.md`.

### Decisions made
- See DECISIONS.md. Short version: domain `logo_plc`, one `switch` per
  output, own pymodbus client, config flow + YAML import, public
  `ha-logo-plc` repo installed via HACS on the Pi5.
- Deployment for a custom_component is much simpler than the vartovyi
  add-on: no Docker rebuild, just files under `/config/custom_components`
  and an HA restart. Most of the vartovyi deploy pain (CIFS/rsync,
  version-bump cache busting) does not apply here.

### Next session
- Review the architecture prep-doc (docs/architecture-prep.md), then
  start writing the integration: manifest + const + coordinator first,
  config flow and switch after.
