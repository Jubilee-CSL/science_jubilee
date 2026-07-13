import logging

import pytest


@pytest.mark.secondary
def test_print_current_positions(motion, capsys):
    pos = motion.get_positions()
    assert isinstance(pos, dict), "Positions should be a dict"

    letters = motion.get_available_axes() or []
    ordered = [(l, pos.get(l)) for l in letters] if letters else sorted(pos.items())

    logger = logging.getLogger(__name__)
    print("Positions:")
    logger.info("Positions:")
    for l, v in ordered:
        if v is None:
            line = f"  {l}: (unknown)"
        else:
            try:
                line = f"  {l}: {float(v):.3f}"
            except Exception:
                line = f"  {l}: {v}"
        print(line)
        logger.info(line)

    captured = capsys.readouterr()
    if not ordered:
        print("  (no positions available)")
        logger.info("  (no positions available)")
        captured = capsys.readouterr()
    assert "Positions:" in captured.out
