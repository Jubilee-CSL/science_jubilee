"""Scaffold a new science-jubilee tool plugin repository.

Usage
-----
    create-tool-plugin
    create-tool-plugin --key my_tool --name "My Tool" --out ~/repos
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_KEY_LEN = 15

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_key(key: str) -> str:
    if not _KEY_REGEX.match(key):
        raise ValueError(
            f"must match {_KEY_REGEX.pattern} "
            "(lowercase letters, digits, underscores; start with a letter)"
        )
    if len(key) > _MAX_KEY_LEN:
        raise ValueError(f"exceeds {_MAX_KEY_LEN} characters (RepRapFirmware limit)")
    return key


def _to_class_name(tool_key: str) -> str:
    return "".join(p.capitalize() for p in tool_key.split("_")) + "Tool"


def _prompt(message: str, default: str | None = None, validator=None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{message}{suffix}: ").strip()
        value = raw or default or ""
        if not value:
            print("  This field is required.")
            continue
        if validator:
            try:
                value = validator(value)
            except ValueError as exc:
                print(f"  Invalid: {exc}")
                continue
        return value


# ---------------------------------------------------------------------------
# File templates
# ---------------------------------------------------------------------------


def _pyproject(tool_key: str, pkg: str, dist: str, display: str) -> str:
    return f"""\
[build-system]
requires = ["setuptools>=42", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{dist}"
version = "0.1.0"
description = "{display} tool plugin for science-jubilee"
requires-python = ">=3.10"
dependencies = ["science-jubilee>=0.0.0"]

[project.entry-points."science_jubilee.tools"]
{tool_key} = "{pkg}.tool:{_to_class_name(tool_key)}"

[project.entry-points."science_jubilee.tools.mocks"]
{tool_key} = "{pkg}.mock:{_to_class_name(tool_key)}Mock"

[project.entry-points."science_jubilee.tools.configs"]
{tool_key} = "{pkg}.configs:__path__"

[project.entry-points."science_jubilee.tools.twin_assets"]
{tool_key} = "{pkg}._paths:get_twin_assets_dir"

[tool.setuptools.packages.find]
where = ["src"]
"""


def _paths_py(pkg: str) -> str:
    return """\
from pathlib import Path


def get_twin_assets_dir() -> Path:
    # twin_assets/ lives at the repo root, not inside the Python package
    return Path(__file__).parent.parent.parent / "twin_assets"
"""


def _tool_py(tool_key: str, pkg: str) -> str:
    cls = _to_class_name(tool_key)
    return f"""\
from dataclasses import dataclass
from typing import ClassVar

from science_jubilee.tools.Tool import Tool, requires_active_tool


@dataclass(slots=True, repr=False)
class {cls}(Tool):
    TOOL_KEY: ClassVar[str] = "{tool_key}"

    @requires_active_tool
    def run(self, nav) -> None:
        \"\"\"TODO: implement tool action.\"\"\"
        raise NotImplementedError
"""


def _mock_py(tool_key: str, pkg: str) -> str:
    cls = _to_class_name(tool_key)
    return f"""\
from dataclasses import dataclass
from typing import ClassVar

from {pkg}.tool import {cls}


@dataclass(slots=True, repr=False)
class {cls}Mock({cls}):
    TOOL_KEY: ClassVar[str] = "{tool_key}"

    def run(self, nav) -> None:
        pass
"""


def _init_py(tool_key: str, pkg: str) -> str:
    cls = _to_class_name(tool_key)
    return f"""\
from {pkg}.tool import {cls}
from {pkg}.mock import {cls}Mock

__all__ = ["{cls}", "{cls}Mock"]
"""


def _test_py(tool_key: str, pkg: str) -> str:
    cls = _to_class_name(tool_key)
    return f"""\
from science_jubilee.tools.Tool import Tool
from {pkg}.tool import {cls}
from {pkg}.mock import {cls}Mock


def test_tool_key():
    assert {cls}.TOOL_KEY == "{tool_key}"


def test_is_tool_subclass():
    assert issubclass({cls}, Tool)


def test_mock_key_matches():
    assert {cls}Mock.TOOL_KEY == {cls}.TOOL_KEY
"""


def _setup_duet_py(tool_key: str) -> str:
    return f"""\
\"\"\"Generate and upload tpre/tpost/tfree firmware files for {tool_key}.

Edit the values below, then run:
    python setup_duet.py
\"\"\"

from science_jubilee.calibration.tool_gfiles import generate_tool_gfiles

# ---- fill these in after physically calibrating the parking post ----
TOOL_NUMBER = 0       # slot index in config.g (P0, P1, ...)
X_PARK      = 0.0    # X coordinate of the parking post
Y_PARK      = 0.0    # Y coordinate (tool locked / fully docked)
Y_CLEAR     = 0.0    # Y coordinate safely clear of all parking posts

# Optional: pass transport="<duet-ip>" to upload directly instead of printing
generate_tool_gfiles(
    tool_number=TOOL_NUMBER,
    x_park=X_PARK,
    y_park=Y_PARK,
    y_clear=Y_CLEAR,
    # transport="192.168.1.2",
)

print()
print("Next steps:")
print(f"  1. Upload tpre{{TOOL_NUMBER}}.g / tpost{{TOOL_NUMBER}}.g / tfree{{TOOL_NUMBER}}.g to 0:/sys/ on the Duet.")
print(f"  2. Run Tool Alignment XY calibration to get X/Y/Z offsets.")
print(f'  3. Add to toffsets.g:  G10 P{{TOOL_NUMBER}} X<X> Y<Y> Z<Z>  ; {tool_key}')
print(f'  4. Add to config.g:    M563 P{{TOOL_NUMBER}} S"{tool_key}"')
print( "  5. M999 to restart the Duet.")
"""


def _readme(tool_key: str, dist: str, pkg: str, display: str) -> str:
    cls = _to_class_name(tool_key)
    return f"""\
# {display}

A [science-jubilee](https://github.com/machineagency/science-jubilee) tool plugin
for the `{tool_key}` tool.

## Install

```bash
pip install git+https://github.com/<owner>/{dist}
```

After installation, `ToolChanger` discovers `{cls}` automatically — no changes
to the science-jubilee source are needed.

## Duet firmware setup (once per machine)

Edit and run `setup_duet.py` to generate the parking macro files, then follow
the printed instructions to complete the firmware configuration.

## Usage

```python
from science_jubilee.machine_session import MachineSession

session = MachineSession.from_env(".env.hardware")
tool = session.tool_changer.get_tool("{tool_key}")
tool.run(session.deck_navigator)
```

## Hardware

<!-- TODO: add BOM, STL links, assembly notes -->
"""


def _gitignore() -> str:
    return """\
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
"""


def _configs_json(tool_key: str) -> str:
    return f'{{\n    "tool_key": "{tool_key}"\n}}\n'


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------


def scaffold(
    tool_key: str, display: str, output_dir: Path, *, force: bool = False
) -> Path:
    pkg = f"{tool_key}_tool"
    dist = tool_key.replace("_", "-") + "-tool"
    root = output_dir / dist
    src = root / "src" / pkg

    if root.exists():
        if not force:
            print(f"Directory {root} already exists — use --force to overwrite.")
            sys.exit(1)
        shutil.rmtree(root)
    zip_path_existing = output_dir / (dist + ".zip")
    if zip_path_existing.exists() and force:
        zip_path_existing.unlink()

    # directory tree
    for d in [
        src,
        src / "configs",
        root / "tests",
    ]:
        d.mkdir(parents=True)

    # Python source
    (src / "__init__.py").write_text(_init_py(tool_key, pkg))
    (src / "tool.py").write_text(_tool_py(tool_key, pkg))
    (src / "mock.py").write_text(_mock_py(tool_key, pkg))
    (src / "_paths.py").write_text(_paths_py(pkg))
    (src / "configs" / "__init__.py").write_text("")
    (src / "configs" / f"{tool_key}.json").write_text(_configs_json(tool_key))

    # twin_assets at repo root — heavy 3D files live here, not inside the Python package
    (root / "twin_assets").mkdir()

    # Tests
    (root / "tests" / "__init__.py").write_text("")
    (root / "tests" / "test_tool.py").write_text(_test_py(tool_key, pkg))

    # Project files
    (root / "pyproject.toml").write_text(_pyproject(tool_key, pkg, dist, display))
    (root / "README.md").write_text(_readme(tool_key, dist, pkg, display))
    (root / ".gitignore").write_text(_gitignore())
    (root / "setup_duet.py").write_text(_setup_duet_py(tool_key))

    # Copy Jinja2 firmware templates alongside setup_duet.py for reference
    templates_src = Path(__file__).parent.parent / "calibration" / "templates"
    for name in ("tpre.g", "tpost.g", "tfree.g"):
        src_t = templates_src / name
        if src_t.exists():
            shutil.copy(src_t, root / f"{name}.template")

    _CALIB_SRC = Path(__file__).parent.parent / "calibration"

    # Copy the XY alignment calibration notebook
    alignment_nb = _CALIB_SRC / "ToolAlignmentXY.ipynb"
    if alignment_nb.exists():
        shutil.copy(alignment_nb, root / "ToolAlignmentXY.ipynb")

    # Copy the parking-position setup notebook
    parking_nb = _CALIB_SRC / "SetToolParkingPositions.ipynb"
    if parking_nb.exists():
        shutil.copy(parking_nb, root / "SetToolParkingPositions.ipynb")

    # Copy calibration helpers the notebooks depend on
    calib_out = root / "calibration"
    calib_out.mkdir()
    for name in ("CalibrationControlPanel.py", "CalibrationJoystick.py"):
        src_f = _CALIB_SRC / name
        if src_f.exists():
            shutil.copy(src_f, calib_out / name)

    # zip contents directly so extracting doesn't create a double-nested folder
    zip_path = output_dir / dist
    shutil.make_archive(str(zip_path), "zip", root_dir=root, base_dir=".")
    shutil.rmtree(root)
    return zip_path.with_suffix(".zip")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scaffold a science-jubilee tool plugin repo."
    )
    parser.add_argument("--key", help="TOOL_KEY (e.g. csl_fluo)")
    parser.add_argument("--name", help='Display name (e.g. "Fluorescence Imager")')
    parser.add_argument(
        "--out", default=".", help="Parent directory for the new repo (default: .)"
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite an existing plugin directory and zip.",
    )
    args = parser.parse_args()

    print("science-jubilee tool plugin scaffolder")
    print("--------------------------------------")

    tool_key = args.key or _prompt(
        "Tool key (lowercase, underscores, max 15 chars, e.g. csl_fluo)",
        validator=_validate_key,
    )
    _validate_key(tool_key)  # also validate if passed via --key

    display = args.name or _prompt(
        "Display name",
        default=" ".join(p.capitalize() for p in tool_key.split("_")),
    )

    output_dir = Path(args.out).expanduser().resolve()

    root = scaffold(tool_key, display, output_dir, force=args.force)

    pkg = f"{tool_key}_tool"
    dist = tool_key.replace("_", "-") + "-tool"

    print(f"\nCreated {root}")
    print(f"  TOOL_KEY   : {tool_key}")
    print(f"  Package    : {pkg}")
    print(f"  Dist name  : {dist}")
    print(f"  Class name : {_to_class_name(tool_key)}")
    print()
    print("Next:")
    print(f"  unzip {root.name}")
    print()
    print("  # plain pip:")
    print(f"  cd {dist}")
    print("  pip install -e .")
    print()
    print(
        "  # pixi (run from the directory that contains pixi.toml, not inside the plugin):"
    )
    print(f'  pixi add --pypi --editable "{dist} @ ./{dist}"')
    print()
    print("  pytest")
    print("  # then edit src/, run setup_duet.py, and fill in README.md")
