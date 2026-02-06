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
    root = Path(__file__).resolve().parent.parent
    src_path = root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from science_jubilee.hal.transport.http import HTTPTransport
    from science_jubilee.hal.motion_driver import MotionDriver

    addr = os.getenv("JUBILEE_ADDRESS")
    transport = HTTPTransport(host=addr)
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
