"""Convenience helpers for downloading G-code files from a Duet filesystem.

This mirrors :mod:`science_jubilee.utils.duet_upload` but for reads/sync.
It uses :class:`science_jubilee.hal.transport.http.HTTPTransport` for file
reads and performs directory listing via DWC2/legacy HTTP endpoints.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from science_jubilee.hal.transport.http import HTTPTransport


def _get_transport(transport_or_address) -> HTTPTransport:
    """Return an HTTPTransport, constructing one from an address string if needed."""
    if isinstance(transport_or_address, HTTPTransport):
        return transport_or_address
    if isinstance(transport_or_address, str):
        return HTTPTransport(address=transport_or_address)
    raise TypeError(
        "transport_or_address must be a hostname string or an HTTPTransport instance."
    )


def _normalize_remote_path(remote_path: str) -> str:
    p = str(remote_path).strip()
    if p.startswith("0:/"):
        return p
    return "0:/" + p.lstrip("/")


def _normalize_entries(payload) -> list[tuple[str, bool]]:
    """Normalize directory listing payload to ``[(name, is_dir), ...]``."""
    items = payload
    if isinstance(payload, dict):
        if isinstance(payload.get("result"), list):
            items = payload["result"]
        elif isinstance(payload.get("files"), list):
            items = payload["files"]
        else:
            items = []

    out: list[tuple[str, bool]] = []
    if not isinstance(items, list):
        return out

    for item in items:
        name: str | None = None
        is_dir = False

        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            raw_name = (
                item.get("name")
                or item.get("fileName")
                or item.get("filename")
                or item.get("path")
            )
            if raw_name is not None:
                name = str(raw_name)
            kind = str(item.get("type", "")).lower()
            if kind in {"d", "dir", "directory"}:
                is_dir = True
            if bool(item.get("directory")):
                is_dir = True

        if not name:
            continue

        name = name.replace("\\", "/")
        base = name.split("/")[-1]
        if base in {"", ".", ".."}:
            continue

        out.append((base, is_dir))

    # De-duplicate while preserving order
    seen: set[str] = set()
    deduped: list[tuple[str, bool]] = []
    for n, d in out:
        key = f"{n}|{int(d)}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append((n, d))
    return deduped


def list_remote_dir(
    transport_or_address,
    remote_dir: str,
    *,
    timeout: float = 10.0,
) -> list[tuple[str, bool]]:
    """List remote directory entries as ``(name, is_dir)``.

    Tries DWC2 endpoint first, then falls back to legacy ``rr_filelist``.
    """
    transport = _get_transport(transport_or_address)
    remote_dir = _normalize_remote_path(remote_dir)

    # Attempt 1: DWC2 endpoint
    encoded = remote_dir.replace(":", "%3A").replace(" ", "%20")
    dwc2_url = f"http://{transport.address}/machine/directory/{encoded}"
    try:
        resp = transport.session.get(dwc2_url, timeout=timeout)
        if resp.status_code == 200:
            entries = _normalize_entries(resp.json())
            if entries:
                return entries
    except Exception:
        pass

    # Attempt 2: Legacy endpoint
    rr_url = f"http://{transport.address}/rr_filelist"
    try:
        resp = transport.session.get(
            rr_url, params={"dir": remote_dir}, timeout=timeout
        )
        if resp.status_code == 200:
            entries = _normalize_entries(resp.json())
            if entries:
                return entries
    except Exception:
        pass

    return []


def download_remote_tree(
    transport_or_address,
    remote_root: str,
    local_root: str | os.PathLike,
    *,
    recursive: bool = True,
    clean: bool = False,
    timeout: float = 10.0,
) -> list[Path]:
    """Download all files from a remote Duet folder into a local folder.

    Parameters
    ----------
    transport_or_address:
        Address string (e.g. ``"10.0.3.48"``) or an existing HTTPTransport.
    remote_root:
        Remote folder (e.g. ``"0:/sys"`` or ``"macros"``).
    local_root:
        Local destination folder.
    recursive:
        If True, include nested folders.
    clean:
        If True, remove local files/folders in ``local_root`` that are not
        present on the remote folder after download (mirror mode).
    timeout:
        Per-request timeout.

    Returns
    -------
    list[pathlib.Path]
        Paths of local files written.
    """
    transport = _get_transport(transport_or_address)
    remote_root = _normalize_remote_path(remote_root).rstrip("/")
    local_root = Path(local_root)
    local_root.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    expected_relative: set[Path] = set()

    def _walk(remote_dir: str, target_dir: Path) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        for name, is_dir in list_remote_dir(transport, remote_dir, timeout=timeout):
            remote_path = f"{remote_dir}/{name}"
            local_path = target_dir / name
            if is_dir:
                if recursive:
                    _walk(remote_path, local_path)
                continue
            content = transport.read_file(remote_path, timeout=timeout)
            local_path.write_text(content, encoding="utf-8")
            written.append(local_path)
            expected_relative.add(local_path.relative_to(local_root))

    _walk(remote_root, local_root)

    if clean:
        # Remove stale files first
        for existing in sorted(
            local_root.rglob("*"), key=lambda p: len(p.parts), reverse=True
        ):
            if existing.is_file():
                rel = existing.relative_to(local_root)
                if rel not in expected_relative:
                    existing.unlink(missing_ok=True)

        # Remove now-empty directories (bottom-up), keep local_root
        for d in sorted(
            [p for p in local_root.rglob("*") if p.is_dir()],
            key=lambda p: len(p.parts),
            reverse=True,
        ):
            try:
                d.rmdir()
            except OSError:
                # Directory not empty (or race) - leave it
                pass

    return written


def download_many(
    transport_or_address,
    mappings: Iterable[tuple[str, str | os.PathLike]],
    *,
    recursive: bool = True,
    clean: bool = False,
    timeout: float = 10.0,
) -> dict[str, list[Path]]:
    """Download multiple remote folders.

    ``mappings`` is an iterable of ``(remote_root, local_root)``.
    """
    out: dict[str, list[Path]] = {}
    for remote_root, local_root in mappings:
        out[str(remote_root)] = download_remote_tree(
            transport_or_address,
            remote_root,
            local_root,
            recursive=recursive,
            clean=clean,
            timeout=timeout,
        )
    return out
