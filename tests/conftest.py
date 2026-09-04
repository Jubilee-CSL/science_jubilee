"""Pytest configuration for science_jubilee."""

import os
import sys
from pathlib import Path

import pytest

## Ensure package import for tests without editable install
_root = Path(__file__).resolve().parent.parent
_src_path = _root / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from science_jubilee.utils.env import load_env_file


def pytest_addoption(parser):
    """Register command-line options for simulation vs hardware selection."""
    parser.addoption(
        "--jubilee-env",
        action="store",
        default="mock",
        choices=["hardware", "mock"],
        help="Environment profile: 'mock' uses the mock digital twin, 'hardware' connects to the real machine.",
    )
    parser.addoption(
        "--jubilee-address",
        action="store",
        default=None,
        help="Override the machine IP address (e.g., 192.168.1.2) for hardware runs.",
    )


_MOCK_DEFAULTS = {
    "JUBILEE_TRANSPORT": "mock",
    "JUBILEE_EXPERIMENT_DIR": "src/science_jubilee/decks/example_deck",
    "JUBILEE_CAMERA_CALIB": "src/science_jubilee/calibration/camera_params.yaml",
}


def pytest_configure(config):
    """Apply selected profile and options before tests start."""
    root = Path(__file__).resolve().parent.parent
    profile = config.getoption("--jubilee-env")
    env_file = root / f".env.{profile}"
    load_env_file(env_file)

    # apply built-in mock defaults when no .env.mock file is present
    if profile == "mock" and not env_file.exists():
        for key, val in _MOCK_DEFAULTS.items():
            os.environ.setdefault(key, val)

    addr_opt = config.getoption("--jubilee-address")
    if addr_opt:
        os.environ["JUBILEE_ADDRESS"] = addr_opt

    os.environ.setdefault("JUBILEE_DECK_DEF", "deck.json")


@pytest.fixture
def jubilee_env(request):
    return request.config.getoption("--jubilee-env")


@pytest.fixture
def session():
    from science_jubilee.machine_session import MachineSession

    return MachineSession.from_env()


@pytest.fixture
def transport(session):
    return session.transport


@pytest.fixture
def motion(session):
    return session.motion


@pytest.fixture
def tool_changer(session):
    return session.tool_changer


@pytest.fixture
def navigator(session):
    if session.navigator is None:
        pytest.skip("No deck definition configured; set JUBILEE_DECK_DEF.")
    return session.navigator


@pytest.fixture
def camera(session):
    return session.camera


@pytest.fixture
def light(session):
    return session.light
