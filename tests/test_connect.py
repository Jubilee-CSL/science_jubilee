def test_connect(machine):
    """Single connection test that works for both simulation and hardware using the pytest-provided fixture."""
    assert machine.transport.connect() is True
