"""Tests for ToolManager."""

import pytest
from PyQt6.QtWidgets import QApplication

from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.tools.rectangle_tool import RectangleTool
from snapmock.tools.select_tool import SelectTool
from snapmock.tools.tool_manager import ToolManager


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


@pytest.fixture()
def tool_manager(scene: SnapScene) -> ToolManager:
    sm = SelectionManager(scene)
    tm = ToolManager(scene, sm)
    tm.register(SelectTool())
    tm.register(RectangleTool())
    return tm


def test_register_tools(tool_manager: ToolManager) -> None:
    assert "select" in tool_manager.tool_ids
    assert "rectangle" in tool_manager.tool_ids


def test_activate_tool(tool_manager: ToolManager) -> None:
    tool_manager.activate("select")
    assert tool_manager.active_tool_id == "select"


def test_switch_tools(tool_manager: ToolManager) -> None:
    tool_manager.activate("select")
    tool_manager.activate("rectangle")
    assert tool_manager.active_tool_id == "rectangle"


def test_activate_unknown_tool(tool_manager: ToolManager) -> None:
    tool_manager.activate("select")
    tool_manager.activate("nonexistent")
    assert tool_manager.active_tool_id == "select"


def test_tool_changed_signal(tool_manager: ToolManager) -> None:
    received: list[str] = []
    tool_manager.tool_changed.connect(received.append)
    tool_manager.activate("rectangle")
    assert received == ["rectangle"]
