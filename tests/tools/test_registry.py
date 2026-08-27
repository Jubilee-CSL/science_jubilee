"""Tests for the tool plugin registry."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.hal.transport.mock import MockTransport
from science_jubilee.tools import registry as tool_registry
from science_jubilee.tools.Tool import Tool, ToolConfigurationError


class _DummyTool(Tool):
    TOOL_KEY: ClassVar[str] = "dummy_tool"


class _DummyToolMock(Tool):
    TOOL_KEY: ClassVar[str] = "dummy_tool"


class _MismatchedKeyTool(Tool):
    TOOL_KEY: ClassVar[str] = "wrong_name"


def _fake_ep(name: str, loaded_obj, dist_name: str | None = "test-dist"):
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = loaded_obj
    ep.dist = MagicMock()
    ep.dist.metadata = {"Name": dist_name} if dist_name else None
    return ep


@pytest.fixture(autouse=True)
def _reset_registry_cache():
    tool_registry.clear_cache()
    yield
    tool_registry.clear_cache()


def test_discover_returns_registered_tool_class():
    with patch.object(
        tool_registry, "_iter_eps", return_value=[_fake_ep("dummy_tool", _DummyTool)]
    ):
        table = tool_registry.discover_tool_classes()

    assert table == {"dummy_tool": _DummyTool}


def test_get_tool_class_selects_mock_group_when_requested():
    def fake_iter(group):
        if group == tool_registry.GROUP_TOOLS:
            return [_fake_ep("dummy_tool", _DummyTool)]
        if group == tool_registry.GROUP_MOCKS:
            return [_fake_ep("dummy_tool", _DummyToolMock)]
        return []

    with patch.object(tool_registry, "_iter_eps", side_effect=fake_iter):
        assert tool_registry.get_tool_class("dummy_tool") is _DummyTool
        assert tool_registry.get_tool_class("dummy_tool", mock=True) is _DummyToolMock


def test_missing_key_returns_none():
    with patch.object(tool_registry, "_iter_eps", return_value=[]):
        assert tool_registry.get_tool_class("nope") is None


def test_entry_point_name_must_match_tool_key():
    ep = _fake_ep("dummy_tool", _MismatchedKeyTool)
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        with pytest.raises(ToolConfigurationError, match="TOOL_KEY"):
            tool_registry.discover_tool_classes()


def test_duplicate_keys_from_different_distributions_raise():
    ep1 = _fake_ep("dummy_tool", _DummyTool, dist_name="pkg-a")
    ep2 = _fake_ep("dummy_tool", _DummyToolMock, dist_name="pkg-b")
    with patch.object(tool_registry, "_iter_eps", return_value=[ep1, ep2]):
        with pytest.raises(ToolConfigurationError, match="Duplicate tool key"):
            tool_registry.discover_tool_classes()


def test_class_without_tool_key_is_skipped():
    class _NoKey(Tool):
        pass

    ep = _fake_ep("nokey", _NoKey)
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        assert tool_registry.discover_tool_classes() == {}


def test_non_tool_class_is_skipped():
    class _NotATool:
        pass

    ep = _fake_ep("nottool", _NotATool)
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        assert tool_registry.discover_tool_classes() == {}


def test_asset_dir_discovery_accepts_string():
    ep = _fake_ep("dummy_tool", "/some/path")
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        assert tool_registry.discover_config_dirs() == {"dummy_tool": "/some/path"}


def test_asset_dir_discovery_accepts_namespace_path():
    ep = _fake_ep("dummy_tool", ["/pkg/twin_assets"])
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        assert tool_registry.discover_twin_asset_dirs() == {
            "dummy_tool": "/pkg/twin_assets"
        }


# ---------------------------------------------------------------------------
# Naming validation
# ---------------------------------------------------------------------------


class _LowercasedTool(Tool):
    TOOL_KEY: ClassVar[str] = "csl_pen"


@pytest.mark.parametrize("bad_name", ["CSL_pen", "csl.pen", "1pen", ""])
def test_invalid_key_shape_is_rejected(bad_name):
    class _T(Tool):
        TOOL_KEY: ClassVar[str] = bad_name

    ep = _fake_ep(bad_name, _T)
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        with pytest.raises(ToolConfigurationError, match="Invalid tool key"):
            tool_registry.discover_tool_classes()


def test_key_over_max_length_is_rejected():
    too_long = "csl_" + "a" * (tool_registry.MAX_KEY_LEN)  # 4 + 15 = 19 chars

    class _T(Tool):
        TOOL_KEY: ClassVar[str] = too_long

    ep = _fake_ep(too_long, _T)
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        with pytest.raises(ToolConfigurationError, match="exceeds"):
            tool_registry.discover_tool_classes()


def test_reserved_key_from_external_dist_is_rejected():
    class _T(Tool):
        TOOL_KEY: ClassVar[str] = "camera"

    ep = _fake_ep("camera", _T, dist_name="third-party-cam")
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        with pytest.raises(ToolConfigurationError, match="reserved"):
            tool_registry.discover_tool_classes()


def test_reserved_key_from_mother_repo_is_allowed():
    class _T(Tool):
        TOOL_KEY: ClassVar[str] = "camera"

    ep = _fake_ep("camera", _T, dist_name="science-jubilee")
    with patch.object(tool_registry, "_iter_eps", return_value=[ep]):
        assert tool_registry.discover_tool_classes() == {"camera": _T}


# ---------------------------------------------------------------------------
# ToolChanger integration
# ---------------------------------------------------------------------------


class _InoculatorLike(Tool):
    TOOL_KEY: ClassVar[str] = "inoculator"

    def __post_init__(self):
        super().__post_init__()
        self.custom_ready = True


def test_tool_changer_instantiates_registered_plugin():
    with patch.object(
        tool_registry,
        "_iter_eps",
        return_value=[
            _fake_ep("inoculator", _InoculatorLike, dist_name="science-jubilee")
        ],
    ):
        tool_registry.clear_cache()
        changer = ToolChanger(MockTransport())

    tool = changer.tools[0]
    assert isinstance(tool, _InoculatorLike)
    assert tool.name == "inoculator"
    assert tool.custom_ready is True


def test_tool_changer_falls_back_to_base_tool_when_plugin_missing(caplog):
    with patch.object(tool_registry, "_iter_eps", return_value=[]):
        tool_registry.clear_cache()
        with caplog.at_level("WARNING"):
            changer = ToolChanger(MockTransport())

    assert isinstance(changer.tools[0], Tool)
    assert type(changer.tools[0]) is Tool
    assert any("No plugin registered" in rec.message for rec in caplog.records)
