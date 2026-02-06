"""
Pytest configuration for science_jubilee.

Loads environment variables for simulation or hardware from .env files
to simplify Windows runs without manual exports.
Hardware is allowed for connection-only tests; movement tests that require
user input should be skipped.
"""

import os
import sys
from pathlib import Path
import pytest
## Ensure package import for tests without editable install
_root = Path(__file__).resolve().parent.parent
_src_path = _root / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))


def _load_env_file(env_file: Path):
    if not env_file.exists():
        return
    with env_file.open("r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Do not override already-set environment variables
            if key not in os.environ:
                os.environ[key] = value

def pytest_addoption(parser):
    """Register command-line options for simulation vs hardware selection."""
    parser.addoption(
        "--jubilee-env",
        action="store",
        default="sim",
        choices=["sim", "hardware"],
        help="Environment profile: 'sim' uses the mock digital twin, 'hardware' connects to the real machine.",
    )
    parser.addoption(
        "--jubilee-address",
        action="store",
        default=None,
        help="Override the machine IP address (e.g., 192.168.1.2) for hardware runs.",
    )


def pytest_configure(config):
    """Apply selected profile and options before tests start."""
    root = Path(__file__).resolve().parent.parent
    profile = config.getoption("--jubilee-env")
    filename = ".env.sim" if profile == "sim" else ".env.hardware"
    _load_env_file(root / filename)

    # Ensure JUBILEE_SIM reflects the selected profile unless already set
    if "JUBILEE_SIM" not in os.environ:
        os.environ["JUBILEE_SIM"] = "1" if profile == "sim" else "0"

    # Optional address override from CLI
    addr_opt = config.getoption("--jubilee-address")
    if addr_opt:
        os.environ["JUBILEE_ADDRESS"] = addr_opt


@pytest.fixture
def motion():
    """Provide a MotionDriver instance configured from pytest-selected env.

    Uses JUBILEE_SIM and JUBILEE_ADDRESS set by pytest_configure or shell.
    In simulation, uses MockTransport; on hardware, uses HTTPTransport.
    """
    from science_jubilee.hal.motion_driver import MotionDriver
    from science_jubilee.hal.transport.mock import MockTransport
    from science_jubilee.hal.transport.http import HTTPTransport

    address = os.getenv("JUBILEE_ADDRESS")
    simulated_env = os.getenv("JUBILEE_SIM", "1").strip().lower()
    simulated = simulated_env in ("1", "true", "yes")

    transport = MockTransport() if simulated else HTTPTransport(host=address)
    return MotionDriver(transport)

