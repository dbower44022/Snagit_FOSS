"""Tests for inter-tool interactions and edge cases."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication

from snapmock.commands.raster_commands import RasterCutCommand
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.tools.base_tool import BaseTool


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


@pytest.fixture()
def selection_manager(scene: SnapScene) -> SelectionManager:
    return SelectionManager(scene)


# --- Undo guard: first Ctrl+Z cancels active operation ---


def test_undo_guard_cancels_active_operation(scene: SnapScene) -> None:
    """Command stack undo should not fire while a tool has an active operation.

    The MainWindow._edit_undo() pattern checks is_active_operation and calls
    cancel() first. We test the BaseTool.is_active_operation property contract.
    """

    class FakeTool(BaseTool):
        def __init__(self) -> None:
            super().__init__()
            self._active = False
            self.cancel_called = False

        @property
        def tool_id(self) -> str:
            return "fake"

        @property
        def display_name(self) -> str:
            return "Fake"

        @property
        def is_active_operation(self) -> bool:
            return self._active

        def cancel(self) -> None:
            self.cancel_called = True
            self._active = False

    tool = FakeTool()
    tool._active = True
    assert tool.is_active_operation

    # Simulate what _edit_undo does
    if tool.is_active_operation:
        tool.cancel()

    assert tool.cancel_called
    assert not tool.is_active_operation


# --- Layer lock deselects items ---


def test_deselect_items_on_locked_layer(
    scene: SnapScene, selection_manager: SelectionManager
) -> None:
    """Items on a locked layer should be deselectable via selection manager."""
    item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    scene.addItem(item)

    # Select the item
    selection_manager.select(item)
    assert selection_manager.count == 1

    # Lock the layer — deselect items on it
    layer.locked = True
    # Simulate what _on_layer_lock_changed does
    for sel_item in list(selection_manager.items):
        if hasattr(sel_item, "layer_id") and sel_item.layer_id == layer.layer_id:
            selection_manager.toggle(sel_item)

    assert selection_manager.is_empty


def test_deselect_items_on_hidden_layer(
    scene: SnapScene, selection_manager: SelectionManager
) -> None:
    """Items on a hidden layer should be deselectable via selection manager."""
    item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    scene.addItem(item)

    selection_manager.select(item)
    assert selection_manager.count == 1

    # Simulate what _on_layer_visibility_changed does
    for sel_item in list(selection_manager.items):
        if hasattr(sel_item, "layer_id") and sel_item.layer_id == layer.layer_id:
            selection_manager.toggle(sel_item)

    assert selection_manager.is_empty


# --- RasterCutCommand + undo interaction ---


def test_raster_cut_redo_undo_cycle(scene: SnapScene) -> None:
    """Full redo/undo cycle via command stack for raster cut."""
    pm = QPixmap(100, 100)
    pm.fill(QColor(255, 0, 0))
    item = RasterRegionItem(pixmap=pm)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    item.setPos(0, 0)
    scene.addItem(item)

    from PyQt6.QtGui import QImage

    sel_rect = QRectF(10, 10, 80, 80)
    cmd = RasterCutCommand(scene, sel_rect, QImage(), layer.layer_id)

    # Push via command stack
    scene.command_stack.push(cmd)

    # Verify cut happened
    img = item._pixmap.toImage()  # noqa: SLF001
    assert img.pixelColor(50, 50).alpha() == 0

    # Undo via command stack
    scene.command_stack.undo()

    # Verify restored
    img = item._pixmap.toImage()  # noqa: SLF001
    assert img.pixelColor(50, 50).red() == 255
    assert img.pixelColor(50, 50).alpha() == 255


# --- BaseTool contract ---


def test_base_tool_default_status_hint() -> None:
    """BaseTool.status_hint should return empty string by default."""

    class MinimalTool(BaseTool):
        @property
        def tool_id(self) -> str:
            return "minimal"

        @property
        def display_name(self) -> str:
            return "Minimal"

    tool = MinimalTool()
    assert tool.status_hint == ""
    assert not tool.is_active_operation


def test_base_tool_cancel_is_safe() -> None:
    """Calling cancel on a tool with no active operation should be safe."""

    class MinimalTool(BaseTool):
        @property
        def tool_id(self) -> str:
            return "minimal"

        @property
        def display_name(self) -> str:
            return "Minimal"

    tool = MinimalTool()
    tool.cancel()  # Should not raise


# --- SelectionManager interactions ---


def test_selection_manager_toggle_deselect(
    scene: SnapScene, selection_manager: SelectionManager
) -> None:
    """Toggling a selected item should deselect it."""
    item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    scene.addItem(item)

    selection_manager.select(item)
    assert selection_manager.count == 1

    selection_manager.toggle(item)
    assert selection_manager.is_empty


def test_selection_manager_select_items_replaces(
    scene: SnapScene, selection_manager: SelectionManager
) -> None:
    """select_items should replace entire selection."""
    item1 = RectangleItem(rect=QRectF(0, 0, 50, 50))
    item2 = RectangleItem(rect=QRectF(60, 60, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item1.layer_id = layer.layer_id
    item2.layer_id = layer.layer_id
    scene.addItem(item1)
    scene.addItem(item2)

    selection_manager.select(item1)
    assert selection_manager.count == 1

    selection_manager.select_items([item2])
    assert selection_manager.count == 1
    assert item2 in selection_manager.items
    assert item1 not in selection_manager.items
