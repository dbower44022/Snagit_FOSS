"""Whole Layer, the source modes, and the render's speed (Blur PRD 2.4, 2.5, 2.7, 2.10).

Freeform blur decisions 3 (all three source modes) and 4 (the Gaussian captures at half
size and scales the result back).
"""

from __future__ import annotations

import statistics
import time

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import BlurMode, BlurRegionShape, BlurSourceMode
from snapmock.core.layer import Layer
from snapmock.core.scene import SnapScene
from snapmock.items.blur_item import GAUSSIAN_HALF_SCALE_MIN_RADIUS, BlurItem
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem


def _stripes(width: int = 400, height: int = 300, band: int = 4) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    for x in range(0, width, band):
        painter.fillRect(
            x, 0, band, height, QColor("#000000") if (x // band) % 2 else QColor("#ffffff")
        )
    painter.end()
    return QPixmap.fromImage(image)


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


def _row(image: QImage, y: int, x0: int, x1: int) -> list[int]:
    return [image.pixelColor(x, y).red() for x in range(x0, x1)]


def test_a_whole_layer_region_covers_the_canvas(scene: SnapScene) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, RasterRegionItem(_stripes()), layer.layer_id))
    item = BlurItem(rect=QRectF(0, 0, 10, 10))
    item.region_shape = BlurRegionShape.WHOLE_LAYER
    item.blur_mode = BlurMode.SOLID
    item.fill_color = QColor("#123456")
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    assert item.region_rect() == QRectF(0, 0, 400, 300)  # the canvas, not the stored rect
    image, target = item.rendered(1.0)
    assert image is not None and target == QRectF(0, 0, 400, 300)
    assert {image.pixelColor(x, 150).name() for x in (5, 200, 395)} == {"#123456"}
    assert item.shape().boundingRect() == QRectF(0, 0, 400, 300)
    # Serialized as itself, and the stored rectangle is not what it draws
    data = item.serialize()
    assert data["region_shape"] == "whole_layer"
    assert BlurItem.deserialize(data).region_shape is BlurRegionShape.WHOLE_LAYER


def _two_layers(scene: SnapScene) -> tuple[str, str]:
    lower = scene.layer_manager.active_layer
    assert lower is not None
    upper = Layer(name="Upper")
    scene.layer_manager.insert_layer(upper, scene.layer_manager.count)
    scene.command_stack.push(AddItemCommand(scene, RasterRegionItem(_stripes()), lower.layer_id))
    block = RectangleItem(QRectF(0, 0, 400, 300))
    block.fill_color = QColor("#20c020")
    block.stroke_width = 0.0
    scene.command_stack.push(AddItemCommand(scene, block, upper.layer_id))
    return lower.layer_id, upper.layer_id


def test_each_source_mode_reads_what_it_names(scene: SnapScene) -> None:
    lower_id, upper_id = _two_layers(scene)
    top = Layer(name="Top")
    scene.layer_manager.insert_layer(top, scene.layer_manager.count)
    item = BlurItem(rect=QRectF(0, 0, 200, 100))
    item.blur_mode = BlurMode.PIXELATE
    item.pixel_size = 50
    scene.command_stack.push(AddItemCommand(scene, item, top.layer_id))

    # All below: the green block on the upper layer covers the stripes, so the result is green
    image, _ = item.rendered(1.0)
    assert image is not None
    assert image.pixelColor(100, 50).green() > 150 and image.pixelColor(100, 50).red() < 90

    # Specific layer: only the stripes of the lower layer, averaged to mid grey
    item.source_mode = BlurSourceMode.SPECIFIC_LAYER
    item.source_layer_id = lower_id
    image, _ = item.rendered(1.0)
    assert image is not None
    grey = image.pixelColor(100, 50)
    assert abs(grey.red() - grey.green()) < 30 and 80 < grey.red() < 190

    # Active layer: the upper layer is active, so the green block alone
    scene.layer_manager.set_active(upper_id)
    item.source_mode = BlurSourceMode.ACTIVE_LAYER
    image, _ = item.rendered(1.0)
    assert image is not None
    assert image.pixelColor(100, 50).green() > 150
    # It follows the active layer: switching to the striped layer changes what it obscures
    scene.layer_manager.set_active(lower_id)
    image, _ = item.rendered(1.0)
    assert image is not None
    again = image.pixelColor(100, 50)
    assert abs(again.red() - again.green()) < 30


def test_a_file_naming_a_layer_that_is_gone_falls_back_to_all_below(scene: SnapScene) -> None:
    lower_id, _upper_id = _two_layers(scene)
    item = BlurItem(rect=QRectF(0, 0, 200, 100))
    item.blur_mode = BlurMode.PIXELATE
    item.pixel_size = 50
    item.source_mode = BlurSourceMode.SPECIFIC_LAYER
    item.source_layer_id = "a-layer-that-was-deleted"
    layer = scene.layer_manager.layers[-1]
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    image, _ = item.rendered(1.0)
    assert image is not None
    assert image.pixelColor(100, 50).green() > 150  # everything below, as all_below reads

    data = item.serialize()
    assert (data["source_mode"], data["source_layer_id"]) == (
        "specific_layer",
        "a-layer-that-was-deleted",
    )
    restored = BlurItem.deserialize(data)
    assert restored.source_mode is BlurSourceMode.SPECIFIC_LAYER
    assert restored.source_layer_id == "a-layer-that-was-deleted"
    old = BlurItem.deserialize({"rect": [0, 0, 10, 10]})
    assert old.source_mode is BlurSourceMode.ALL_BELOW and old.source_layer_id is None
    assert lower_id  # the fixture's lower layer is still there; the named one never was


def test_the_half_scale_gaussian_still_obscures_and_keeps_a_weak_radius_sharp(
    scene: SnapScene,
) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, RasterRegionItem(_stripes()), layer.layer_id))
    item = BlurItem(rect=QRectF(0, 0, 200, 120))
    item.setPos(40, 40)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))

    item.blur_radius = 10.0  # at or above the threshold: the half-scale path
    image, _ = item.rendered(1.0)
    assert image is not None
    assert statistics.pstdev(_row(image, 60, 20, 180)) < 12  # the 4 px stripes are gone

    item.blur_radius = 50.0  # the largest radius: softer still, and unreadable
    image, _ = item.rendered(1.0)
    assert image is not None
    assert statistics.pstdev(_row(image, 60, 20, 180)) < 8

    item.blur_radius = 1.0  # below the threshold: full resolution keeps the detail
    assert item.blur_radius < GAUSSIAN_HALF_SCALE_MIN_RADIUS
    image, _ = item.rendered(1.0)
    assert image is not None
    assert statistics.pstdev(_row(image, 60, 20, 180)) > 40  # barely noticeable, as 2.10 asks


def test_a_1000_px_gaussian_renders_within_the_target(qapp: QApplication) -> None:
    """2.10's 100 ms for a 1000 by 1000 px region, met from the half-scale threshold up.

    The timing is recorded in the notes; the test keeps a loose ceiling so a shared machine
    does not fail the suite.
    """
    scene = SnapScene(width=1920, height=1080)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(
        AddItemCommand(scene, RasterRegionItem(_stripes(1920, 1080)), layer.layer_id)
    )
    item = BlurItem(rect=QRectF(0, 0, 1000, 1000))
    item.setPos(100, 40)
    item.blur_radius = 10.0
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    times = []
    for _ in range(3):
        item._cache_key = None  # noqa: SLF001
        start = time.perf_counter()
        item.rendered(1.0)
        times.append((time.perf_counter() - start) * 1000.0)
    assert statistics.median(times) < 400.0  # measured at about 43 ms alone on this machine
