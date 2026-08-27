import logging
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional, Union

import requests
from requests.adapters import HTTPAdapter, Retry

from .base import BaseTransport

logger = logging.getLogger(__name__)


class HTTPTransport(BaseTransport):
    """HTTP transport for Duet/RepRapFirmware endpoints."""

    def __init__(
        self,
        address: str,
        session: Optional[requests.Session] = None,
        crash_detection: bool = False,
        crash_handler=None,
        deck_clear_provider: Optional[Callable[[], bool]] = None,
    ):
        self.address = address
        self.crash_detection = crash_detection
        self.crash_handler = crash_handler
        self.deck_clear_provider = deck_clear_provider

        if session is None:
            session = requests.Session()
            retries = Retry(
                total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
            )
            session.mount("http://", HTTPAdapter(max_retries=retries))
            session.headers["Connection"] = "close"
        self.session = session

    @staticmethod
    def _split_response_objects(s: str):
        """Split text strings from gcode responses when multiple responses are in the Duet buffer."""
        return [line for line in s.split("\n") if line.strip()]

    @staticmethod
    def _delay_time(n: int) -> float:
        """Calculate delay time for next request. Simple stepped backoff."""
        if n == 0:
            return 0
        if n < 10:
            return 0.1
        if n < 20:
            return 0.2
        if n < 30:
            return 0.3
        else:
            return 1

    def send_gcode(
        self,
        cmd: str = "",
        timeout: Optional[float] = None,
        response_wait: float = 60,
        wait: bool = False,
    ):
        """Send a G-Code command over HTTP and return the response or None.
        If wait is True and the command implies motion, ensure completion with M400.
        """
        try:
            response = self.session.post(
                f"http://{self.address}/machine/code", data=f"{cmd}", timeout=timeout
            ).text
            # On success via /machine/code, optionally block until motion completes
            if wait and not cmd.strip().upper().startswith("M400"):
                _ = self.session.post(
                    f"http://{self.address}/machine/code", data="M400", timeout=timeout
                ).text
            if "rejected" in response:
                raise requests.RequestException
        except requests.RequestException:
            try:
                # Query reply sequence
                reply_response = self.session.get(
                    f"http://{self.address}/rr_model?key=seqs"
                )
                logger.debug(
                    f"MODEL response, status: {reply_response.status_code}, headers:{reply_response.headers}, content:{reply_response.content}"
                )
                reply_count = reply_response.json()["result"]["reply"]

                buffer_response = self.session.get(
                    f"http://{self.address}/rr_gcode?gcode={cmd}", timeout=timeout
                )
                logger.debug(
                    f"GCODE response, status: {buffer_response.status_code}, headers:{buffer_response.headers}, content:{buffer_response.content}"
                )

                tic = time.time()
                try_count = 0
                while True:
                    try:
                        new_reply_response = self.session.get(
                            f"http://{self.address}/rr_model?key=seqs"
                        )
                        logger.debug(
                            f"MODEL response, status: {new_reply_response.status_code}, headers:{new_reply_response.headers}, content:{new_reply_response.content}"
                        )
                        new_reply_count = new_reply_response.json()["result"]["reply"]

                        if new_reply_count != reply_count:
                            reply = self.session.get(f"http://{self.address}/rr_reply")
                            logger.debug(
                                f"REPLY response, status: {reply.status_code}, headers:{reply.headers}, content:{reply.content}"
                            )
                            text = reply.text

                            responses = self._split_response_objects(text)
                            if len(responses) > 0:
                                text = responses[-1]
                            else:
                                text = None

                            if (
                                self.crash_detection
                                and text
                                and ("crash detected" in text)
                            ):
                                logger.error("Jubilee crash detected")
                                if self.crash_handler is not None:
                                    try:
                                        self.crash_handler.handle_crash()
                                    except Exception as e:
                                        logger.exception(f"Crash handler failed: {e}")
                            # If requested, wait for motion completion via M400
                            if wait and not (cmd.strip().upper().startswith("M400")):
                                # Issue M400 and wait for its reply increment
                                m400_reply_response = self.session.get(
                                    f"http://{self.address}/rr_model?key=seqs"
                                )
                                m400_reply_count = m400_reply_response.json()["result"][
                                    "reply"
                                ]
                                self.session.get(
                                    f"http://{self.address}/rr_gcode?gcode=M400",
                                    timeout=timeout,
                                )
                                tic2 = time.time()
                                tries2 = 0
                                while True:
                                    try:
                                        new_m400_reply_response = self.session.get(
                                            f"http://{self.address}/rr_model?key=seqs"
                                        )
                                        new_m400_reply_count = (
                                            new_m400_reply_response.json()["result"][
                                                "reply"
                                            ]
                                        )
                                        if new_m400_reply_count != m400_reply_count:
                                            # consume rr_reply for M400
                                            _ = self.session.get(
                                                f"http://{self.address}/rr_reply"
                                            )
                                            break
                                        elif time.time() - tic2 > response_wait:
                                            break
                                        time.sleep(self._delay_time(tries2))
                                        tries2 += 1
                                    except Exception:
                                        time.sleep(2)
                                        continue
                            return text
                        elif time.time() - tic > response_wait:
                            return None
                        time.sleep(self._delay_time(try_count))
                        try_count += 1
                    except Exception as e:
                        logger.debug(f"Error in gcode reply wait loop: {e}")
                        time.sleep(2)
                        continue
            except requests.RequestException as e:
                logger.error(
                    f"Both `requests.post` and `requests.get` requests failed: {e}"
                )
                return None
        return response

    def connect(self, timeout: Optional[float] = 5.0) -> bool:
        """Old-style connectivity check: issue an object-model GCode query and
        confirm we receive a valid JSON response.

        Mirrors prior Machine.connect logic by probing
        M409 K"move.axes[].homed" and validating the "result" list.
        """
        try:
            start = time.time()
            max_tries = 50
            for i in range(max_tries):
                obj = self.send_gcode_json('M409 K"move.axes[].homed"')
                if isinstance(obj, dict):
                    res = obj.get("result")
                    if isinstance(res, list):
                        return True
                # Respect overall timeout if provided
                if timeout is not None and (time.time() - start) > timeout:
                    break
                time.sleep(self._delay_time(i))
            return False
        except Exception as e:
            logger.debug(f"HTTPTransport.connect failed: {e}")
            return False

    def deck_is_clear(self) -> bool:
        """Return deck clearance.
        Hardware/HTTP mode behavior:
        - If an external provider is supplied, use it.
        - Otherwise, interactively prompt the user to confirm the deck is clear.

        Default is False (not clear) unless user explicitly confirms.
        """
        if self.deck_clear_provider is not None:
            try:
                return bool(self.deck_clear_provider())
            except Exception:
                # If provider fails, fall back to prompt
                pass
        try:
            answer = (
                input("Confirm deck is clear and safe to home Z (y/N): ")
                .strip()
                .lower()
            )
            return answer in ("y", "yes")
        except Exception:
            return False

    # ---- Convenience: available axes (http-specific) ---------------------
    def get_available_axes(self) -> list:
        """Return axis letters available on the hardware in firmware order.

        Tries the RepRapFirmware object model via M409. Falls back to parsing
        M114 response if necessary. Letters are normalized to uppercase.
        """
        # Primary: direct letters list
        obj = self.send_gcode_json('M409 K"move.axes[].letter"')
        if obj and isinstance(obj, dict):
            res = obj.get("result")
            if isinstance(res, list) and all(isinstance(x, str) for x in res):
                return [x.upper() for x in res]

        # Fallback: axis objects
        obj2 = self.send_gcode_json('M409 K"move.axes[]"')
        if obj2 and isinstance(obj2, dict):
            res2 = obj2.get("result")
            if isinstance(res2, list):
                letters = []
                for axis_obj in res2:
                    if isinstance(axis_obj, dict) and "letter" in axis_obj:
                        letters.append(str(axis_obj["letter"]).upper())
                if letters:
                    return letters

        # Final fallback: parse M114 text response for axis letters
        try:
            text = self.send_gcode("M114") or ""
            # Find tokens like 'X:12.34' and collect the leading letters
            letters = [
                m.group(1).upper()
                for m in re.finditer(r"([A-Za-z]):\s*-?\d+(?:\.\d+)?", text)
            ]
            # Preserve order and uniqueness
            seen = set()
            ordered = []
            for l in letters:
                if l not in seen:
                    seen.add(l)
                    ordered.append(l)
            return ordered
        except Exception:
            return []

    def get_axis_limits(self) -> dict:
        """Return axis limits for the hardware: letter -> (min, max).

        Uses the RepRapFirmware object model via M409 K"move.axes[]".
        """
        try:
            obj = self.send_gcode_json('M409 K"move.axes[]"')
            limits = {}
            if obj and isinstance(obj, dict):
                res = obj.get("result")
                if isinstance(res, list):
                    for axis_obj in res:
                        if isinstance(axis_obj, dict):
                            letter = str(axis_obj.get("letter", "")).upper()
                            minv = axis_obj.get("min")
                            maxv = axis_obj.get("max")
                            if (
                                letter
                                and isinstance(minv, (int, float))
                                and isinstance(maxv, (int, float))
                            ):
                                limits[letter] = (float(minv), float(maxv))
            return limits
        except Exception:
            return {}

    def get_positions(self) -> dict:
        """Return current axis positions by parsing M114 response."""
        try:
            text = self.send_gcode("M114") or ""
        except Exception:
            return {}
        positions = {}
        for m in re.finditer(r"([A-Za-z]):\s*(-?\d+(?:\.\d+)?)", text):
            positions[m.group(1).upper()] = float(m.group(2))
        return positions

    # ---- Tools API ------------------------------------------------------
    def get_active_tool_index(self) -> int:
        """Query current tool selection via "T" response; return -1 if none."""
        try:
            resp = (self.send_gcode("T") or "").strip()
        except Exception:
            return -1
        lower = resp.lower()
        if lower.startswith("no tool"):
            return -1
        if lower.startswith("tool"):
            parts = resp.split()
            try:
                return int(parts[1])
            except Exception:
                return -1
        if resp.isdigit():
            try:
                return int(resp)
            except Exception:
                return -1
        return -1

    def select_tool(self, tool_idx: int) -> bool:
        try:
            _ = self.send_gcode(f"T{int(tool_idx)}")
            return True
        except Exception:
            return False

    def park_tool(self) -> bool:
        try:
            _ = self.send_gcode("T-1")
            return True
        except Exception:
            return False

    def get_tools(self) -> dict:
        """Return configured tools: {number: {"name": str}}."""
        tools: dict[int, dict] = {}
        try:
            obj = self.send_gcode_json('M409 K"tools[]"')
            if obj and isinstance(obj, dict):
                res = obj.get("result")
                if isinstance(res, list):
                    for t in res:
                        if isinstance(t, dict):
                            num = t.get("number")
                            name = t.get("name")
                            if isinstance(num, int):
                                tools[num] = {"name": name}
        except Exception:
            pass
        return tools

    def get_tool_offsets(self) -> dict:
        """Return tool offsets mapping number -> [X, Y, Z]."""
        offsets: dict[int, list[float]] = {}
        try:
            obj = self.send_gcode_json('M409 K"tools"')
            if obj and isinstance(obj, dict):
                res = obj.get("result")
                if isinstance(res, list):
                    for t in res:
                        if isinstance(t, dict):
                            num = t.get("number")
                            offs = t.get("offsets")
                            if (
                                isinstance(num, int)
                                and isinstance(offs, list)
                                and len(offs) >= 3
                            ):
                                try:
                                    x, y, z = (
                                        float(offs[0]),
                                        float(offs[1]),
                                        float(offs[2]),
                                    )
                                    offsets[num] = [x, y, z]
                                except Exception:
                                    pass
        except Exception:
            pass
        return offsets

    @staticmethod
    def _parse_park_position(content: str) -> list:
        """Extract [X, Y, Z] from a tpost{n}.g file by reading G53 lines."""
        import re

        pos = [0.0, 0.0, 0.0]
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.upper().startswith("G53"):
                continue
            for letter, idx in (("X", 0), ("Y", 1), ("Z", 2)):
                m = re.search(rf"(?<![A-Z]){letter}(-?[\d.]+)", stripped, re.IGNORECASE)
                if m:
                    pos[idx] = float(m.group(1))
        return pos

    def download_sys_file(self, filename: str, timeout: float = 5.0) -> str:
        """Download a file from 0:/sys/ on the Duet and return its text content."""
        try:
            resp = self.session.get(
                f"http://{self.address}/machine/file/0:/sys/{filename}",
                timeout=timeout,
            )
            if resp.ok:
                return resp.text
        except Exception:
            pass
        resp = self.session.get(
            f"http://{self.address}/rr_download",
            params={"name": f"0:/sys/{filename}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.text

    def get_tool_parking_positions(
        self, num_tools: int = 4, timeout: float = 5.0
    ) -> dict:
        """Return {tool_idx: [X, Y, Z]} by downloading and parsing tpost{n}.g files."""
        parks: dict[int, list[float]] = {}
        for idx in range(num_tools):
            try:
                content = self.download_sys_file(f"tpost{idx}.g", timeout=timeout)
                parks[idx] = self._parse_park_position(content)
            except Exception:
                pass
        return parks

    # ---- File upload ----------------------------------------------------

    #: Accepted destination aliases -> Duet filesystem paths
    _UPLOAD_DESTINATIONS: dict[str, str] = {
        "sys": "0:/sys",
        "macros": "0:/macros",
        "macro": "0:/macros",
    }

    def upload_file(
        self,
        local_path: Union[str, os.PathLike],
        *,
        destination: str = "sys",
        remote_name: str | None = None,
        timeout: float = 30.0,
    ) -> str:
        """Upload a local .g file to the Duet filesystem.

        Tries the DWC2 endpoint (``PUT /machine/file/``) first, then falls
        back to the legacy ``rr_upload`` endpoint automatically.

        Parameters
        ----------
        local_path:
            Path to the local file to upload.
        destination:
            Target folder on the Duet: ``"sys"`` (default) or ``"macros"``.
            A full Duet path like ``"0:/sys"`` is also accepted.
        remote_name:
            Filename to use on the Duet. Defaults to the local filename.
        timeout:
            HTTP request timeout in seconds.

        Returns
        -------
        str
            Full remote path, e.g. ``"0:/sys/toffsets.g"``.

        Raises
        ------
        FileNotFoundError
            If ``local_path`` does not exist.
        RuntimeError
            If both upload endpoints fail.

        Example
        -------
        >>> transport.upload_file("C:/Jubilee/sys/toffsets.g")
        >>> transport.upload_file("C:/local/my_macro.g", destination="macros")
        >>> transport.upload_file("C:/local/offsets.g", destination="sys", remote_name="toffsets.g")
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        folder = self._UPLOAD_DESTINATIONS.get(
            destination.lower(), destination.rstrip("/")
        )
        filename = remote_name if remote_name else local_path.name
        remote_path = f"{folder}/{filename}"
        file_bytes = local_path.read_bytes()

        # --- Attempt 1: DWC2 endpoint (PUT /machine/file/...) ----------
        encoded_path = remote_path.replace(":", "%3A").replace(" ", "%20")
        dwc2_url = f"http://{self.address}/machine/file/{encoded_path}"
        try:
            resp = self.session.put(
                dwc2_url,
                data=file_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=timeout,
            )
            if resp.status_code in (200, 201):
                logger.info("Uploaded via DWC2: %s -> %s", local_path.name, remote_path)
                print(f"Uploaded '{local_path.name}' -> {remote_path}  (DWC2)")
                return remote_path
            logger.debug(
                "DWC2 upload returned %s: %s", resp.status_code, resp.text[:200]
            )
        except requests.RequestException as e:
            logger.debug("DWC2 upload failed: %s", e)

        # --- Attempt 2: Legacy rr_upload endpoint ----------------------
        rr_url = f"http://{self.address}/rr_upload"
        try:
            resp = self.session.put(
                rr_url,
                params={"name": remote_path},
                data=file_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                try:
                    body = resp.json()
                    if body.get("err", 1) == 0:
                        logger.info(
                            "Uploaded via rr_upload: %s -> %s",
                            local_path.name,
                            remote_path,
                        )
                        print(
                            f"Uploaded '{local_path.name}' -> {remote_path}  (rr_upload)"
                        )
                        return remote_path
                    logger.debug("rr_upload returned err=%s", body.get("err"))
                except Exception:
                    # Some firmware versions return plain 200 with no JSON
                    logger.info(
                        "Uploaded via rr_upload: %s -> %s", local_path.name, remote_path
                    )
                    print(f"Uploaded '{local_path.name}' -> {remote_path}  (rr_upload)")
                    return remote_path
            logger.debug("rr_upload returned %s: %s", resp.status_code, resp.text[:200])
        except requests.RequestException as e:
            logger.debug("rr_upload failed: %s", e)

        raise RuntimeError(
            f"Failed to upload '{local_path.name}' to '{remote_path}' on {self.address}. "
            "Both /machine/file/ (DWC2) and /rr_upload (legacy) endpoints failed."
        )

    def upload_files(
        self,
        local_paths: list[Union[str, os.PathLike]],
        *,
        destination: str = "sys",
        timeout: float = 30.0,
    ) -> list[str]:
        """Upload multiple files to the same destination folder.

        Parameters
        ----------
        local_paths:
            List of local file paths.
        destination:
            ``"sys"`` or ``"macros"`` (or a full Duet path).
        timeout:
            Per-file HTTP timeout.

        Returns
        -------
        list[str]
            Remote paths for each uploaded file.
        """
        return [
            self.upload_file(p, destination=destination, timeout=timeout)
            for p in local_paths
        ]

    def read_file(
        self,
        remote_path: str,
        *,
        timeout: float = 10.0,
    ) -> str:
        """Read a text file from the Duet filesystem and return its contents.

        Tries the DWC2 endpoint (``GET /machine/file/``) first, then falls
        back to the legacy ``rr_download`` endpoint.

        Parameters
        ----------
        remote_path:
            Full Duet path, e.g. ``"0:/sys/toffsets.g"``, or a short form
            like ``"sys/toffsets.g"`` which will be prefixed with ``"0:/"``
            automatically.
        timeout:
            HTTP request timeout in seconds.

        Returns
        -------
        str
            The text content of the file.

        Raises
        ------
        RuntimeError
            If neither endpoint returns the file successfully.

        Example
        -------
        >>> content = transport.read_file("0:/sys/toffsets.g")
        >>> content = transport.read_file("sys/config.g")
        """
        # Normalize: ensure the path starts with "0:/"
        if not remote_path.startswith("0:/") and not remote_path.startswith("0%3A"):
            remote_path = "0:/" + remote_path.lstrip("/")

        # --- Attempt 1: DWC2 GET /machine/file/ --------------------------
        encoded_path = remote_path.replace(":", "%3A").replace(" ", "%20")
        dwc2_url = f"http://{self.address}/machine/file/{encoded_path}"
        try:
            resp = self.session.get(dwc2_url, timeout=timeout)
            if resp.status_code == 200:
                logger.debug("Read via DWC2: %s", remote_path)
                return resp.text
            logger.debug("DWC2 read returned %s for %s", resp.status_code, remote_path)
        except requests.RequestException as e:
            logger.debug("DWC2 read failed: %s", e)

        # --- Attempt 2: Legacy rr_download --------------------------------
        rr_url = f"http://{self.address}/rr_download"
        try:
            resp = self.session.get(
                rr_url, params={"name": remote_path}, timeout=timeout
            )
            if resp.status_code == 200:
                logger.debug("Read via rr_download: %s", remote_path)
                return resp.text
            logger.debug(
                "rr_download returned %s for %s", resp.status_code, remote_path
            )
        except requests.RequestException as e:
            logger.debug("rr_download failed: %s", e)

        raise RuntimeError(
            f"Failed to read '{remote_path}' from {self.address}. "
            "Both /machine/file/ (DWC2) and /rr_download (legacy) endpoints failed."
        )
