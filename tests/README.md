# Tests

## Structure

```
tests/
├── conftest.py                  # fixtures and CLI options
├── machine_basic/               # connectivity, axes, positions, HTTP
├── machine_movement/            # homing, navigation, tool changes
├── tools/                       # camera, light
└── digital_twin/                # mock-only: recording transport, macro expansion, blender



## Running tests

### Mock (no hardware needed)

```powershell
pytest -q --jubilee-env mock
pytest -q --jubilee-env mock -m "not invasive"   # skip motion tests
```

### Hardware

```powershell
pytest -q --jubilee-env hardware --jubilee-address 192.168.1.2
```

Or set in `.env.hardware`:
```
JUBILEE_TRANSPORT=hardware
JUBILEE_ADDRESS=192.168.1.2
```

Then just:
```powershell
pytest -q --jubilee-env hardware
```

## Markers

| Marker | Meaning |
|--------|---------|
| `primary` | connectivity only — run first |
| `secondary` | reads state, no motion |
| `invasive` | moves the machine, changes tool state |

```powershell
pytest -q -m primary
pytest -q -m "primary or secondary"
pytest -q --jubilee-env hardware -m invasive --maxfail=1
```

## Fixtures (`conftest.py`)

| Fixture | Type | Description |
|---------|------|-------------|
| `jubilee_env` | `str` | `"mock"` or `"hardware"` |
| `transport` | `RecordingTransport` | wraps Mock or HTTP transport |
| `motion` | `MotionDriver` | built on `transport` |
| `tool_changer` | `ToolChanger` | built on `transport` |
| `navigator` | `DeckNavigator` | skips if no `JUBILEE_DECK_DEF` set |
| `camera` | `BaseCamera` | mock or hardware depending on env |
| `light` | `BaseLight` | `NeopixelMock` or `Neopixel` |

All commands sent during a test are logged to `pipeline_data/gcode_logs/latest.gcode`
and a copy named after the test file.

## Adding tests

- Use the fixture at the right layer (`motion` not `transport` for movement tests).
- Mark with `primary` / `secondary` / `invasive`.
- Tests that are multi-step procedures with no clear assertion belong in `scripts/` instead.

## Troubleshooting

- `JUBILEE_ADDRESS not set` → add to `.env.hardware` or pass `--jubilee-address`.
- HTTP timeout → check IP, network, firewall, and that DWC is reachable.
- Deck clearance prompt blocks → the hardware transport asks interactively before Z motion.


This guide shows how to run the hardware tests in `science-jubilee` on Windows. It also covers simulation runs when hardware isn’t connected.

## Prerequisites

- Python 3.10+
- Packages:
  - `pytest`
  - `requests`

Install (optional):

```powershell
python -m pip install -U pytest requests
```

## Environment setup

The tests read environment variables from `.env` files or from the command line. The main profiles are:

- **Hardware**: real Jubilee via HTTP/RepRapFirmware
- **Mock**: pure in-process digital twin for fast, offline tests

### .env files

All `.env.*` files live in the repo root (next to `src/` and `tests/`).

**Hardware** – `.env.hardware`:

```
JUBILEE_TRANSPORT=hardware
JUBILEE_ADDRESS=192.168.1.2
```

Replace `192.168.1.2` with your printer’s IP.

**Mock simulation** – `.env.mock`:

```
JUBILEE_TRANSPORT=mock
```

### Selecting the profile

When running tests via `pytest`, the loader in `tests/conftest.py` automatically reads the appropriate `.env.*` file based on `--jubilee-env`:

- `--jubilee-env hardware`  → `.env.hardware`
- `--jubilee-env mock`      → `.env.mock`

Examples:

```powershell
# Hardware, overriding address on the command line
pytest -q --jubilee-env hardware --jubilee-address 192.168.1.2

# Pure mock simulation (default if you don’t specify anything)
pytest -q --jubilee-env mock
```

When executing files directly (like `python tests/test_homing.py`), the tests use the shared env utility to load `.env.hardware` by default for hardware runs.

## Running tests

### Markers and selection

Tests are categorized with markers:

- `primary`: core connectivity (HTTP request, connect)
- `secondary`: informational (available axes)
- `invasive`: motion/homing (changes machine state)

Select by marker:

```powershell
pytest -q -m primary
pytest -q -m secondary
pytest -q -m invasive
```

Combine with environment and filters:

```powershell
pytest -q --jubilee-env hardware -m primary --maxfail=1
pytest -q --jubilee-env hardware -m "primary or secondary"
pytest -q -m "secondary and not invasive"
```

### 1) HTTP smoke test (M115)

Verifies HTTP connectivity with the printer and checks for a plausible firmware reply.

```powershell
pytest -q --jubilee-env hardware -k test_requests_send_gcode_m115
```

Skips automatically unless `JUBILEE_TRANSPORT=hardware` and `JUBILEE_ADDRESS` is set.

### 2) Available axes (works in sim and hardware)

Checks that the transport can report available axes. In simulation, the mock transport returns a deterministic set; in hardware, we require that X and Y are present.

```powershell
pytest -q -k test_available_axes
# Hardware run:
pytest -q --jubilee-env hardware -k test_available_axes
```

### 3) Homing sequence (XYU, then Z)

Performs a basic homing sequence. In tests, Z homing is only allowed once the driver has learned deck clearance.

```powershell
pytest -q -k test_home_xyu_and_z
# Hardware run:
pytest -q --jubilee-env hardware -k test_home_xyu_and_z
```

Manual interactive homing (hardware-only):

```powershell
python tests\test_homing.py
```

This script will:
- Load `.env.hardware` if `JUBILEE_ADDRESS` is not set
- Prompt you to confirm deck clearance via the HTTP transport
- Park any active tool (`T-1`) and home `U`, `Y`, `X`, then `Z`

### Selecting tests / filters

Use `-k` to filter by test name, and `--maxfail=1` to stop early on failures:

```powershell
pytest -q --jubilee-env hardware --maxfail=1 -k "http or homing or available_axes"
```

## Tips and troubleshooting

- If a test says `JUBILEE_ADDRESS not set`, create `.env.hardware` or pass `--jubilee-address`.
- If HTTP requests time out, check:
  - Printer IP address and network connectivity
  - Firewall settings on your PC
  - That the Duet/RepRapFirmware HTTP endpoints are reachable
- The transports use the RRF object model (via `M409`) and fall back to parsing `M114` where needed.
- Deck clearance is enforced by the motion layer; hardware transport may prompt interactively.

## Project notes

- Env utilities live in `src/science_jubilee/utils/env.py` (`load_env_file`, `ensure_env_from_file`).
- Transports are selected via `JUBILEE_TRANSPORT` (and `--jubilee-env`):
  - `MockTransport`: deterministic axes and world state for tests (`--jubilee-env mock`)
  - `HTTPTransport`: real hardware via `/machine/code`, `rr_gcode`, and object model (`--jubilee-env hardware`)

Happy testing!
