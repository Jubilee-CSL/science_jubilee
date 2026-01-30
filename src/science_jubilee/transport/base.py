import json
from typing import Optional, Any


class BaseTransport:
    """Abstract transport interface for gcode exchange."""

    def send_gcode(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False):
        """Send a G-Code command and return the response string or None.
        If wait is True, transports should block until motion completes (e.g., by issuing M400).
        Implementations should block until a response is available or timeout/response_wait is reached.
        """
        raise NotImplementedError()

    def connect(self, timeout: Optional[float] = 5.0) -> bool:
        """Establish or verify connectivity for the transport.
        Returns True if reachable/ready, False otherwise.
        Implementations may perform a lightweight ping.
        """
        raise NotImplementedError()

    def send_gcode_json(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False) -> Optional[Any]:
        """Send a G-Code command and parse a JSON response.
        Returns the parsed JSON object or None if parsing fails or no response.
        This does not interpret firmware-specific keys; it simply returns the decoded JSON.
        """
        resp = self.send_gcode(cmd=cmd, timeout=timeout, response_wait=response_wait, wait=wait)
        if resp is None:
            return None
        try:
            return json.loads(resp)
        except Exception:
            return None

    def deck_is_clear(self) -> bool:
        """Return True if the deck is clear of obstacles according to the transport's knowledge.
        Hardware transports may require an external provider or always return False.
        Mock/digital twin transports can compute this from world state.
        """
        raise NotImplementedError()
