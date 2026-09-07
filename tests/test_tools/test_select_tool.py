"""Tests for SelectTool."""

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QTransform
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem
from snapmock.tools.select_tool import SelectTool, _State
from snapmock.ui.transform_handles import HandlePosition


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


def _add_text_item(scene: SnapScene, text: str = "Hello") -> TextItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = TextItem()
    item.text = text
    item.setPos(100, 100)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _begin_handle_drag(tool: SelectTool, item: TextItem) -> None:
    """Put the tool into HANDLE_DRAG state the way mouse_press does."""
    tool._state = _State.HANDLE_DRAG
    tool._handle_pos = HandlePosition.BOTTOM_CENTER
    tool._handle_item_originals = [(item, QPointF(item.pos()), QTransform(item.transform()))]
    tool._text_originals = {
        id(item): {
            "width": item._width,
            "height": item._height,
            "frame_height": item._frame_height(),
            "auto_size": item._auto_size,
            "font_size": item.text_document.defaultFont().pointSize(),
        }
    }


def test_vertical_resize_sets_explicit_height_and_disables_auto_size(scene: SnapScene) -> None:
    """Dragging a vertical handle locks the box height and turns auto-size off."""
    sm = SelectionManager(scene)
    tool = SelectTool()
    tool.activate(scene, sm)
    item = _add_text_item(scene)
    sm.select_items([item])
    assert item.auto_size is True
    orig_frame_h = item._frame_height()

    _begin_handle_drag(tool, item)
    tool._apply_text_resize(item, 1.0, 2.0, QTransform(item.transform()))
    tool._handle_transform_release()

    assert item.auto_size is False
    assert item.text_height == pytest.approx(orig_frame_h * 2.0)
    assert item._frame_height() == pytest.approx(orig_frame_h * 2.0)

    # The resize is one undoable step that restores auto-size.
    scene.command_stack.undo()
    assert item.auto_size is True
    assert item.text_height is None
    assert item._frame_height() == pytest.approx(orig_frame_h)

    scene.command_stack.redo()
    assert item.auto_size is False
    assert item.text_height == pytest.approx(orig_frame_h * 2.0)


def test_horizontal_resize_keeps_auto_size(scene: SnapScene) -> None:
    """A width-only reflow does not lock the height."""
    sm = SelectionManager(scene)
    tool = SelectTool()
    tool.activate(scene, sm)
    item = _add_text_item(scene)
    sm.select_items([item])
    orig_w = item.text_width

    _begin_handle_drag(tool, item)
    tool._apply_text_resize(item, 1.5, 1.0, QTransform(item.transform()))
    tool._handle_transform_release()

    assert item.auto_size is True
    assert item.text_height is None
    assert item.text_width == pytest.approx(orig_w * 1.5)
