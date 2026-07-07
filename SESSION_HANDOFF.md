# Session handoff

Where things stand and how to pick up in the next session (which will
run under WSL, where the shell can reach this folder — this session's
sandbox could not, so no git/lint/tests were run here).

## Read first, in this order

1. `DECISIONS.md` — every decision made so far + open questions.
2. `docs/architecture-prep.md` — file-by-file design of the integration.
3. `docs/logo-modbus-notes.md` — LOGO! Modbus facts + script retrospective.
4. `LEARNING_LOG.md` — session log + (empty) mistakes ledger.

## What exists in the repo now

Planning docs, the Modbus core, and the full HA integration (config
flow + switch). Verified against real PLCs for reads and pulses; the HA
side has NOT yet been loaded in Home Assistant.

```
ha-logo-plc/
├── README.md
├── LICENSE
├── hacs.json
├── .gitignore
├── DECISIONS.md
├── LEARNING_LOG.md
├── SESSION_HANDOFF.md            # this file
├── custom_components/logo_plc/
│   ├── manifest.json             # domain, version, pymodbus requirement
│   ├── const.py                  # constants, defaults, address helpers
│   ├── hub.py                    # async pymodbus wrapper (no HA imports)
│   ├── coordinator.py            # DataUpdateCoordinator over the hub
│   ├── __init__.py               # config entry setup / unload
│   ├── config_flow.py            # add PLC + add/remove outputs
│   ├── switch.py                 # LogoSwitch, smart-toggle
│   ├── strings.json
│   └── translations/en.json
├── scripts/
│   └── probe.py                  # standalone live-PLC check (no HA needed)
└── docs/
    ├── architecture-prep.md
    └── logo-modbus-notes.md
```

Done: YAML import (`async_setup` + `async_step_import`), plus a
ready-to-use `docs/example-configuration.yaml` for both PLCs with every
mapped output from the original script. Switches use
`has_entity_name = True` (friendly names like "LOGO1 Q1").

Not created yet: tests, CI. GitHub user (Babajko) is filled into
manifest.json and README. LICENSE still says "Ruslan" — change if a
different name should appear.

## Before deploying — sanity checks in the venv

```bash
source .venv/bin/activate
pip install homeassistant ruff        # ruff optional but recommended
python -m py_compile custom_components/logo_plc/*.py
ruff check custom_components/logo_plc
```

## Load it in Home Assistant (Pi5)

1. Copy `custom_components/logo_plc/` to `/config/custom_components/logo_plc/`
   on the Pi5 (git pull / scp / Samba).
2. Restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> "Siemens LOGO!
   PLC". Enter e.g. name `LOGO1`, host `192.168.0.2`, port `504`,
   unit id `1`, scan interval `1`.
4. On the new integration press Configure -> Add an output. Example
   for LOGO1 Q1: name `Q1`, state address `8192`, pulse address `21`,
   pulse duration `1`. Then "Save and finish".
5. A switch entity appears and reflects the relay; toggling it pulses
   the network-input coil.

Watch the 8-connection limit: while the old YAML modbus is still
running it competes for slots. For a clean test, disable the old
modbus/template/script blocks for the outputs you are trying, or expect
occasional connection contention.

## Verify the Modbus core against a real LOGO! (do this first)

```bash
cd ~/projects/logo_plc
python -m venv .venv && source .venv/bin/activate
pip install pymodbus

# read the output states (Q1..Q20); use the real port (YAML uses 504)
python scripts/probe.py 192.168.0.2 --port 504

# toggle one output via its network-input coil, e.g. LOGO1 Q1 = coil 21
python scripts/probe.py 192.168.0.2 --port 504 --pulse 21 --duration 1
```

Expected: a connected line, then Q1..Q20 with ON/off matching the real
relays. If the read works, hub.py + the addressing are correct and we
can wire the HA side. Note which pymodbus version got installed
(`python -c "import pymodbus; print(pymodbus.__version__)"`) so we pin
`manifest.json` to match the HA on the Pi5.

## Decisions locked in

- Domain `logo_plc`. One `switch` per output: reads the Q coil for
  state, pulses a V-memory network-input coil to toggle.
- Own pymodbus client (not the core modbus integration).
- Config flow (UI) + YAML import. One config entry per PLC.
- Public GitHub repo `ha-logo-plc`, HACS-installable. HACS already on
  the Pi5. Dev deploy = git pull / symlink into
  `/config/custom_components/logo_plc/` + HA restart.
- Commits / README / public text read as human-written. No AI tells.

## Still open (decide when we reach them)

- turn_on / turn_off: smart toggle (leaning yes) vs always pulse.
  Decide before writing `switch.py`.
- Exact Pi5 deploy mechanics (SSH, pull vs symlink, restart method).
- Confirm the real Modbus port on the PLCs (YAML says 504, LOGO!
  default is 502).
- LICENSE copyright holder: replace "Ruslan" with the name to publish
  under.
- Fill the `<user>` / `<your-user>` placeholders in README, hacs.json
  targets and manifest with the actual GitHub username.

## Next session — start here

The integration is code-complete for a first load: add a PLC and its
outputs from the UI, get smart-toggle switches. Next:

1. Load it on the Pi5 (steps above) and verify a switch reads state and
   toggles a relay. Note the installed pymodbus version and adjust the
   manifest pin if needed.
2. Then: YAML import (`async_setup` + import flow), tests
   (`pytest-homeassistant-custom-component`, mock pymodbus), and a small
   CI workflow (hassfest + ruff). Fill the README/manifest placeholders
   and push to GitHub.

Decisions already locked: smart toggle, two PLCs (.2 and .3). hub.py
tolerates the pymodbus `slave` -> `device_id` rename, so the code runs
on current pymodbus regardless.

## One-time setup to do under WSL

```bash
cd ~/projects/logo_plc

# git + GitHub (public repo named ha-logo-plc)
git init
git add .
git commit -m "Project scaffolding, design docs and LOGO! Modbus notes"
gh repo create ha-logo-plc --public --source=. --remote=origin --push
# (or create the repo on github.com and: git remote add origin ...; git push -u origin main)

# dev environment for the integration + tests
python -m venv .venv
source .venv/bin/activate
pip install homeassistant pymodbus pytest pytest-homeassistant-custom-component ruff mypy
```

Then confirm the shell can see the repo (`ls`, `git status`) — this is
the step that failed in the previous session's sandbox and should work
natively under WSL.
