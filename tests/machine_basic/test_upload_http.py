"""Test that HTTPTransport.upload_file / read_file round-trip correctly.

The test uploads a small .g comment file whose content includes the current
ISO timestamp, then reads it back from the Duet and confirms the content
matches exactly.  A cleanup upload (empty file) is attempted afterwards.

Run against real hardware only:

    pytest tests/test_upload_http.py --jubilee-env=hardware

The test is automatically skipped in mock mode or when JUBILEE_ADDRESS is unset.
"""

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# Remote filename used for the round-trip test — won't collide with real sys files
_TEST_REMOTE_NAME = "_test_upload_roundtrip.g"
_TEST_DESTINATION = "sys"


@pytest.fixture
def http_transport():
    """Return a live HTTPTransport, or skip if not in hardware mode."""
    transport_type = os.getenv("JUBILEE_TRANSPORT", "").strip().lower()
    if transport_type != "hardware":
        pytest.skip(
            f"upload round-trip test is hardware-only "
            f"(JUBILEE_TRANSPORT={transport_type!r})"
        )

    address = os.getenv("JUBILEE_ADDRESS", "").strip()
    if not address:
        root = Path(__file__).resolve().parent.parent
        env_file = root / ".env.hardware"
        if env_file.exists():
            from science_jubilee.utils.env import load_env_file

            load_env_file(env_file)
            address = os.getenv("JUBILEE_ADDRESS", "").strip()

    if not address:
        pytest.skip("JUBILEE_ADDRESS not set — cannot run hardware upload test")

    from science_jubilee.hal.transport.http import HTTPTransport

    return HTTPTransport(address=address, deck_clear_provider=lambda: True)


def _make_test_gfile(tmp_dir: Path) -> tuple[Path, str]:
    """Write a dated .g comment file and return (path, expected_content)."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    content = (
        f"; science_jubilee upload round-trip test\n"
        f"; generated: {timestamp}\n"
        f"; This file is safe to delete.\n"
    )
    path = tmp_dir / _TEST_REMOTE_NAME
    path.write_text(content, encoding="utf-8")
    return path, content


@pytest.mark.primary
class TestUploadRoundTrip:
    """Upload a dated .g file and read it back to verify round-trip integrity."""

    def test_upload_and_read_back(self, http_transport):
        """Write a timestamped .g file, upload it, read it back, compare."""
        with tempfile.TemporaryDirectory() as tmp:
            local_path, expected = _make_test_gfile(Path(tmp))
            logger.info("Uploading test file: %s", _TEST_REMOTE_NAME)

            # --- Upload ---------------------------------------------------
            remote_path = http_transport.upload_file(
                local_path,
                destination=_TEST_DESTINATION,
                remote_name=_TEST_REMOTE_NAME,
            )
            assert remote_path.endswith(
                _TEST_REMOTE_NAME
            ), f"upload_file returned unexpected remote path: {remote_path!r}"

            # --- Read back ------------------------------------------------
            logger.info("Reading back: %s", remote_path)
            actual = http_transport.read_file(remote_path)

            # Normalize line endings: Duet returns CRLF, we wrote LF locally
            actual_norm = actual.replace("\r\n", "\n").replace("\r", "\n").strip()
            expected_norm = expected.replace("\r\n", "\n").replace("\r", "\n").strip()

            assert actual_norm == expected_norm, (
                f"Round-trip content mismatch.\n"
                f"Expected:\n{expected_norm}\n"
                f"Got:\n{actual_norm}"
            )

            # --- Verify timestamp is preserved ----------------------------
            timestamp_line = [l for l in expected.splitlines() if "generated:" in l][
                0
            ].strip()
            assert timestamp_line in actual_norm, (
                f"Timestamp line not found in retrieved content.\n"
                f"Expected line: {timestamp_line!r}\n"
                f"Actual content:\n{actual_norm}"
            )

            logger.info("Round-trip test passed for %s", remote_path)

    def test_cleanup_after_upload(self, http_transport):
        """Confirm we can overwrite the test file with an empty one (cleanup).

        This is a best-effort test — if upload succeeds the remote file is
        replaced with a harmless empty comment.
        """
        with tempfile.TemporaryDirectory() as tmp:
            empty_path = Path(tmp) / _TEST_REMOTE_NAME
            empty_path.write_text("; cleanup — safe to delete\n", encoding="utf-8")
            remote_path = http_transport.upload_file(
                empty_path,
                destination=_TEST_DESTINATION,
                remote_name=_TEST_REMOTE_NAME,
            )
            content = http_transport.read_file(remote_path)
            assert "cleanup" in content, (
                "Cleanup upload or read-back failed — "
                f"unexpected content: {content!r}"
            )
