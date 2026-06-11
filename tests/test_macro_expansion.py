"""Tests for RecordingTransport macro expansion.

All tests use the real firmware/sys/ and firmware/macro/ directories so the
logged G-code matches what would actually be executed on hardware.

Log files are written to <repo_root>/gcode_logs/ and named after the test
function so they persist after the run and can be inspected.
"""

import pytest
from pathlib import Path

from science_jubilee.hal.transport.mock import MockTransport
from science_jubilee.hal.transport.recording import RecordingTransport

# Persistent log output directory - repo_root/gcode_logs/
# This file lives at tests/test_macro_expansion.py, so parent.parent = repo root.
_REPO_ROOT = Path(__file__).parent.parent
_LOG_DIR = _REPO_ROOT / "gcode_logs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _firmware_dirs() -> tuple[Path, Path]:
    """Return the real firmware sys and macro directories."""
    return _REPO_ROOT / "firmware" / "sys", _REPO_ROOT / "firmware" / "macro"


def _make_recording(name: str, mock: MockTransport, sys_dir: Path, macro_dir: Path) -> tuple[RecordingTransport, Path]:
    """Create a RecordingTransport that writes to gcode_logs/<name>.gcode."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _LOG_DIR / f"{name}.gcode"
    rec = RecordingTransport(mock, log_path=str(log), sys_dir=sys_dir, macro_dir=macro_dir)
    return rec, log


def _log_content(log: Path) -> str:
    return log.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: T{n} expansion via send_gcode
# ---------------------------------------------------------------------------

def test_tool_change_from_no_active_tool_expands_tpre_and_tpost(request):
    """T0 with no active tool: no tfree, tpre0 + tpost0 are expanded."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("T0")

    content = _log_content(log)
    assert "; === tool change: T0 ===" in content
    # tpre0 content (real firmware: G0 X350.5 Y270 F20000)
    assert "G0 X350.5 Y270 F20000" in content
    # tpost0 content (real firmware: G53 G1 X290.5 F6000)
    assert "G53 G1 X290.5 F6000" in content
    # tool_lock.g (nested M98) content
    assert "G1 U80 F1500" in content
    # no tfree since no prior active tool
    assert "tfree0.g" not in content


def test_tool_change_with_active_tool_expands_tfree_then_tpre_tpost(request):
    """T1 with tool 0 active: tfree0, tpre1, tpost1 all expanded."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    # Pre-select tool 0 directly on mock (bypasses recording intentionally for setup)
    mock.active_tool_index = 0
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("T1")

    content = _log_content(log)
    assert "; === tool change: T1 ===" in content
    # tfree0 content (freeing tool 0)
    assert "; tfree0.g" in content
    assert "G1 Z2" in content
    # tpre1 content (real firmware: G0 X270 Y270 F20000)
    assert "G0 X270 Y270 F20000" in content
    # tpost1 content (real firmware: G53 G1 X210 F6000)
    assert "G53 G1 X210 F6000" in content
    # nested tool_lock.g
    assert "G1 U80 F1500" in content


def test_park_tool_expands_tfree_for_active_tool(request):
    """T-1 with tool 0 active: tfree0 is expanded, no tpre/tpost."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    mock.active_tool_index = 0
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("T-1")

    content = _log_content(log)
    assert "; === park tool: T-1 ===" in content
    assert "; tfree0.g" in content
    assert "G1 Z2" in content
    # tpre and tpost should not be present
    assert "tpre" not in content
    assert "tpost" not in content


def test_park_tool_with_no_active_tool_logs_header_only(request):
    """T-1 with no active tool: just the park header, no macro content."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("T-1")

    content = _log_content(log)
    assert "; === park tool: T-1 ===" in content
    # No macro content - G1 Z2 only appears inside tfree macros
    assert "G1 Z2" not in content


# ---------------------------------------------------------------------------
# Tests: select_tool / park_tool bypass fix
# ---------------------------------------------------------------------------

def test_select_tool_produces_same_expansion_as_send_gcode(request):
    """select_tool(0) must log the same macro expansion as send_gcode('T0')."""
    sys_dir, macro_dir = _firmware_dirs()

    # Reference: expansion via send_gcode
    rec_ref, log_ref = _make_recording(request.node.name + "_ref", MockTransport(), sys_dir, macro_dir)
    rec_ref.send_gcode("T0")
    ref_content = _log_content(log_ref)

    # Under test: expansion via select_tool
    rec_sel, log_sel = _make_recording(request.node.name + "_sel", MockTransport(), sys_dir, macro_dir)
    rec_sel.select_tool(0)
    sel_content = _log_content(log_sel)

    # Both logs should contain identical macro expansion content
    assert "; === tool change: T0 ===" in sel_content
    assert "G0 X350.5 Y270 F20000" in sel_content
    assert "G1 U80 F1500" in sel_content
    # Expansion content matches reference
    assert ref_content == sel_content


def test_park_tool_method_logs_tfree_expansion(request):
    """park_tool() must log the tfree expansion the same as send_gcode('T-1')."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    mock.active_tool_index = 0
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.park_tool()

    content = _log_content(log)
    assert "; === park tool: T-1 ===" in content
    assert "; tfree0.g" in content
    assert "G1 Z2" in content


# ---------------------------------------------------------------------------
# Tests: recursive M98 expansion
# ---------------------------------------------------------------------------

def test_nested_m98_in_macro_is_expanded(request):
    """M98 calls inside an expanded tpost file are themselves expanded."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("T0")

    content = _log_content(log)
    # tpost0.g has M98 P"/macros/tool_lock.g" which should be expanded
    assert '; M98 P"/macros/tool_lock.g"' in content
    # The content of tool_lock.g should appear
    assert "G1 U80 F1500" in content


def test_standalone_m98_send_gcode_expands_macro(request):
    """Directly send_gcode an M98 command: the macro content appears in the log."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode('M98 P"nonexistent_macro.g"')

    content = _log_content(log)
    # The M98 itself is logged as a comment
    assert '; M98 P"nonexistent_macro.g"' in content
    # File does not exist -> fallback message
    assert "(macro not found: nonexistent_macro.g)" in content


# ---------------------------------------------------------------------------
# Tests: missing macro file fallback
# ---------------------------------------------------------------------------

def test_missing_tpre_logs_not_found_comment(request):
    """T99 with no tpre99.g in sys_dir logs a '(macro not found:...)' comment."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("T99")

    content = _log_content(log)
    assert "; === tool change: T99 ===" in content
    assert "(macro not found: tpre99.g)" in content
    assert "(macro not found: tpost99.g)" in content


def test_missing_tfree_logs_not_found_comment(request):
    """T0 when tool 99 is active (no tfree99.g): logs not-found comment, continues."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    mock.active_tool_index = 99
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("T0")

    content = _log_content(log)
    assert "(macro not found: tfree99.g)" in content
    # tpre0 still expands normally with real firmware content
    assert "G0 X350.5 Y270 F20000" in content


def test_no_macro_dirs_does_not_raise(request):
    """With sys_dir=None and macro_dir=None, T{n} logs header and not-found comments."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _LOG_DIR / f"{request.node.name}.gcode"
    mock = MockTransport()
    rec = RecordingTransport(mock, log_path=str(log), sys_dir=None, macro_dir=None)

    rec.send_gcode("T0")

    content = _log_content(log)
    assert "; === tool change: T0 ===" in content
    assert "(macro not found: tpre0.g)" in content
    assert "(macro not found: tpost0.g)" in content


# ---------------------------------------------------------------------------
# Tests: regular G-code is unaffected
# ---------------------------------------------------------------------------

def test_regular_gcode_is_logged_unchanged(request):
    """Non-tool-change commands are logged verbatim."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.send_gcode("G28 X")
    rec.send_gcode("G0 X100 Y50 F6000")

    content = _log_content(log)
    assert "G28 X" in content
    assert "G0 X100 Y50 F6000" in content


def test_select_tool_updates_mock_active_tool(request):
    """After select_tool, the mock's active tool index is updated correctly."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    assert mock.active_tool_index == -1
    rec.select_tool(0)
    assert mock.active_tool_index == 0


def test_park_tool_resets_mock_active_tool(request):
    """After park_tool, the mock's active tool index is -1."""
    sys_dir, macro_dir = _firmware_dirs()
    mock = MockTransport()
    mock.active_tool_index = 0
    rec, log = _make_recording(request.node.name, mock, sys_dir, macro_dir)

    rec.park_tool()
    assert mock.active_tool_index == -1
