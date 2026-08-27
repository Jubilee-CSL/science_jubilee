"""Plugin discovery for tools, mocks, configs, and twin assets.

External tool plugins register themselves with ``importlib.metadata`` entry
points. A plugin package's ``pyproject.toml`` declares up to five groups::

    [project.entry-points."science_jubilee.tools"]
    csl_fluo_tool = "csl_fluo_tool:FluorescenceTool"

    [project.entry-points."science_jubilee.tools.mocks"]
    csl_fluo_tool = "csl_fluo_tool:FluorescenceToolMock"

    [project.entry-points."science_jubilee.tools.configs"]
    csl_fluo_tool = "csl_fluo_tool.configs:__path__"

    [project.entry-points."science_jubilee.tools.twin_assets"]
    csl_fluo_tool = "csl_fluo_tool.twin_assets:__path__"

The entry-point *name* is the ``TOOL_KEY`` used everywhere: in ``M563 S"..."``
on the Duet, when looking up mocks/configs/twin assets, and as the
identifier reported by :class:`~science_jubilee.hal.tool_changer.ToolChanger`.

Naming rules (enforced at discovery time):

* lowercase ASCII letters, digits, and underscores only
* must start with a letter
* max 15 characters (RepRapFirmware ``M563 S`` limit)
* external plugins must not claim a name reserved for the mother repo
  (see :data:`RESERVED_MOTHER_REPO_KEYS`)
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from importlib.metadata import EntryPoint, entry_points, version
from typing import Dict, List, Optional, Type

from science_jubilee.tools.Tool import Tool, ToolConfigurationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entry-point group names
# ---------------------------------------------------------------------------

GROUP_TOOLS = "science_jubilee.tools"
GROUP_MOCKS = "science_jubilee.tools.mocks"
GROUP_CONFIGS = "science_jubilee.tools.configs"
GROUP_TWIN_ASSETS = "science_jubilee.tools.twin_assets"


# ---------------------------------------------------------------------------
# Naming rules
# ---------------------------------------------------------------------------

MOTHER_DIST = "science-jubilee"
MAX_KEY_LEN = 15
_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")

# Bare names owned by the mother repo. External plugins may not register these;
# they must namespace their key (e.g. ``csl_camera`` instead of ``camera``).
RESERVED_MOTHER_REPO_KEYS = frozenset(
    {
        "camera",
        "light",
        "neopixel",
        "toolhead_cam",
        "inoculator",
    }
)


def _validate_key(name: str, group: str, dist_name: Optional[str]) -> None:
    """Raise ``ToolConfigurationError`` if ``name`` violates the naming rules."""
    if not _KEY_REGEX.match(name):
        raise ToolConfigurationError(
            f"Invalid tool key {name!r} in group {group!r}: must match "
            f"{_KEY_REGEX.pattern} (lowercase letters, digits, underscores; "
            "must start with a letter)."
        )
    if len(name) > MAX_KEY_LEN:
        raise ToolConfigurationError(
            f"Tool key {name!r} in group {group!r} exceeds "
            f"{MAX_KEY_LEN} characters (RepRapFirmware M563 S limit)."
        )
    if name in RESERVED_MOTHER_REPO_KEYS and dist_name != MOTHER_DIST:
        raise ToolConfigurationError(
            f"Tool key {name!r} in group {group!r} is reserved for the "
            f"mother repo but was registered by distribution "
            f"{dist_name or '?'!r}. Prefix with your org tag, e.g. "
            f"'csl_{name}'."
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_eps(group: str):
    """Yield every entry point registered under ``group``."""
    try:
        return list(entry_points(group=group))
    except TypeError:  # Python < 3.10 API
        return list(entry_points().get(group, []))


def _distribution_name(ep: EntryPoint) -> Optional[str]:
    """Return the distribution (installed package) that provides ``ep``."""
    dist = getattr(ep, "dist", None)
    if dist is None:
        return None
    metadata = getattr(dist, "metadata", None)
    if metadata is None:
        return None
    return metadata["Name"]


def _load_class(ep: EntryPoint) -> Optional[Type[Tool]]:
    """Load ``ep`` and verify it points to a ``Tool`` subclass."""
    try:
        obj = ep.load()
    except Exception as exc:
        logger.warning("Failed to load tool plugin %r: %s", ep.name, exc)
        return None
    if not isinstance(obj, type) or not issubclass(obj, Tool):
        logger.warning(
            "Tool plugin %r does not resolve to a Tool subclass (got %r); skipping.",
            ep.name,
            obj,
        )
        return None
    return obj


def _load_path(ep: EntryPoint) -> Optional[str]:
    """Load an entry point that resolves to a filesystem path (or ``__path__``).

    Package ``__path__`` attributes are ``_NamespacePath`` / list-like objects
    exposing at least one directory. Callables returning a string are also
    accepted so plugins can compute the directory dynamically.
    """
    try:
        obj = ep.load()
    except Exception as exc:
        logger.warning("Failed to load asset directory %r: %s", ep.name, exc)
        return None
    if callable(obj):
        try:
            obj = obj()
        except Exception as exc:
            logger.warning("Asset directory factory %r raised: %s", ep.name, exc)
            return None
    if isinstance(obj, (str, os.PathLike)):
        return str(obj)
    # __path__ attributes (list-like)
    try:
        first = next(iter(obj))
    except (TypeError, StopIteration):
        logger.warning(
            "Asset entry point %r resolved to %r, expected str/path/__path__.",
            ep.name,
            obj,
        )
        return None
    return str(first)


# ---------------------------------------------------------------------------
# Public discovery API
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def discover_tool_classes() -> Dict[str, Type[Tool]]:
    """Return ``{TOOL_KEY: class}`` for every hardware tool plugin.

    Duplicate keys (same name registered by two distributions, or a mismatch
    between the entry-point name and ``cls.TOOL_KEY``) raise
    :class:`ToolConfigurationError` — the runtime cannot decide silently which
    plugin wins.
    """
    return _collect_tool_classes(GROUP_TOOLS)


@lru_cache(maxsize=1)
def discover_mock_classes() -> Dict[str, Type[Tool]]:
    """Return ``{TOOL_KEY: class}`` for every mock tool plugin."""
    return _collect_tool_classes(GROUP_MOCKS)


def _collect_tool_classes(group: str) -> Dict[str, Type[Tool]]:
    result: Dict[str, Type[Tool]] = {}
    seen_dists: Dict[str, str] = {}
    for ep in _iter_eps(group):
        cls = _load_class(ep)
        if cls is None:
            continue
        declared = getattr(cls, "TOOL_KEY", None)
        if declared is None:
            logger.warning(
                "Tool plugin %r (%s) has no TOOL_KEY class attribute; skipping.",
                ep.name,
                cls.__qualname__,
            )
            continue
        if declared != ep.name:
            raise ToolConfigurationError(
                f"Entry-point name {ep.name!r} does not match "
                f"{cls.__qualname__}.TOOL_KEY = {declared!r}."
            )
        _validate_key(ep.name, group, _distribution_name(ep))
        if ep.name in result:
            raise ToolConfigurationError(
                f"Duplicate tool key {ep.name!r} in group {group!r}: "
                f"registered by both {seen_dists.get(ep.name, '?')!r} "
                f"and {_distribution_name(ep) or '?'!r}."
            )
        result[ep.name] = cls
        seen_dists[ep.name] = _distribution_name(ep) or "?"
        _log_plugin_version(ep, cls)
    return result


def _log_plugin_version(ep: EntryPoint, cls: Type[Tool]) -> None:
    dist_name = _distribution_name(ep)
    plugin_version = None
    if dist_name:
        try:
            plugin_version = version(dist_name)
        except Exception:
            plugin_version = None
    try:
        sj_version = version("science-jubilee")
    except Exception:
        sj_version = "unknown"
    logger.debug(
        "Registered tool plugin key=%r class=%s dist=%s version=%s "
        "science_jubilee_version=%s",
        ep.name,
        cls.__qualname__,
        dist_name or "?",
        plugin_version or "?",
        sj_version,
    )


@lru_cache(maxsize=1)
def discover_config_dirs() -> Dict[str, str]:
    """Return ``{TOOL_KEY: dir}`` for plugin-shipped JSON config folders."""
    return _collect_paths(GROUP_CONFIGS)


@lru_cache(maxsize=1)
def discover_twin_asset_dirs() -> Dict[str, str]:
    """Return ``{TOOL_KEY: dir}`` for plugin-shipped digital-twin assets."""
    return _collect_paths(GROUP_TWIN_ASSETS)


def _collect_paths(group: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for ep in _iter_eps(group):
        path = _load_path(ep)
        if path is None:
            continue
        if ep.name in result:
            logger.warning(
                "Duplicate asset key %r in group %r; keeping first entry.",
                ep.name,
                group,
            )
            continue
        result[ep.name] = path
    return result


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def get_tool_class(name: str, *, mock: bool = False) -> Optional[Type[Tool]]:
    """Return the ``Tool`` subclass registered under ``name``.

    ``mock=True`` selects the mocks entry-point group. Returns ``None`` when
    no plugin is installed for that key.
    """
    table = discover_mock_classes() if mock else discover_tool_classes()
    return table.get(name)


def get_config_dir(name: str) -> Optional[str]:
    return discover_config_dirs().get(name)


def get_twin_asset_dir(name: str) -> Optional[str]:
    return discover_twin_asset_dirs().get(name)


def registered_tool_keys(*, mock: bool = False) -> List[str]:
    """List all currently-registered ``TOOL_KEY`` values."""
    table = discover_mock_classes() if mock else discover_tool_classes()
    return sorted(table.keys())


def clear_cache() -> None:
    """Reset all cached discovery tables (mostly useful in tests)."""
    for fn in (
        discover_tool_classes,
        discover_mock_classes,
        discover_config_dirs,
        discover_twin_asset_dirs,
    ):
        fn.cache_clear()
