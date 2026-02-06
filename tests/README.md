# Hardware test guide for Jubilee

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

The tests read environment variables from `.env` files or from the command line.

- Create a file `.env.hardware` in the repo root (next to `src/` and `tests/`) with:

```
JUBILEE_SIM=0
JUBILEE_ADDRESS=192.168.1.2
```

Replace `192.168.1.2` with your printer’s IP.

- Alternatively, you can pass the address via `pytest` CLI:

```powershell
pytest -q --jubilee-env hardware --jubilee-address 192.168.1.2
```

When running tests via `pytest`, the loader in `tests/conftest.py` automatically reads `.env.sim` or `.env.hardware`. When executing files directly (like `python tests/test_homing.py`), the test uses the shared env utility to load `.env.hardware`.

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

Skips automatically if `JUBILEE_SIM` is true or `JUBILEE_ADDRESS` is missing.

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
- Simulation is selected by `JUBILEE_SIM=1` (default via `.env.sim`); hardware uses `JUBILEE_SIM=0`.
- Transports:
  - `MockTransport`: deterministic axes and world state for tests
  - `HTTPTransport`: real hardware via `/machine/code`, `rr_gcode`, and object model

Happy testing! 🚀
