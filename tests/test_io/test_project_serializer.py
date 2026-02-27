"""Tests for project save/load."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.io.project_serializer import load_project, save_project
from snapmock.items.rectangle_item import RectangleItem


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def test_save_load_empty(scene: SnapScene, tmp_path: Path) -> None:
    path = tmp_path / "test.smk"
    save_project(scene, path)
    assert path.exists()
    loaded = load_project(path)
    assert loaded.canvas_size.width() == 800
    assert loaded.canvas_size.height() == 600
    assert loaded.layer_manager.count >= 1


def test_save_load_with_items(scene: SnapScene, tmp_path: Path) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(10, 20, 100, 50))
    item.setPos(30, 40)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))

    path = tmp_path / "with_items.smk"
    save_project(scene, path)
    loaded = load_project(path)

    from snapmock.items.base_item import SnapGraphicsItem

    loaded_items = [i for i in loaded.items() if isinstance(i, SnapGraphicsItem)]
    assert len(loaded_items) == 1
    loaded_item = loaded_items[0]
    assert isinstance(loaded_item, RectangleItem)
    assert loaded_item.pos().x() == 30
    assert loaded_item.pos().y() == 40


def test_loaded_project_is_clean(scene: SnapScene, tmp_path: Path) -> None:
    path = tmp_path / "clean.smk"
    save_project(scene, path)
    loaded = load_project(path)
    assert not loaded.command_stack.is_dirty
