"""Record the fallback walks of a run and render them as one recap page.

Stdlib only, so this works in a venv and in Blender's bundled Python alike.
Each step is drawn in red when it failed, green when it answered, grey when it
was skipped, orange when only partly satisfied.

A run accumulates several sections (machine state, tool plugins, package paths,
camera calibration, ...) into a single :class:`Trace`, then flushes them to
``<dir>/traces/<command>.html``. HTML rather than SVG so that paths wrap instead
of being clipped and can be opened as links.

Call :func:`capture_logger` once per package whose log should appear in the
recap alongside the walks.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path

FAILED = "failed"
OK = "ok"
SKIPPED = "skipped"
PARTIAL = "partial"

_GLYPH = {FAILED: "\u2715", OK: "\u2713", SKIPPED: "\u2013", PARTIAL: "+"}

_MAX_RECORDS = 2000
_records: deque = deque(maxlen=_MAX_RECORDS)
_captured: set[str] = set()


class _BufferHandler(logging.Handler):
    """Keep records in memory so the recap can show what happened, in order."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _records.append(
                (
                    time.strftime("%H:%M:%S", time.localtime(record.created)),
                    record.levelname,
                    record.name,
                    record.getMessage(),
                )
            )
        except Exception:  # logging must never break the run
            pass


def capture_logger(name: str) -> None:
    """Mirror a logger's records into the recap. Safe to call repeatedly."""
    if name in _captured:
        return
    _captured.add(name)
    logging.getLogger(name).addHandler(_BufferHandler())


def get_records() -> list:
    """Return (time, level, logger, message) for every captured record."""
    return list(_records)


def clear_records() -> None:
    _records.clear()


_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 28px 32px 48px;
       font-family: "Segoe UI", Helvetica, Arial, sans-serif;
       background: #f7f8fa; color: #212121; }
h1 { font-size: 20px; margin: 0 0 4px; }
.meta { font-size: 12px; color: #757575; margin-bottom: 20px; }
.legend span { margin-right: 14px; white-space: nowrap; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px;
      margin-right: 5px; vertical-align: -1px; }
.cols { display: grid; gap: 20px;
        grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
.card { background: #fff; border: 1px solid #e4e6ea; border-radius: 10px;
        padding: 14px 16px 16px; }
.card > h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em;
             color: #546e7a; margin: 0 0 10px; }
.step { border-radius: 8px; border: 1.5px solid; padding: 8px 10px;
        margin-bottom: 8px; }
.step .lbl { font-size: 13px; font-weight: 600; display: flex; gap: 8px; }
.step .g { font-weight: 700; }
.step .det { font-size: 11.5px; color: #5c6b73; margin-top: 4px;
             overflow-wrap: anywhere; font-family: Consolas, monospace; }
.step .det a { color: #1565c0; text-decoration: none; }
.step .det a:hover { text-decoration: underline; }
.failed  { background: #ffebee; border-color: #c62828; }
.failed  .g { color: #c62828; }
.ok      { background: #e8f5e9; border-color: #2e7d32; }
.ok      .g { color: #2e7d32; }
.skipped { background: #f5f5f5; border-color: #bdbdbd; }
.skipped .g { color: #9e9e9e; }
.partial { background: #fff8e1; border-color: #ef6c00; }
.partial .g { color: #ef6c00; }
details.res { background: #fff; border: 1px solid #e4e6ea; border-radius: 10px;
              padding: 12px 16px; margin-top: 20px; }
details.res summary { font-size: 13px; font-weight: 600; cursor: pointer;
                      color: #37474f; }
details.res a { color: #1565c0; text-decoration: none; }
details.res pre { background: #fafbfc; border: 1px solid #eceff1; border-radius: 6px;
                  padding: 12px; overflow: auto; max-height: 460px;
                  font-size: 11.5px; font-family: Consolas, monospace;
                  color: #37474f; margin: 10px 0 0; }
table.log { width: 100%; border-collapse: collapse; margin-top: 10px;
            font-size: 11.5px; font-family: Consolas, monospace; }
table.log td { padding: 2px 8px 2px 0; vertical-align: top;
               border-bottom: 1px solid #f0f2f4; }
table.log td.t { color: #9aa5ab; white-space: nowrap; }
table.log td.l { font-weight: 700; white-space: nowrap; }
table.log td.n { color: #78909c; white-space: nowrap; }
table.log td.m { overflow-wrap: anywhere; }
.lv-ERROR, .lv-CRITICAL { color: #c62828; }
.lv-WARNING { color: #ef6c00; }
.lv-INFO { color: #2e7d32; }
.lv-DEBUG { color: #9e9e9e; }
"""


def _esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _linkify(detail: str) -> str:
    """Render a detail string, turning a filesystem path into a file:// link."""
    detail = str(detail)
    if os.sep not in detail or len(detail) < 4:
        return _esc(detail)
    try:
        target = Path(detail)
        href = target.resolve().as_uri()
    except (OSError, ValueError):
        return _esc(detail)
    missing = "" if target.exists() else " (missing)"
    return f'<a href="{_esc(href)}" title="{_esc(detail)}">{_esc(detail)}</a>{missing}'


def _linkify_tokens(text: str) -> str:
    """Linkify path-looking words inside a longer sentence."""
    return " ".join(
        _linkify(word) if os.sep in word and len(word) > 3 else _esc(word)
        for word in str(text).split(" ")
    )


def _log_html() -> str:
    """Render the buffered run log; the cards say why, this says what happened."""
    records = get_records()
    if not records:
        return ""
    rows = "".join(
        f'<tr><td class="t">{_esc(when)}</td>'
        f'<td class="l lv-{_esc(level)}">{_esc(level)}</td>'
        f'<td class="n">{_esc(name.split(".", 1)[-1])}</td>'
        f'<td class="m">{_linkify_tokens(message)}</td></tr>'
        for when, level, name, message in records
    )
    return (
        '<details class="res"><summary>Run log '
        f"&middot; {len(records)} records</summary>"
        f'<table class="log">{rows}</table></details>'
    )


class Section:
    """One fallback walk inside a run."""

    def __init__(self, name: str):
        self.name = name
        self.steps: list[tuple[str, str, str]] = []

    def step(self, label: str, status: str, detail: str = "") -> None:
        self.steps.append((label, status, detail))

    def failed(self, label: str, detail: str = "") -> None:
        self.step(label, FAILED, detail)

    def ok(self, label: str, detail: str = "") -> None:
        self.step(label, OK, detail)

    def skipped(self, label: str, detail: str = "") -> None:
        self.step(label, SKIPPED, detail)

    def partial(self, label: str, detail: str = "") -> None:
        self.step(label, PARTIAL, detail)

    def to_html(self) -> str:
        rows = [f"<h2>{_esc(self.name)}</h2>"]
        for label, status, detail in self.steps:
            glyph = _GLYPH.get(status, _GLYPH[SKIPPED])
            rows.append(f'<div class="step {_esc(status)}">')
            rows.append(
                f'<div class="lbl"><span class="g">{glyph}</span>'
                f"<span>{_esc(label)}</span></div>"
            )
            if detail:
                rows.append(f'<div class="det">{_linkify(detail)}</div>')
            rows.append("</div>")
        return '<section class="card">' + "".join(rows) + "</section>"


class Trace:
    """Collects every fallback walk of a run, plus the files it produced."""

    def __init__(self, title: str = "jubilee-twin run"):
        self.title = title
        self.sections: list[Section] = []
        self.results: list[tuple[str, str, str]] = []

    def section(self, name: str, reset: bool = False) -> Section:
        """Return the named section, creating it on first use.

        Pass reset=True at the start of a walk so re-running it in the same
        process replaces its steps instead of appending to them.
        """
        for existing in self.sections:
            if existing.name == name:
                if reset:
                    existing.steps.clear()
                return existing
        created = Section(name)
        self.sections.append(created)
        return created

    def result(self, label: str, text: str = "", path: str = "") -> None:
        """Attach a produced file's contents, shown below the walks."""
        self.results = [r for r in self.results if r[0] != label]
        self.results.append((label, text, str(path)))

    def _default(self) -> Section:
        return self.section("Run")

    def failed(self, label: str, detail: str = "") -> None:
        self._default().failed(label, detail)

    def ok(self, label: str, detail: str = "") -> None:
        self._default().ok(label, detail)

    def skipped(self, label: str, detail: str = "") -> None:
        self._default().skipped(label, detail)

    def partial(self, label: str, detail: str = "") -> None:
        self._default().partial(label, detail)

    def render_html(self, out_path) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        legend = "".join(
            f'<span><i class="sw" style="background:{colour}"></i>'
            f"{_GLYPH[status]} {word}</span>"
            for status, colour, word in (
                (OK, "#2e7d32", "answered"),
                (FAILED, "#c62828", "failed"),
                (SKIPPED, "#bdbdbd", "skipped"),
                (PARTIAL, "#ef6c00", "partial"),
            )
        )

        results = "".join(
            '<details class="res" open>'
            f"<summary>{_esc(label)}"
            f'{f" &middot; {_linkify(path)}" if path else ""}</summary>'
            f"<pre>{_esc(text)}</pre></details>"
            for label, text, path in self.results
        )

        html = (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_esc(self.title)}</title><style>{_CSS}</style></head><body>"
            f"<h1>{_esc(self.title)}</h1>"
            f'<div class="meta">{_esc(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}'
            f'<div class="legend" style="margin-top:6px">{legend}</div></div>'
            f'<div class="cols">{"".join(s.to_html() for s in self.sections)}</div>'
            f"{results}{_log_html()}</body></html>"
        )
        out_path.write_text(html, encoding="utf-8")
        return out_path


# ---------------------------------------------------------------------------
# Run-scoped session
#
# Several independent steps contribute to one recap page and none of them call
# each other, so the trace lives here instead of being threaded through every
# signature.
# ---------------------------------------------------------------------------

_session: Trace | None = None
_session_dir: Path | None = None


def start_session(out_dir, title: str = "jubilee run") -> Trace:
    """Begin a fresh recap. Call once per command."""
    global _session, _session_dir
    _session = Trace(title)
    _session_dir = Path(out_dir) if out_dir is not None else None
    return _session


def session(out_dir=None, title: str = "jubilee run") -> Trace:
    """Return the current recap, starting one if the command did not."""
    global _session_dir
    if _session is None:
        # Deferred init: sections may accumulate before the caller can set a dir.
        start_session(out_dir, title)
    elif out_dir is not None:
        _session_dir = Path(out_dir)
    return _session


def flush(out_dir=None, name: str | None = None) -> Path | None:
    """Render the recap to <dir>/traces/<name>.html.

    Defaults to a filename derived from the session title, so each command
    keeps its own recap instead of overwriting a shared one.
    """
    if _session is None or not _session.sections:
        return None
    target = Path(out_dir) if out_dir is not None else _session_dir
    if target is None:
        return None
    if name is None:
        slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in _session.title)
        for prefix in ("jubilee-twin-", "jubilee-"):
            slug = slug.replace(prefix, "")
        name = slug.strip("-") or "recap"
    return _session.render_html(Path(target) / "traces" / f"{name}.html")
