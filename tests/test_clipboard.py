"""Tests for ClipboardManager."""

import pytest
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


@pytest.fixture()
def clipboard(scene: SnapScene) -> ClipboardManager:
    return ClipboardManager(scene)


def test_clipboard_initially_empty(clipboard: ClipboardManager) -> None:
    assert not clipboard.has_internal
    assert clipboard.paste_items() == []


def test_copy_items(scene: SnapScene, clipboard: ClipboardManager) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem()
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    clipboard.copy_items([item])
    assert clipboard.has_internal
    data = clipboard.paste_items()
    assert len(data) == 1
    assert data[0]["type"] == "RectangleItem"


def test_clear_clipboard(scene: SnapScene, clipboard: ClipboardManager) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem()
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    clipboard.copy_items([item])
    clipboard.clear()
    assert not clipboard.has_internal
