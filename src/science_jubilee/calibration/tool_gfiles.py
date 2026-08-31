"""Generate Duet tool g-code files from Jinja2 templates.

Renders the standard set of per-tool firmware files:
  - ``tpre{n}.g``   – runs before picking up tool n
  - ``tpost{n}.g``  – runs after tool n is locked on the carriage
  - ``tfree{n}.g``  – runs before releasing tool n

Files are written to a dated local folder (``firmware/sys/YYYY-MM-DD/``).
Upload to the Duet manually via DuetWebControl → System → 0:/sys/.

Example
-------
>>> from science_jubilee.calibration.tool_gfiles import generate_tool_gfiles
>>> generate_tool_gfiles(
...     tool_number=0,
...     x_park=100.0,
...     y_park=300.0,
...     y_clear=260.0,
...     manhattan_offset=60.0,
... )
# writes tpre0.g, tpost0.g, tfree0.g to firmware/sys/YYYY-MM-DD/
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader

# Templates live alongside this file in the templates/ subdirectory
_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Files to render: (template_name, output_filename_pattern)
_TOOL_TEMPLATES: list[tuple[str, str]] = [
    ("tpre.g", "tpre{n}.g"),
    ("tpost.g", "tpost{n}.g"),
    ("tfree.g", "tfree{n}.g"),
]


def generate_tool_gfiles(
    tool_number: int,
    *,
    x_park: float,
    y_park: float,
    y_clear: float,
    manhattan_offset: float = 60.0,
    output_dir: Optional[Union[str, os.PathLike]] = None,
    print_output: bool = True,
) -> dict[str, Path]:
    """Render tpre, tpost, and tfree g-code files for a tool.

    Files are written to a dated subdirectory of ``firmware/sys/`` so previous
    runs are never overwritten.  Copy the files to ``0:/sys/`` on the Duet via
    DuetWebControl, renaming them without the date suffix.

    Returns a mapping of template base name -> absolute local path.
    """
    if output_dir is None:
        from science_jubilee._paths import jubilee_dir

        output_dir = jubilee_dir() / "firmware" / "sys" / date.today().isoformat()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))

    context = {
        "tool_number": tool_number,
        "x_park": x_park,
        "y_park": y_park,
        "y_clear": y_clear,
        "manhattan_offset": manhattan_offset,
    }

    written: dict[str, Path] = {}

    for template_name, filename_pattern in _TOOL_TEMPLATES:
        template = env.get_template(template_name)
        content = template.render(**context)
        out_name = filename_pattern.format(n=tool_number)
        out_path = output_dir / out_name

        with open(out_path, "w") as f:
            f.write(content)

        if print_output:
            print(f"--- {out_name} ---")
            print(content)

        key = template_name.replace(".g", "")  # e.g. "tpre"
        written[key] = out_path

    return written
