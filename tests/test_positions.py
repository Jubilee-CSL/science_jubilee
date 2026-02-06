import logging
import pytest


@pytest.mark.secondary
def test_print_current_positions(motion, capsys):
    """Pretty-print current axis positions using transport convenience.

    This test exercises driver.transport.get_positions() and prints a
    human-readable summary in firmware axis order when available.
    """
    driver = motion

    # Retrieve current positions from transport
    pos = driver.transport.get_positions() or {}
    assert isinstance(pos, dict), "Positions should be a dict"

    # Determine preferred ordering based on available axes
    letters = driver.get_available_axes() or []
    ordered = [(l, pos.get(l)) for l in letters] if letters else sorted(pos.items())

    # Use logging (visible with live logging) and print (for capsys assertion)
    logger = logging.getLogger(__name__)
    print("Positions:")
    logger.info("Positions:")
    for l, v in ordered:
        if v is None:
            line = f"  {l}: (unknown)"
            print(line)
            logger.info(line)
        else:
            try:
                line = f"  {l}: {float(v):.3f}"
                print(line)
                logger.info(line)
            except Exception:
                line = f"  {l}: {v}"
                print(line)
                logger.info(line)

    # Basic sanity: ensure something was printed
    captured = capsys.readouterr()
    # If no axes/positions, still provide a hint
    if not ordered:
        print("  (no positions available)")
        logger.info("  (no positions available)")
        captured = capsys.readouterr()
    assert "Positions:" in captured.out
