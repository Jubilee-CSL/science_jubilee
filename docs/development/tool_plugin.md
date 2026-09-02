---
title: Writing a Tool Plugin
---

(tool-plugin-guide)=
# Writing a Tool Plugin

This guide covers everything needed to package a new Jubilee tool as a standalone
Python plugin — from naming conventions and repo layout to Duet firmware files and
digital-twin assets.

## Quickstart — scaffolder

The fastest way to start is the included scaffolder, which generates a complete,
testable repo skeleton and zips it up ready to unpack wherever you work:

```bash
create-tool-plugin
# prompts: tool key, display name, output directory
# → produces  <output>/<dist-name>.zip
```

Or non-interactively:

```bash
create-tool-plugin --key csl_fluo --name "Fluorescence Imager" --out ~/repos
```

The zip contains pre-filled `pyproject.toml`, `tool.py`, `mock.py`, tests that
pass immediately, `setup_duet.py` for firmware setup, and reference copies of
the Jinja2 firmware templates.  Unzip, `pip install -e .`, `pytest` — all green.

The rest of this page explains the conventions the scaffolder encodes.

---

## 1. Naming your tool

Every tool has a single canonical name called the **`TOOL_KEY`**.  It must satisfy
all of the following:

| Rule | Reason |
|------|--------|
| Lowercase ASCII letters, digits, and underscores only | RepRapFirmware `M563 S"..."` limit |
| Must start with a letter | Python identifier derivation |
| At most 15 characters | RepRapFirmware `M563 S` string limit |
| Prefix with your org tag if not in the mother repo | Collision avoidance (e.g. `csl_pen`) |

Reserved bare names (mother-repo only): `inoculator`, `camera`, `light`,
`neopixel`, `toolhead_cam`.  External plugins must prefix — e.g. `csl_pen` instead
of `pen`.

### The five naming surfaces

One `TOOL_KEY` gets written in five places, each with its own format:

| Surface | Format | Example |
|---------|--------|---------|
| `TOOL_KEY` class attribute | exact key string | `"csl_fluo"` |
| Entry-point name (`pyproject.toml`) | exact key string | `csl_fluo` |
| Duet `M563 S"..."` | exact key string | `M563 P2 S"csl_fluo"` |
| Python package name (import) | `[a-z_][a-z0-9_]*` — replace `-` with `_` | `csl_fluo_tool` |
| Distribution name (pip / PyPI) | lowercase, prefer dashes | `csl-fluo-tool` |

---

## 2. Repo layout

```
csl-fluo-tool/                        # distribution name  (key dashes, not underscores)
├── pyproject.toml
├── README.md
├── .gitignore
├── setup_duet.py                     # fill in X/Y coords, run to generate tpre/tpost/tfree
├── tpre.g.template                   # reference copies of the Jinja2 firmware templates
├── tpost.g.template
├── tfree.g.template
├── src/
│   └── csl_fluo_tool/                # Python package name  (key with underscores + _tool)
│       ├── __init__.py
│       ├── tool.py                   # hardware Tool subclass
│       ├── mock.py                   # mock subclass
│       ├── configs/
│       │   └── csl_fluo.json
│       └── twin_assets/              # place .stl / .blend / .step files here
└── tests/
    └── test_tool.py
```

---

## 3. `pyproject.toml` — entry-point groups

```toml
[project]
name = "csl-fluo-tool"
version = "0.1.0"
dependencies = ["science-jubilee>=0.4"]

[project.entry-points."science_jubilee.tools"]
csl_fluo = "csl_fluo_tool.tool:FluoTool"

[project.entry-points."science_jubilee.tools.mocks"]
csl_fluo = "csl_fluo_tool.mock:FluoToolMock"

[project.entry-points."science_jubilee.tools.configs"]
csl_fluo = "csl_fluo_tool.configs:__path__"

[project.entry-points."science_jubilee.tools.twin_assets"]
csl_fluo = "csl_fluo_tool.twin_assets:__path__"
```

The entry-point **name** (`csl_fluo`) must exactly match the `TOOL_KEY` class
attribute.  The registry raises `ToolConfigurationError` at startup if they differ.

Groups 3 and 4 (`configs`, `twin_assets`) are optional — only declare the groups
your plugin actually ships.

---

## 4. Writing the `Tool` subclass

```python
# src/csl_fluo_tool/tool.py
from dataclasses import dataclass
from typing import ClassVar

from science_jubilee.tools.Tool import Tool, requires_active_tool


@dataclass(slots=True, repr=False)
class FluoTool(Tool):
    TOOL_KEY: ClassVar[str] = "csl_fluo"

    exposure_ms: float = 100.0

    @requires_active_tool
    def capture(self, nav) -> None:
        """Trigger fluorescence capture at the current position."""
        ...
```

Key points:

- Inherit from `Tool`, use `@dataclass(slots=True, repr=False)`.
- Set `TOOL_KEY` as a `ClassVar[str]` matching the entry-point name.
- Gate hardware calls with `@requires_active_tool` so they fail fast if the
  tool is not the active Duet tool.
- The mock subclass can inherit from `FluoTool` and override only the I/O calls.

---

## 5. Duet firmware setup

The `tpre<N>.g`, `tpost<N>.g`, and `tfree<N>.g` files on the Duet SD card are
**machine-calibrated positional data** — they contain the exact X/Y coordinates
of each physical parking post on *that specific machine*.  They are generated once
by running the `SetToolParkingPositions` calibration notebook and have nothing to
do with the tool type.  **A plugin does not ship these files.**

The only Duet-side contributions for a new tool are one line in `toffsets.g` and
one `M563` declaration in `config.g` — both added manually after running
`generate_tool_gfiles` and the Tool Alignment XY calibration (see section 6).

---

## 6. Installing a plugin — user steps

### Python side (one command)

```bash
pip install git+https://github.com/<owner>/csl-fluo-tool
```

After this, `ToolChanger` discovers `FluoTool` automatically via entry points.
No code changes to the mother repo are required.

### Duet firmware side (manual, once per machine)

1. **Generate the parking macros** by calling `generate_tool_gfiles` (or running
   `calibration/SetToolParkingPositions.ipynb`).  Pass the X/Y positions you
   measured while physically aligning the parking post:
   ```python
   from science_jubilee.calibration.tool_gfiles import generate_tool_gfiles
   generate_tool_gfiles(tool_number=2, x_park=210.0, y_park=338.0, y_clear=270.0)
   # writes tpre2.g, tpost2.g, tfree2.g to firmware/sys/ and prints contents
   ```
   Upload the rendered files to `0:/sys/` on the Duet (pass `transport=` to
   upload automatically, or copy-paste via the Duet Web Console).
2. **Run the Tool Alignment XY calibration** to determine the tool offset (X, Y, Z).
3. **Add one line to `toffsets.g`**:
   ```gcode
   G10 P{N} X{X} Y{Y} Z{Z}  ; csl_fluo
   ```
4. **Add one line to `config.g`** (the `S"..."` string must match `TOOL_KEY` exactly):
   ```gcode
   M563 P{N} S"csl_fluo"
   ```
5. Restart the Duet (`M999`).

---

## 7. Digital-twin assets

Place `.stl`, `.blend`, or `.step` files in `src/csl_fluo_tool/twin_assets/`.
The `jubilee-blender-twin` tool discovers them via the
`science_jubilee.tools.twin_assets` entry-point group and can import the geometry
automatically during scene setup.

---

## 8. Path to the mother repo

If your tool becomes popular and the community converges on it, it can be absorbed
into `science-jubilee` directly:

1. Move the folder into `src/science_jubilee/tools/<toolname>/`.
2. Rename `TOOL_KEY` from `csl_fluo` → `fluo` (drop the org prefix).
3. Move the entry-point declarations from the plugin's `pyproject.toml` into the
   mother repo's `setup.cfg`.
4. The old plugin package can release a final version that depends on the new
   mother-repo version and re-exports the class for backwards compatibility.
