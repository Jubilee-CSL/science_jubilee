"""Pytest configuration for science_jubilee.

Loads environment variables for hardware or mock simulation from .env files.
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


def pytest_configure(config):
    """Apply selected profile and options before tests start."""
    root = Path(__file__).resolve().parent.parent
    profile = config.getoption("--jubilee-env")
    env_map = {
        "hardware": ".env.hardware",
        "mock": ".env.mock",
    }
    filename = env_map.get(profile, ".env.mock")
    load_env_file(root / filename)

    # Optional address override from CLI
    addr_opt = config.getoption("--jubilee-address")
    if addr_opt:
        os.environ["JUBILEE_ADDRESS"] = addr_opt

    # Default deck and labware definitions for navigation tests.
    # These can be overridden in .env.mock / .env.hardware if desired.
    os.environ.setdefault("JUBILEE_DECK_DEF", "lab_automation_deck_AFL_bolton.json")
    os.environ.setdefault("JUBILEE_LABWARE_DEF", "20mlscintillation_12_wellplate_18000ul.json")


@pytest.fixture
def jubilee_env(request):
    """Return the selected environment string: 'mock' or 'hardware'."""
    return request.config.getoption("--jubilee-env")


@pytest.fixture
def transport():
    """Provide a transport configured from pytest-selected env.

    - mock     -> MockTransport (wrapped in RecordingTransport)
    - hardware -> HTTPTransport (wrapped in RecordingTransport)
    """
    from science_jubilee.hal.transport.mock import MockTransport
    from science_jubilee.hal.transport.http import HTTPTransport
    from science_jubilee.hal.transport.recording import RecordingTransport

    address = os.getenv("JUBILEE_ADDRESS")
    transport_type = os.getenv("JUBILEE_TRANSPORT", "").strip().lower()

    if transport_type == "hardware":
        base = HTTPTransport(address=address, deck_clear_provider=lambda: True)
    else:
        base = MockTransport()

    log_path = os.getenv("JUBILEE_GCODE_LOG", "gcode_logs/latest.gcode")
    return RecordingTransport(base, log_path=log_path)


@pytest.fixture
def motion(transport):
    """Provide a MotionDriver built on top of the transport fixture."""
    from science_jubilee.hal.motion_driver import MotionDriver
    return MotionDriver(transport)


@pytest.fixture
def tool_changer(transport):
    """Provide a ToolChanger built on top of the transport fixture."""
    from science_jubilee.hal.tool_changer import ToolChanger
    return ToolChanger(transport)


@pytest.fixture
def navigator(motion):
    """
    Construct a reusable DeckNavigator
    test environment.
    """
    from science_jubilee.decks.Deck import Deck
    from science_jubilee.navigation.deck_navigation import (DeckNavigator)

    deck_def = (_get_defs_from_env())
    deck = Deck(deck_def)

    nav = DeckNavigator(driver=motion,deck=deck)

    return nav


# ------------------------------------------------------------------
# Environment helpers
# ------------------------------------------------------------------


def _get_defs_from_env() -> tuple[str, str]:
    """
    Return:
        deck_definition,
        labware_definition

    Environment variables can override defaults.
    """

    deck_def = os.getenv("JUBILEE_DECK_DEF","lab_automation_deck_AFL_bolton.json")

    return deck_def
