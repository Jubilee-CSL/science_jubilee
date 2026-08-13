from pathlib import Path


def jubilee_dir() -> Path:
    """Return the science_jubilee repo root.

    Works for editable installs (returns the checked-out repo root).
    For wheel installs, returns the directory containing the installed package.
    """
    # src/science_jubilee/_paths.py → parents: [0] science_jubilee/, [1] src/, [2] repo root
    return Path(__file__).parents[2]
