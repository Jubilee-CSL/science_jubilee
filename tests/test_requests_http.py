import os
import time
from pathlib import Path
import logging
from science_jubilee.utils.env import ensure_env_from_file

import pytest
import requests
logger = logging.getLogger(__name__)


@pytest.mark.primary

def test_requests_send_gcode_m115():
    """Smoke test that raw HTTP requests can reach the printer and return a plausible reply.
    Uses /machine/code when available; falls back to rr_gcode/rr_reply.
    Skips when simulation is selected or address is missing.
    """
    # Honor pytest-selected environment (via conftest.py)
    sim_env = os.getenv("JUBILEE_SIM", "1").strip().lower()
    if sim_env in ("1", "true", "yes"):
        logger.info("Skipping HTTP test: simulation environment detected (JUBILEE_SIM=%s)", sim_env)
        pytest.skip("requests-based HTTP test is hardware-only")

    # Try to obtain address from environment; if missing, attempt to load .env.hardware
    root = Path(__file__).resolve().parent.parent
    address = ensure_env_from_file("JUBILEE_ADDRESS", root / ".env.hardware")
    if not address:
        pytest.skip("JUBILEE_ADDRESS not set")

    text = None

    # Primary path: /machine/code (RRF HTTP API)
    logger.info("Testing HTTP /machine/code at http://%s", address)
    try:
        r = requests.post(f"http://{address}/machine/code", data="M115", timeout=5)
        if r.ok:
            text = r.text
            # Some gateways may return empty body; handle below with fallback
            if text and "rejected" in text.lower():
                text = None
            else:
                logger.info("/machine/code returned ok; length=%d", len(text or ""))
    except Exception:
        text = None

    # Fallback path: rr_gcode/rr_reply sequence
    if not text:
        logger.info("Falling back to rr_gcode/rr_reply sequence")
        try:
            model = requests.get(f"http://{address}/rr_model?key=seqs", timeout=5).json()
            prev_reply = model.get("result", {}).get("reply")
            # issue M115
            _ = requests.get(f"http://{address}/rr_gcode?gcode=M115", timeout=5)

            start = time.time()
            while time.time() - start < 5:
                try:
                    new_model = requests.get(f"http://{address}/rr_model?key=seqs", timeout=5).json()
                    new_reply = new_model.get("result", {}).get("reply")
                    if new_reply != prev_reply:
                        rep = requests.get(f"http://{address}/rr_reply", timeout=5)
                        if rep.ok:
                            text = rep.text
                            logger.info("rr_reply returned ok; length=%d", len(text or ""))
                        break
                except Exception:
                    pass
                time.sleep(0.1)
        except Exception:
            pass

    logger.info("M115 response (truncated 120 chars): %r", (text or "").strip()[:120])
    assert text is not None and text.strip() != "", "No response text returned from M115"
    upper = text.upper()
    assert ("FIRMWARE" in upper) or ("REPRAPFIRMWARE" in upper), f"Unexpected M115 reply: {text!r}"
