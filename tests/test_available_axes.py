import logging
import pytest


logger = logging.getLogger(__name__)

@pytest.mark.secondary
def test_available_axes(motion, jubilee_env):
    letters = motion.get_available_axes()

    assert isinstance(letters, list) and len(letters) > 0, "Expected non-empty axes list"
    assert all(isinstance(l, str) and len(l) == 1 and l.isalpha() and l.upper() == l for l in letters), (
        f"Axes must be single uppercase letters, got: {letters}"
    )

    if jubilee_env == "mock":
        logger.info("Mock simulation mode detected; axes=%s", letters)
        assert letters[:4] == ["X", "Y", "Z", "U"], f"Unexpected mock axes list: {letters}"
    else:
        logger.info("Hardware mode detected; axes=%s", letters)
        assert "X" in letters and "Y" in letters, f"Hardware axes should include X and Y, got: {letters}"
