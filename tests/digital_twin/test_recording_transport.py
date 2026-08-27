import pytest

from science_jubilee.hal.transport.mock import MockTransport
from science_jubilee.hal.transport.recording import RecordingTransport


def test_recording_transport_writes_latest_and_run_named_copy(tmp_path, monkeypatch):
    log_dir = tmp_path / "gcode_logs"
    latest = log_dir / "latest.gcode"
    monkeypatch.setenv("JUBILEE_RUN_NAME", "deck_navigation")

    rec = RecordingTransport(MockTransport(), log_path=str(latest))
    rec.send_gcode("G28")

    run_copy = log_dir / "deck_navigation.gcode"
    assert latest.exists()
    assert run_copy.exists()
    assert "G28" in latest.read_text(encoding="utf-8")
    assert "G28" in run_copy.read_text(encoding="utf-8")


def test_recording_transport_uses_pytest_current_test_env(tmp_path, monkeypatch):
    """Copy is named after the test file reported by pytest."""
    monkeypatch.delenv("JUBILEE_RUN_NAME", raising=False)
    monkeypatch.delenv("JUBILEE_GCODE_LOG_COPY", raising=False)
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST", "tests/test_navigation_deck.py::test_move_to_well (call)"
    )
    latest = tmp_path / "gcode_logs" / "latest.gcode"

    rec = RecordingTransport(MockTransport(), log_path=str(latest))
    rec.send_gcode("G28")

    assert (tmp_path / "gcode_logs" / "test_navigation_deck.gcode").exists()


def test_recording_transport_uses_explicit_copy_path_when_set(tmp_path, monkeypatch):
    latest = tmp_path / "gcode_logs" / "latest.gcode"
    copy_path = tmp_path / "gcode_logs" / "custom_run_name.gcode"
    monkeypatch.setenv("JUBILEE_GCODE_LOG_COPY", str(copy_path))

    rec = RecordingTransport(MockTransport(), log_path=str(latest))
    rec.send_gcode("M400")

    assert latest.exists()
    assert copy_path.exists()
    assert "M400" in latest.read_text(encoding="utf-8")
    assert "M400" in copy_path.read_text(encoding="utf-8")


def test_recording_transport_saves_machine_state(tmp_path):
    import json

    latest = tmp_path / "gcode_logs" / "latest.gcode"

    RecordingTransport(MockTransport(), log_path=str(latest))

    state_file = tmp_path / "gcode_logs" / "machine_state.json"
    assert state_file.exists(), "machine_state.json was not written"
    state = json.loads(state_file.read_text())
    for key in ("transport", "positions", "active_tool", "tools", "tool_parks"):
        assert key in state, f"missing key '{key}' in machine_state.json"


def test_http_transport_parse_park_position():
    from science_jubilee.hal.transport.http import HTTPTransport

    tpost = """
; tpost0.g
G90
G53 G1 X290.5 F6000  ; move to pickup
G53 G1 Y338.5 F6000
M98 P"/macros/tool_lock.g"
"""
    result = HTTPTransport._parse_park_position(tpost)
    assert result == pytest.approx([290.5, 338.5, 0.0])


def test_recording_transport_warns_when_summary_fails(tmp_path):
    import warnings
    from unittest.mock import patch

    latest = tmp_path / "gcode_logs" / "latest.gcode"
    inner = MockTransport()

    with patch.object(
        type(inner), "get_machine_summary", side_effect=RuntimeError("boom")
    ):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            RecordingTransport(inner, log_path=str(latest))

    assert caught, "expected a UserWarning when get_machine_summary raises"
    assert any("machine_state" in str(w.message).lower() for w in caught)
