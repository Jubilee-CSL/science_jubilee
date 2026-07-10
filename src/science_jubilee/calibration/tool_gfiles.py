"""Generate and optionally upload Duet tool g-code files from Jinja2 templates.

Renders the standard set of per-tool firmware files:
  - ``tpre{n}.g``   – runs before picking up tool n
  - ``tpost{n}.g``  – runs after tool n is locked on the carriage
  - ``tfree{n}.g``  – runs before releasing tool n

If an ``HTTPTransport`` (or address string) is provided each rendered file is
also uploaded to ``0:/sys/`` on the Duet immediately after being written.

Example
-------
>>> from science_jubilee.calibration.tool_gfiles import generate_tool_gfiles
>>>
>>> generate_tool_gfiles(
...     tool_number=0,
...     x_park=100.0,
...     y_park=300.0,
...     y_clear=260.0,
...     manhattan_offset=60.0,
... )
# writes tpre0.g, tpost0.g, tfree0.g to firmware/sys/

>>> # With automatic upload to the Duet:
>>> from science_jubilee.hal.transport.http import HTTPTransport
>>> transport = HTTPTransport("10.0.3.48")
>>> generate_tool_gfiles(
...     tool_number=0,
...     x_park=100.0, y_park=300.0, y_clear=260.0, manhattan_offset=60.0,
...     transport=transport,
... )
"""

from __future__ import annotations

import os
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
    transport=None,
    print_output: bool = True,
) -> dict[str, Path]:
    """Render tpre, tpost, and tfree g-code files for a tool.

    Parameters
    ----------
    tool_number:
        Index of the tool being configured.
    x_park:
        X coordinate of the tool's parking post.
    y_park:
        Y coordinate of the parking post (tool locked position).
    y_clear:
        Y coordinate safely clear of all parking posts.
    manhattan_offset:
        Offset (mm) added to x_park for the approach move in tpre. Default 60.
    output_dir:
        Directory to write the rendered files. Defaults to
        ``<repo_root>/firmware/sys/``.
    transport:
        An ``HTTPTransport`` instance or a bare address string (e.g.
        ``"10.0.3.48"``). When provided, each file is also uploaded to
        ``0:/sys/`` on the Duet immediately after being written locally.
    print_output:
        If True (default), print the rendered content of each file.

    Returns
    -------
    dict[str, Path]
        Mapping of template base name (e.g. ``"tpre"``) -> absolute local path
        of the written file.
    """
    if output_dir is None:
        # Default: <repo>/firmware/sys/ relative to this file's location
        # parents[0]=calibration, [1]=science_jubilee, [2]=src, [3]=repo root
        output_dir = Path(__file__).parents[3] / "firmware" / "sys"
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

    if transport is not None:
        _upload_files(transport, list(written.values()))

    return written


def _upload_files(transport, paths: list[Path]) -> None:
    """Upload a list of local paths to 0:/sys/ via HTTPTransport."""
    # Accept a bare address string for convenience
    from science_jubilee.hal.transport.http import HTTPTransport

    if isinstance(transport, str):
        transport = HTTPTransport(address=transport)

    for path in paths:
        transport.upload_file(path, destination="sys")
