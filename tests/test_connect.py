def test_connect(motion):
    """Single connection test that works for both simulation and hardware using the pytest-provided fixture."""
    assert motion.transport.connect() is True
