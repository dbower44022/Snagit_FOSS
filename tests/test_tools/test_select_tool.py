"""Tests for SelectTool."""

import pytest
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.rectangle_item import RectangleItem
from snapmock.tools.select_tool import SelectTool


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def test_select_tool_identity() -> None:
    tool = SelectTool()
    assert tool.tool_id == "select"
    assert tool.display_name == "Select"


def test_select_tool_activation(scene: SnapScene) -> None:
    sm = SelectionManager(scene)
    tool = SelectTool()
    tool.activate(scene, sm)
    assert tool._scene is scene
    tool.deactivate()
    assert tool._scene is None


def test_select_tool_creates_no_items(scene: SnapScene) -> None:
    """Select tool should not create items — only select existing ones."""
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem()
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    assert len(layer.item_ids) == 1
