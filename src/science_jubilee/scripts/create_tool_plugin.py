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
import warnings
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
    # strip leading "tool_" then CamelCase the remaining name_org segments
    return "".join(p.capitalize() for p in tool_key.removeprefix("tool_").split("_"))


def _make_names(tool_key: str) -> tuple[str, str]:
    """Return (pkg, dist); tool_key is already in tool_name_org format."""
    return tool_key, tool_key.replace("_", "-")


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

Fill in the parking-post coordinates in the `.g.template` files under `templates/`,
then upload `tpre{{N}}.g`, `tpost{{N}}.g`, and `tfree{{N}}.g` to `0:/sys/` on the Duet.

## Usage

```python
from science_jubilee.machine_session import MachineSession

session = MachineSession.from_env(".env.hardware")
tool = session.tool_changer.get_tool("{tool_key}")
tool.run(session.deck_navigator)
```

## Hardware

<!-- TODO: add BOM, STL links, assembly notes -->

## Conventions

- Console scripts registered under `[project.scripts]` should be prefixed with
  the tool key (e.g. `{tool_key}_calibrate`) so multiple installed plugins never
  collide on a name.
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


def _twin_json(tool_key: str, display: str) -> str:
    """Digital-twin manifest — overrides only, everything else is auto-derived.

    Park positions and offsets are deliberately absent: they live in the tool's
    tpre/tpost/tfree macros and nowhere else.
    """
    return f"""\
{{
    "tool_key": "{tool_key}",
    "display_name": "{display}",

    "_comment_assets": "Paths are relative to this twin_assets/ directory. Name the tool body tool.blend and leave these null.",
    "blend": null,
    "park_post_blend": null,

    "_comment_aliases": "Extra names the Duet may report for this tool; matching is case- and separator-insensitive.",
    "aliases": []
}}
"""


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------


def scaffold(
    tool_key: str, display: str, output_dir: Path, *, force: bool = False
) -> Path:
    pkg, dist = _make_names(tool_key)
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
    twin_assets = root / "twin_assets"
    twin_assets.mkdir()
    (twin_assets / "twin.json").write_text(_twin_json(tool_key, display))

    # Tests
    (root / "tests" / "__init__.py").write_text("")
    (root / "tests" / "test_tool.py").write_text(_test_py(tool_key, pkg))

    # Project files
    (root / "pyproject.toml").write_text(_pyproject(tool_key, pkg, dist, display))
    (root / "README.md").write_text(_readme(tool_key, dist, pkg, display))
    (root / ".gitignore").write_text(_gitignore())

    _CALIB_SRC = Path(__file__).parent.parent / "calibration"
    templates_src = _CALIB_SRC / "templates"

    tmpl_out = root / "templates"
    tmpl_out.mkdir()

    # Zeroed macros so the tool has a real slot from the start; the calibration
    # notebook overwrites them with measured coordinates.
    try:
        from science_jubilee.calibration.tool_gfiles import generate_tool_gfiles

        generate_tool_gfiles(
            tool_number=0,
            x_park=0.0,
            y_park=0.0,
            y_clear=0.0,
            output_dir=tmpl_out,
            print_output=False,
        )
    except Exception as exc:
        warnings.warn(f"Could not render tool macros: {exc}")

    wedge = templates_src / "wedge_plate.blend"
    if wedge.exists():
        shutil.copy(wedge, tmpl_out / "wedge_plate.blend")
    else:
        warnings.warn(f"Wedge plate asset not found, skipping: {wedge}")

    park_post = templates_src / "park_post_47.blend"
    if park_post.exists():
        shutil.copy(park_post, tmpl_out / "park_post_47.blend")
    else:
        warnings.warn(f"Park post asset not found, skipping: {park_post}")

    calib_out = root / "calibration"
    calib_out.mkdir()

    alignment_nb = _CALIB_SRC / "ToolAlignmentXY.ipynb"
    if alignment_nb.exists():
        shutil.copy(alignment_nb, calib_out / "ToolAlignmentXY.ipynb")
    else:
        warnings.warn(f"Calibration notebook not found, skipping: {alignment_nb}")

    parking_nb = _CALIB_SRC / "SetToolParkingPositions.ipynb"
    if parking_nb.exists():
        shutil.copy(parking_nb, calib_out / "SetToolParkingPositions.ipynb")
    else:
        warnings.warn(f"Calibration notebook not found, skipping: {parking_nb}")

    for name in ("CalibrationControlPanel.py", "CalibrationJoystick.py"):
        src_f = _CALIB_SRC / name
        if src_f.exists():
            shutil.copy(src_f, calib_out / name)
        else:
            warnings.warn(f"Calibration helper not found, skipping: {src_f}")

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
    parser.add_argument("--key", help="TOOL_KEY (e.g. tool_fluo_csl)")
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
        "Tool key (lowercase, underscores, max 15 chars, e.g. tool_fluo_csl)",
        validator=_validate_key,
    )
    _validate_key(tool_key)  # also validate if passed via --key

    display = args.name or _prompt(
        "Display name",
        default=" ".join(p.capitalize() for p in tool_key.split("_")),
    )

    output_dir = Path(args.out).expanduser().resolve()

    root = scaffold(tool_key, display, output_dir, force=args.force)

    pkg, dist = _make_names(tool_key)

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
    print("  # then edit src/ and fill in README.md")
