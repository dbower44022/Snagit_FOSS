"""Tests for RasterCutCommand and ResizeImageCommand."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF, QSizeF
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QApplication

from snapmock.commands.raster_commands import RasterCutCommand, ResizeImageCommand
from snapmock.core.scene import SnapScene
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


# --- RasterCutCommand ---


def test_raster_cut_erases_pixels(scene: SnapScene) -> None:
    """RasterCutCommand.redo() should erase pixels in the selection area."""
    # Create a red pixmap
    pm = QPixmap(100, 100)
    pm.fill(QColor(255, 0, 0))
    item = RasterRegionItem(pixmap=pm)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    item.setPos(0, 0)
    scene.addItem(item)

    # Cut a region in the middle
    sel_rect = QRectF(25, 25, 50, 50)
    cmd = RasterCutCommand(scene, sel_rect, QImage(), layer.layer_id)
    cmd.redo()

    # Check that the cut region has transparent pixels
    result_pixmap = item._pixmap  # noqa: SLF001
    img = result_pixmap.toImage()
    # Center pixel should be transparent
    center_color = img.pixelColor(50, 50)
    assert center_color.alpha() == 0

    # Corner pixel should still be red
    corner_color = img.pixelColor(5, 5)
    assert corner_color.red() == 255
    assert corner_color.alpha() == 255


def test_raster_cut_undo_restores_pixels(scene: SnapScene) -> None:
    """RasterCutCommand.undo() should restore the original pixmap."""
    pm = QPixmap(100, 100)
    pm.fill(QColor(0, 255, 0))
    item = RasterRegionItem(pixmap=pm)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    item.setPos(0, 0)
    scene.addItem(item)

    sel_rect = QRectF(10, 10, 80, 80)
    cmd = RasterCutCommand(scene, sel_rect, QImage(), layer.layer_id)
    cmd.redo()

    # Verify cut happened
    img = item._pixmap.toImage()  # noqa: SLF001
    assert img.pixelColor(50, 50).alpha() == 0

    # Undo
    cmd.undo()
    img = item._pixmap.toImage()  # noqa: SLF001
    assert img.pixelColor(50, 50).green() == 255
    assert img.pixelColor(50, 50).alpha() == 255


def test_raster_cut_ignores_items_on_other_layers(scene: SnapScene) -> None:
    """RasterCutCommand should only affect items on the specified layer."""
    pm = QPixmap(100, 100)
    pm.fill(QColor(0, 0, 255))
    item = RasterRegionItem(pixmap=pm)
    item.layer_id = "other_layer"
    item.setPos(0, 0)
    scene.addItem(item)

    layer = scene.layer_manager.active_layer
    assert layer is not None
    sel_rect = QRectF(0, 0, 100, 100)
    cmd = RasterCutCommand(scene, sel_rect, QImage(), layer.layer_id)
    cmd.redo()

    # Item should be unaffected
    img = item._pixmap.toImage()  # noqa: SLF001
    assert img.pixelColor(50, 50).blue() == 255


def test_raster_cut_no_intersection(scene: SnapScene) -> None:
    """RasterCutCommand should do nothing if selection doesn't intersect items."""
    pm = QPixmap(50, 50)
    pm.fill(QColor(255, 0, 0))
    item = RasterRegionItem(pixmap=pm)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    item.setPos(200, 200)
    scene.addItem(item)

    sel_rect = QRectF(0, 0, 50, 50)
    cmd = RasterCutCommand(scene, sel_rect, QImage(), layer.layer_id)
    cmd.redo()

    img = item._pixmap.toImage()  # noqa: SLF001
    assert img.pixelColor(25, 25).red() == 255


# --- ResizeImageCommand ---


def test_resize_image_scales_canvas(scene: SnapScene) -> None:
    """ResizeImageCommand should change the canvas size."""
    old_size = scene.canvas_size
    assert old_size.width() == 400

    new_size = QSizeF(800, 600)
    cmd = ResizeImageCommand(scene, new_size)
    cmd.redo()

    assert scene.canvas_size.width() == 800
    assert scene.canvas_size.height() == 600


def test_resize_image_scales_item_positions(scene: SnapScene) -> None:
    """Items should be repositioned proportionally."""
    rect_item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    rect_item.layer_id = layer.layer_id
    rect_item.setPos(100, 100)
    scene.addItem(rect_item)

    new_size = QSizeF(800, 600)  # 2x width, 2x height
    cmd = ResizeImageCommand(scene, new_size)
    cmd.redo()

    assert rect_item.pos().x() == pytest.approx(200, abs=1)
    assert rect_item.pos().y() == pytest.approx(200, abs=1)


def test_resize_image_scales_geometry(scene: SnapScene) -> None:
    """Items should have their geometry scaled."""
    rect_item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    rect_item.layer_id = layer.layer_id
    rect_item.setPos(0, 0)
    scene.addItem(rect_item)

    new_size = QSizeF(800, 600)  # 2x width, 2x height
    cmd = ResizeImageCommand(scene, new_size)
    cmd.redo()

    # Rectangle should be scaled
    assert rect_item._rect.width() == pytest.approx(100, abs=1)  # noqa: SLF001
    assert rect_item._rect.height() == pytest.approx(100, abs=1)  # noqa: SLF001


def test_resize_image_undo_restores(scene: SnapScene) -> None:
    """Undo should restore canvas size and item state."""
    rect_item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    rect_item.layer_id = layer.layer_id
    rect_item.setPos(100, 100)
    scene.addItem(rect_item)

    new_size = QSizeF(800, 600)
    cmd = ResizeImageCommand(scene, new_size)
    cmd.redo()
    cmd.undo()

    assert scene.canvas_size.width() == 400
    assert scene.canvas_size.height() == 300
    assert rect_item.pos().x() == pytest.approx(100, abs=1)
    assert rect_item.pos().y() == pytest.approx(100, abs=1)
    assert rect_item._rect.width() == pytest.approx(50, abs=1)  # noqa: SLF001


def test_resize_image_scales_raster_item(scene: SnapScene) -> None:
    """RasterRegionItem pixmap should be scaled."""
    pm = QPixmap(100, 100)
    pm.fill(QColor(255, 0, 0))
    item = RasterRegionItem(pixmap=pm)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    item.setPos(0, 0)
    scene.addItem(item)

    new_size = QSizeF(800, 600)  # 2x, 2x
    cmd = ResizeImageCommand(scene, new_size)
    cmd.redo()

    assert item._pixmap.width() == 200  # noqa: SLF001
    assert item._pixmap.height() == 200  # noqa: SLF001
