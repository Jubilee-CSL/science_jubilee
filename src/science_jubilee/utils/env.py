import os
from pathlib import Path
from typing import Union


def load_env_file(env_file: Union[str, Path], override: bool = False) -> None:
    """Load key=value pairs from a .env-style file into os.environ.

    - Skips comments and blank lines
    - Does not override existing variables unless override=True
    """
    try:
        p = Path(env_file)
        if not p.exists():
            return
        with p.open("r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if override or key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Silent failure by design; tests may still proceed with existing env
        return


def ensure_env_from_file(key: str, env_file: Union[str, Path]) -> str:
    """Ensure an environment variable is set; if missing, load it from a file.

    Returns the environment value (which may remain empty if not found).
    """
    val = os.getenv(key)
    if val:
        return val
    load_env_file(env_file)
    return os.getenv(key, "")
