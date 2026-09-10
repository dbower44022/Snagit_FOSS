"""Tests for ClipboardManager."""

import pytest
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow


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


def test_paste_gives_the_copy_new_ids(main_window: MainWindow) -> None:
    """A pasted item is a new item; the original keeps its id (notes Section 16.10)."""
    from snapmock.commands.group_commands import GroupItemsCommand
    from snapmock.items.group_item import GroupItem

    scene = main_window.scene
    layer = scene.layer_manager.active_layer
    assert layer is not None
    a, b = RectangleItem(), RectangleItem()
    b.setPos(200, 0)
    for item in (a, b):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    command = GroupItemsCommand(scene, [a, b], main_window.selection_manager)
    scene.command_stack.push(command)
    group = command.group
    assert group is not None
    main_window._edit_copy()  # noqa: SLF001
    main_window._edit_paste()  # noqa: SLF001
    pasted = [i for i in scene.annotation_items() if i is not group]
    assert len(pasted) == 1 and isinstance(pasted[0], GroupItem)
    old_ids = {group.item_id, a.item_id, b.item_id}
    new_ids = {pasted[0].item_id} | {m.item_id for m in pasted[0].descendants()}
    assert len(new_ids) == 3 and old_ids.isdisjoint(new_ids)
    assert len({i.item_id for i in scene.all_annotation_items()}) == 6
