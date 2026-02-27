"""Integration tests — verify end-to-end workflows across subsystems."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.io.exporter import export_png
from snapmock.io.project_serializer import load_project, save_project
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.ellipse_item import EllipseItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.tools.tool_manager import ToolManager


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def test_add_undo_redo_cycle(scene: SnapScene) -> None:
    """Items can be added, undone, and redone via the command stack."""
    layer = scene.layer_manager.active_layer
    assert layer is not None

    item = RectangleItem(rect=QRectF(0, 0, 100, 50))
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))

    snap_items = [i for i in scene.items() if isinstance(i, SnapGraphicsItem)]
    assert len(snap_items) == 1

    scene.command_stack.undo()
    snap_items = [i for i in scene.items() if isinstance(i, SnapGraphicsItem)]
    assert len(snap_items) == 0

    scene.command_stack.redo()
    snap_items = [i for i in scene.items() if isinstance(i, SnapGraphicsItem)]
    assert len(snap_items) == 1


def test_copy_paste_via_clipboard(scene: SnapScene) -> None:
    """Items can be copied and pasted through the clipboard manager."""
    layer = scene.layer_manager.active_layer
    assert layer is not None

    item = EllipseItem(rect=QRectF(0, 0, 80, 80))
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))

    clipboard = ClipboardManager(scene)
    clipboard.copy_items([item])
    assert clipboard.has_internal

    data = clipboard.paste_items()
    assert len(data) == 1
    assert data[0]["type"] == "EllipseItem"


def test_save_load_preserves_items(scene: SnapScene, tmp_path: Path) -> None:
    """A round-trip save/load preserves layer and item state."""
    layer = scene.layer_manager.active_layer
    assert layer is not None

    r = RectangleItem(rect=QRectF(10, 20, 100, 50))
    r.setPos(30, 40)
    scene.command_stack.push(AddItemCommand(scene, r, layer.layer_id))

    e = EllipseItem(rect=QRectF(0, 0, 60, 60))
    e.setPos(200, 100)
    scene.command_stack.push(AddItemCommand(scene, e, layer.layer_id))

    path = tmp_path / "integration.smk"
    save_project(scene, path)
    loaded = load_project(path)

    loaded_items = [i for i in loaded.items() if isinstance(i, SnapGraphicsItem)]
    assert len(loaded_items) == 2
    types = {type(i).__name__ for i in loaded_items}
    assert types == {"RectangleItem", "EllipseItem"}
    assert not loaded.command_stack.is_dirty


def test_export_after_modifications(scene: SnapScene, tmp_path: Path) -> None:
    """Exporting works after adding items to the scene."""
    layer = scene.layer_manager.active_layer
    assert layer is not None

    item = RectangleItem(rect=QRectF(0, 0, 200, 100))
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))

    path = tmp_path / "out.png"
    export_png(scene, path)
    assert path.exists()
    assert path.stat().st_size > 0


def test_tool_manager_integration(scene: SnapScene) -> None:
    """ToolManager registers and switches tools correctly in context."""
    from snapmock.tools.rectangle_tool import RectangleTool
    from snapmock.tools.select_tool import SelectTool

    selection = SelectionManager(scene)
    mgr = ToolManager(scene, selection)
    mgr.register(SelectTool())
    mgr.register(RectangleTool())

    mgr.activate("select")
    assert mgr.active_tool_id == "select"

    mgr.activate("rectangle")
    assert mgr.active_tool_id == "rectangle"


def test_layer_operations_with_items(scene: SnapScene) -> None:
    """Adding a second layer and items to each layer keeps them independent."""
    layer1 = scene.layer_manager.active_layer
    assert layer1 is not None

    item1 = RectangleItem(rect=QRectF(0, 0, 50, 50))
    scene.command_stack.push(AddItemCommand(scene, item1, layer1.layer_id))

    layer2 = scene.layer_manager.add_layer("Layer 2")
    item2 = EllipseItem(rect=QRectF(0, 0, 80, 80))
    scene.command_stack.push(AddItemCommand(scene, item2, layer2.layer_id))

    all_items = [i for i in scene.items() if isinstance(i, SnapGraphicsItem)]
    assert len(all_items) == 2

    assert item1.layer_id == layer1.layer_id
    assert item2.layer_id == layer2.layer_id


def test_dirty_flag_lifecycle(scene: SnapScene) -> None:
    """The dirty flag tracks unsaved changes correctly."""
    assert not scene.command_stack.is_dirty

    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    assert scene.command_stack.is_dirty

    scene.command_stack.mark_clean()
    assert not scene.command_stack.is_dirty

    scene.command_stack.undo()
    assert scene.command_stack.is_dirty
