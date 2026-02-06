import logging
import time
import re
from typing import Optional, Callable

import requests
from requests.adapters import HTTPAdapter, Retry

from .base import BaseTransport


logger = logging.getLogger(__name__)


class HTTPTransport(BaseTransport):
    """HTTP transport for Duet/RepRapFirmware endpoints."""

    def __init__(self, address: str, session: Optional[requests.Session] = None, crash_detection: bool = False, crash_handler=None, deck_clear_provider: Optional[Callable[[], bool]] = None):
        self.address = address
        self.crash_detection = crash_detection
        self.crash_handler = crash_handler
        self.deck_clear_provider = deck_clear_provider

        if session is None:
            session = requests.Session()
            retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
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

    def send_gcode(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False):
        """Send a G-Code command over HTTP and return the response or None.
        If wait is True and the command implies motion, ensure completion with M400.
        """
        try:
            response = requests.post(f"http://{self.address}/machine/code", data=f"{cmd}", timeout=timeout).text
            # On success via /machine/code, optionally block until motion completes
            if wait and not cmd.strip().upper().startswith("M400"):
                _ = requests.post(f"http://{self.address}/machine/code", data="M400", timeout=timeout).text
            if "rejected" in response:
                raise requests.RequestException
        except requests.RequestException:
            try:
                # Query reply sequence
                reply_response = self.session.get(f"http://{self.address}/rr_model?key=seqs")
                logger.debug(f"MODEL response, status: {reply_response.status_code}, headers:{reply_response.headers}, content:{reply_response.content}")
                reply_count = reply_response.json()["result"]["reply"]

                buffer_response = self.session.get(f"http://{self.address}/rr_gcode?gcode={cmd}", timeout=timeout)
                logger.debug(f"GCODE response, status: {buffer_response.status_code}, headers:{buffer_response.headers}, content:{buffer_response.content}")

                tic = time.time()
                try_count = 0
                while True:
                    try:
                        new_reply_response = self.session.get(f"http://{self.address}/rr_model?key=seqs")
                        logger.debug(f"MODEL response, status: {new_reply_response.status_code}, headers:{new_reply_response.headers}, content:{new_reply_response.content}")
                        new_reply_count = new_reply_response.json()["result"]["reply"]

                        if new_reply_count != reply_count:
                            reply = self.session.get(f"http://{self.address}/rr_reply")
                            logger.debug(f"REPLY response, status: {reply.status_code}, headers:{reply.headers}, content:{reply.content}")
                            text = reply.text

                            responses = self._split_response_objects(text)
                            if len(responses) > 0:
                                text = responses[-1]
                            else:
                                text = None

                            if self.crash_detection and text and ("crash detected" in text):
                                logger.error("Jubilee crash detected")
                                if self.crash_handler is not None:
                                    try:
                                        self.crash_handler.handle_crash()
                                    except Exception as e:
                                        logger.exception(f"Crash handler failed: {e}")
                            # If requested, wait for motion completion via M400
                            if wait and not (cmd.strip().upper().startswith("M400")):
                                # Issue M400 and wait for its reply increment
                                m400_reply_response = self.session.get(f"http://{self.address}/rr_model?key=seqs")
                                m400_reply_count = m400_reply_response.json()["result"]["reply"]
                                self.session.get(f"http://{self.address}/rr_gcode?gcode=M400", timeout=timeout)
                                tic2 = time.time()
                                tries2 = 0
                                while True:
                                    try:
                                        new_m400_reply_response = self.session.get(f"http://{self.address}/rr_model?key=seqs")
                                        new_m400_reply_count = new_m400_reply_response.json()["result"]["reply"]
                                        if new_m400_reply_count != m400_reply_count:
                                            # consume rr_reply for M400
                                            _ = self.session.get(f"http://{self.address}/rr_reply")
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
                logger.error(f"Both `requests.post` and `requests.get` requests failed: {e}")
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
            answer = input("Confirm deck is clear and safe to home Z (y/N): ").strip().lower()
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
            letters = [m.group(1).upper() for m in re.finditer(r"([A-Za-z]):\s*-?\d+(?:\.\d+)?", text)]
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
