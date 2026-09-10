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


# --- the three save-and-load findings of the Group and Ungroup kickoff (notes 16.10) ---


def test_every_item_type_keeps_its_transform_through_save_and_load(
    scene: SnapScene, tmp_path: Path
) -> None:
    """A handle resize, rotation, or skew sets the Qt transform; it survives the file."""
    from PyQt6.QtGui import QPixmap, QTransform

    from snapmock.io.project_serializer import ITEM_REGISTRY
    from snapmock.items.blur_item import BlurItem
    from snapmock.items.callout_item import CalloutItem
    from snapmock.items.numbered_step_item import NumberedStepItem
    from snapmock.items.raster_region_item import RasterRegionItem
    from snapmock.items.text_item import TextItem

    layer = scene.layer_manager.active_layer
    assert layer is not None
    items = [
        RectangleItem(rect=QRectF(0, 0, 50, 40)),
        TextItem(text="t"),
        CalloutItem(text="c"),
        BlurItem(rect=QRectF(0, 0, 30, 30)),
        NumberedStepItem(number=3),
        RasterRegionItem(pixmap=QPixmap(10, 10)),
    ]
    for n, item in enumerate(items):
        item.setPos(n * 100, 10)
        item.setTransform(QTransform().scale(2, 0.5).shear(0.1, 0).rotate(10 * n))
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    path = tmp_path / "transforms.smk"
    save_project(scene, path)
    loaded = load_project(path)
    by_id = {i.item_id: i for i in loaded.annotation_items()}
    assert set(by_id) == {i.item_id for i in items}
    for item in items:
        assert by_id[item.item_id].transform() == item.transform(), item.type_name
    # Every type writes the entry, and an entry without it reads as the identity
    assert all("transform" in item.serialize() for item in items)
    assert "transform" in ITEM_REGISTRY["GroupItem"]().serialize()
    plain = items[0].serialize()
    del plain["transform"]
    assert RectangleItem.deserialize(plain).transform().isIdentity()


def test_stacking_order_survives_save_and_load(scene: SnapScene, tmp_path: Path) -> None:
    """The loader gives every top-level item the z-value of its place in item_ids."""
    from PyQt6.QtGui import QColor

    from snapmock.commands.arrange_commands import apply_layer_z_values
    from snapmock.core.render_engine import RenderEngine

    layer = scene.layer_manager.active_layer
    assert layer is not None
    bottom = RectangleItem(rect=QRectF(0, 0, 100, 100))
    bottom.fill_color = QColor("red")
    bottom.setPos(10, 10)
    top = RectangleItem(rect=QRectF(0, 0, 100, 100))
    top.fill_color = QColor("blue")
    top.setPos(40, 40)
    for item in (bottom, top):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    apply_layer_z_values(scene, layer.layer_id)
    assert RenderEngine(scene).render_to_image().pixelColor(60, 60) == QColor("blue")
    path = tmp_path / "stack.smk"
    save_project(scene, path)
    loaded = load_project(path)
    assert RenderEngine(loaded).render_to_image().pixelColor(60, 60) == QColor("blue")
    z = {i.item_id: i.zValue() for i in loaded.annotation_items()}
    assert z[top.item_id] > z[bottom.item_id]
