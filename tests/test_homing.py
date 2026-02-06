import pytest

@pytest.mark.invasive
def test_home_xyu_and_z(motion):
    driver = motion
    # Ensure any active tool is parked to avoid homing interference on hardware
    try:
        driver.transport.send_gcode("T-1")
    except Exception:
        pass

    # Home XYU (non-interactive); Z requires deck-clear caching
    driver.home("x")
    driver.home("y")
    driver.home("u")
    driver.learn_deck_clearance(True)
    driver.home("z")

    # Query homing status via transport convenience method
    homed = driver.transport.get_axes_homed()

    # Ensure at least X, Y, Z, U are homed
    assert homed and all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"
if __name__ == "__main__":
    # Manual hardware run: execute homing sequence and report status.
    # Add src to sys.path so imports work when running this file directly.
    import os
    import sys
    from pathlib import Path
    from science_jubilee.utils.env import ensure_env_from_file
    
    # Load .env.hardware if JUBILEE_ADDRESS is not already set
    def _load_env_file(env_file: Path):
        if not env_file.exists():
            return
        try:
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
                    if key not in os.environ:
                        os.environ[key] = value
        except Exception:
            pass

    root = Path(__file__).resolve().parent.parent
    src_path = root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from science_jubilee.hal.transport.http import HTTPTransport
    from science_jubilee.hal.motion_driver import MotionDriver

    # Attempt to load hardware env file to obtain JUBILEE_ADDRESS
    addr = ensure_env_from_file("JUBILEE_ADDRESS", root / ".env.hardware")
    if not addr:
        raise SystemExit("JUBILEE_ADDRESS is not set. Please create .env.hardware with JUBILEE_ADDRESS=<ip> or set the environment variable.")
    transport = HTTPTransport(address=addr)
    driver = MotionDriver(transport)

    # Learn deck clearance via transport (HTTPTransport may prompt the user itself).
    try:
        driver.learn_deck_clearance(driver.transport.deck_is_clear())
    except Exception:
        pass

    # Park tool and perform homing sequence
    try:
        driver.transport.send_gcode("T-1")
    except Exception:
        pass
    
    driver.home("u")
    driver.home("y")
    driver.home("x")
    driver.home("z")

    homed = driver.transport.get_axes_homed()
    assert homed and all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"
