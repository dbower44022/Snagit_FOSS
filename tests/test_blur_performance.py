"""The Blur tool's Performance rows (Blur PRD 2.10, 8.1).

Decision 4 of the Eyedropper and Blur performance work, option C: the blur itself is
made cheaper rather than moved to a background thread. The three changes are float32 in
place of float64, all four colour channels in one array, and a direct sum of shifted
slices in place of the cumulative sums while the box is narrow. The measured figures are
in ``docs/Eyedropper-Blur-Performance-Implementation.md``, Section 4; the ceilings here
are loose, so a machine shared with another test run does not fail the suite.
"""

from __future__ import annotations

import statistics
import time

import numpy as np
import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import BlurMode
from snapmock.core.scene import SnapScene
from snapmock.items import shadow
from snapmock.items.blur_item import GAUSSIAN_HALF_SCALE_MIN_RADIUS, BlurItem
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.shadow import blur_image


def _stripes(width: int, height: int, band: int = 4) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    for x in range(0, width, band):
        painter.fillRect(
            x, 0, band, height, QColor("#000000") if (x // band) % 2 else QColor("#ffffff")
        )
    painter.end()
    return QPixmap.fromImage(image)


def _bytes_of(image: QImage) -> np.ndarray:
    image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    pointer = image.bits()
    assert pointer is not None
    pointer.setsize(image.sizeInBytes())
    raw = np.frombuffer(pointer.asstring(image.sizeInBytes()), dtype=np.uint8)
    return raw.reshape(image.height(), image.bytesPerLine())[:, : image.width() * 4].copy()


def _row(image: QImage, y: int, x0: int, x1: int) -> list[int]:
    return [image.pixelColor(x, y).red() for x in range(x0, x1)]


def _blur_region(canvas: int, region: int, radius: float) -> tuple[SnapScene, BlurItem]:
    scene = SnapScene(width=canvas, height=canvas)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(
        AddItemCommand(scene, RasterRegionItem(_stripes(canvas, canvas)), layer.layer_id)
    )
    item = BlurItem(rect=QRectF(0, 0, region, region))
    item.setPos(20, 20)
    item.blur_mode = BlurMode.GAUSSIAN
    item.blur_radius = radius
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return scene, item


def _median_render_ms(item: BlurItem, runs: int = 3) -> float:
    times = []
    for _ in range(runs):
        item._cache_key = None  # noqa: SLF001
        start = time.perf_counter()
        item.rendered(1.0)
        times.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(times)


def test_the_narrow_box_and_the_cumulative_sum_agree(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The two box paths are the same blur; the narrow one is only faster.

    A radius of 1 takes the direct sum of shifted slices. With the threshold lowered the
    same radius takes the cumulative sum, and the two results must agree: float32 leaves
    at most one level of 255 between them where a value falls on a rounding boundary.
    """
    source = _stripes(300, 220).toImage()
    direct = _bytes_of(blur_image(source, 1.0)).astype(int)
    monkeypatch.setattr(shadow, "_DIRECT_BOX_MAX", 0)
    summed = _bytes_of(blur_image(source, 1.0)).astype(int)
    assert int(np.abs(direct - summed).max()) <= 1


def test_a_1000_px_gaussian_meets_the_target_at_every_radius(qapp: QApplication) -> None:
    """2.10's 100 ms for a 1000 by 1000 px region, now met below radius 4 as well.

    Measured alone on the development machine: 55 ms at radius 1, 57 ms at radius 2,
    72 ms at radius 3, 11 ms at radius 4, 29 ms at radius 10, and 42 ms at radius 50,
    against 163, 161, about 190, 37, 40, and 50 ms before this work.
    """
    for radius in (1.0, 3.0, 10.0, 50.0):
        _scene, item = _blur_region(1920, 1000, radius)
        assert _median_render_ms(item) < 400.0, f"radius {radius} is slower than the ceiling"


def test_the_full_resolution_blur_obscures_at_radius_3_and_keeps_radius_1_sharp(
    qapp: QApplication,
) -> None:
    """The quality 2.10's acceptance rows ask for, on the path that changed.

    Radius 1 stays barely noticeable and radius 3 — the widest radius that still renders
    at full resolution — already flattens 4 px stripes, so nothing about the faster
    arithmetic weakened the blur.
    """
    _scene, item = _blur_region(400, 200, 1.0)
    assert item.blur_radius < GAUSSIAN_HALF_SCALE_MIN_RADIUS
    image, _ = item.rendered(1.0)
    assert image is not None
    assert statistics.pstdev(_row(image, 60, 20, 180)) > 40  # the stripes are still there

    item.blur_radius = 3.0
    assert item.blur_radius < GAUSSIAN_HALF_SCALE_MIN_RADIUS
    image, _ = item.rendered(1.0)
    assert image is not None
    assert statistics.pstdev(_row(image, 60, 20, 180)) < 25  # and now they are not
