import json
import logging
import pytest


@pytest.mark.secondary
def test_machine_summary_print(motion, capsys):
    """Print machine summary as JSON and pretty string.

    Ensures BaseTransport.get_machine_summary() returns a dict
    and BaseTransport.format_machine_summary() prints a readable summary.
    """
    driver = motion

    # JSON dict summary
    summary = driver.transport.get_machine_summary()
    assert isinstance(summary, dict), "Summary should be a dict"

    # Print JSON summary (pretty) with logging for live view
    logger = logging.getLogger(__name__)
    print("Summary (JSON):")
    logger.info("Summary (JSON):")
    json_text = json.dumps(summary, indent=2, sort_keys=True)
    print(json_text)
    logger.info(json_text)

    # Pretty string summary
    pretty = driver.transport.format_machine_summary()
    assert isinstance(pretty, str)
    print("Summary (pretty):")
    logger.info("Summary (pretty):")
    print(pretty)
    logger.info(pretty)

    captured = capsys.readouterr()
    assert "Summary (JSON):" in captured.out
    assert "Summary (pretty):" in captured.out
