"""Convenience shim for uploading G-code files to the Duet filesystem.

The implementation lives on ``HTTPTransport.upload_file`` / ``upload_files``.
These module-level helpers accept either a bare address string or an
``HTTPTransport`` instance, constructing one on the fly if needed.

Example
-------
>>> from science_jubilee.utils.duet_upload import upload_gcode_file
>>> upload_gcode_file("10.0.3.48", "C:/Users/me/toffsets.g")
>>> upload_gcode_file("10.0.3.48", "C:/local/my_macro.g", destination="macros")

>>> # Or use the transport directly (preferred):
>>> from science_jubilee.hal.transport.http import HTTPTransport
>>> transport = HTTPTransport(address="10.0.3.48")
>>> transport.upload_file("C:/Users/me/toffsets.g")
"""

from __future__ import annotations

import logging
import os
from typing import Union

from science_jubilee.hal.transport.http import HTTPTransport

logger = logging.getLogger(__name__)


def _get_transport(transport_or_address) -> HTTPTransport:
    """Return an HTTPTransport, constructing one from an address string if needed."""
    if isinstance(transport_or_address, HTTPTransport):
        return transport_or_address
    if isinstance(transport_or_address, str):
        return HTTPTransport(address=transport_or_address)
    raise TypeError(
        "transport_or_address must be a hostname string or an HTTPTransport instance."
    )


def upload_gcode_file(
    transport_or_address,
    local_path: Union[str, os.PathLike],
    *,
    destination: str = "sys",
    remote_name: str | None = None,
    timeout: float = 30.0,
) -> str:
    """Convenience wrapper around ``HTTPTransport.upload_file``.

    Accepts either a bare address string or an existing ``HTTPTransport``.
    Prefer calling ``transport.upload_file(...)`` directly when you already
    have a transport instance.
    """
    return _get_transport(transport_or_address).upload_file(
        local_path,
        destination=destination,
        remote_name=remote_name,
        timeout=timeout,
    )


def upload_gcode_files(
    transport_or_address,
    local_paths: list[Union[str, os.PathLike]],
    *,
    destination: str = "sys",
    timeout: float = 30.0,
) -> list[str]:
    """Convenience wrapper around ``HTTPTransport.upload_files``."""
    return _get_transport(transport_or_address).upload_files(
        local_paths,
        destination=destination,
        timeout=timeout,
    )
