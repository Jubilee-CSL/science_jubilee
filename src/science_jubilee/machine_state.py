"""Resolve the machine's state, live or otherwise.

One fallback chain shared by everything that needs to know what the machine
looks like when it may not be reachable: the mock transport replays it, and the
digital twin builds its scene from it.

The returned dict has the shape of :meth:`BaseTransport.get_machine_summary`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from science_jubilee._paths import jubilee_dir, machine_state_json

logger = logging.getLogger(__name__)

EMPTY_OFFSETS = [0.0, 0.0, -400.0]


def empty_state() -> dict:
    """A machine with four unconfigured slots and nothing homed."""
    return {
        "transport": None,
        "address": None,
        "firmware": None,
        "deck_clear": True,
        "axes": ["X", "Y", "Z", "U"],
        "homed": [False, False, False, False],
        "homed_map": {},
        "limits": {
            "X": (0.0, 300.0),
            "Y": (0.0, 300.0),
            "Z": (0.0, 200.0),
            "U": (0.0, 300.0),
        },
        "positions": {"X": 0.0, "Y": 0.0, "Z": 0.0, "U": 0.0},
        "active_tool": -1,
        "tools": {str(i): {"name": "None"} for i in range(4)},
        "tool_offsets": {str(i): list(EMPTY_OFFSETS) for i in range(4)},
        "tool_parks": {},
    }


def read_env_address(env_file: Optional[Path] = None) -> Optional[str]:
    """JUBILEE_ADDRESS from .env.hardware, only when transport=hardware."""
    env_file = Path(env_file) if env_file else jubilee_dir() / ".env.hardware"
    try:
        lines = env_file.read_text().splitlines()
    except OSError:
        return None
    values = {}
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    if values.get("JUBILEE_TRANSPORT", "").lower() != "hardware":
        return None
    return values.get("JUBILEE_ADDRESS") or None


def _port_open(address: str, port: int = 80, timeout: float = 0.3) -> bool:
    """Cheap reachability probe: HTTPTransport retries make a blind attempt slow."""
    import socket

    host = address.split("//")[-1].split("/")[0].split(":")[0]
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def query_live(address: str, timeout: float = 3.0) -> Optional[dict]:
    """Full summary straight from the machine, or None if it does not answer."""
    if not _port_open(address):
        logger.debug("No machine listening at %s", address)
        return None
    try:
        from science_jubilee.hal.transport.http import HTTPTransport

        transport = HTTPTransport(address=address)
        if not transport.connect(timeout=timeout):
            return None
        summary = transport.get_machine_summary()
    except Exception as exc:
        logger.debug("Live query to %s failed: %s", address, exc)
        return None
    return summary if summary.get("tools") else None


def load_saved(path: Optional[Path] = None) -> Optional[dict]:
    """Contents of the snapshot written by RecordingTransport."""
    path = Path(path) if path else machine_state_json()
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def resolve(
    address: Optional[str] = None,
    saved_path: Optional[Path] = None,
    allow_live: bool = True,
) -> Tuple[dict, str]:
    """Return (state, source label) using the shared fallback chain.

    1. live machine at ``address`` (or the one in .env.hardware)
    2. live machine at the address recorded in the saved snapshot
    3. the saved snapshot's contents
    4. an empty four-slot machine
    """
    from science_jubilee import trace as trace_mod

    sec = trace_mod.session().section("Machine state", reset=True)
    tried: set[str] = set()

    if not allow_live:
        sec.skipped("live machine", "live query disabled")
    else:
        hw_address = address or read_env_address()
        if not hw_address:
            sec.failed("live machine", "no JUBILEE_ADDRESS with transport=hardware")
        else:
            tried.add(hw_address)
            live = query_live(hw_address)
            if live is not None:
                sec.ok("live machine", hw_address)
                return live, f"live ({hw_address})"
            sec.failed("live machine", f"{hw_address} did not answer")

    saved = load_saved(saved_path)

    if allow_live and saved and saved.get("address") not in tried:
        saved_address = saved.get("address")
        if saved_address:
            live = query_live(saved_address)
            if live is not None:
                sec.ok("live machine — address from snapshot", saved_address)
                return live, f"live ({saved_address})"
            sec.failed(
                "live machine — address from snapshot",
                f"{saved_address} did not answer",
            )

    if saved:
        source = str(saved_path or machine_state_json())
        sec.ok("saved snapshot", source)
        return saved, source

    sec.failed("saved snapshot", str(saved_path or machine_state_json()))
    return empty_state(), "empty machine"
