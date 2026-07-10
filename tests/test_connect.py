import pytest


@pytest.mark.primary
def test_connect(transport):
    """Connection test operates at the transport level; no driver needed."""
    assert transport.connect() is True
