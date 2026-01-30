def test_home_xyu_and_z(machine):
    m = machine
    # Home XYU using Machine helper (non-interactive)
    # Ensure any active tool is parked to avoid homing interference on hardware
    m.park_tool()
    m.home_xyu()
    # Home Z via high-level method
    m.home_z(deck_clearance=True)

    # Query homing status via Machine helper (uses BaseTransport)
    homed = m.get_axes_homed()

    # Ensure at least X, Y, Z, U are homed
    assert all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"
if __name__ == "__main__":
    # Manual hardware run: execute homing sequence and report status
    # Construct Machine from environment for CLI runs
    import os
    from science_jubilee.Machine import Machine
    addr = os.getenv("JUBILEE_ADDRESS")
    sim_env = os.getenv("JUBILEE_SIM", "1").strip().lower()
    sim = sim_env in ("1", "true", "yes")
    m = Machine(address=addr, simulated=sim)
    # Home sequence
    m.park_tool()
    m.home_xyu()
    m.home_z(deck_clearance=True)
    homed = m.get_axes_homed()
    assert all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"