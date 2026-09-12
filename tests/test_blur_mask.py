"""A freeform blur region's alpha mask (Blur PRD 2.4, 2.5, 2.7, 5.1, 7.1).

Freeform blur decision 1, option A: the painted region is stored as a bitmap mask in
canvas pixels aligned to the region's rectangle, opaque where the region obscures.
"""

from __future__ import annotations

import base64
import zipfile
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import BlurMode, BlurRegionShape
from snapmock.core.scene import SnapScene
from snapmock.io.project_serializer import load_project, save_project
from snapmock.items.blur_item import BlurItem
from snapmock.items.mask_utils import INLINE_LIMIT, decode_mask_png
from snapmock.items.raster_region_item import RasterRegionItem


def _stripes(width: int = 300, height: int = 200, band: int = 4) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    for x in range(0, width, band):
        painter.fillRect(
            x, 0, band, height, QColor("#000000") if (x // band) % 2 else QColor("#ffffff")
        )
    painter.end()
    return QPixmap.fromImage(image)


def _scene(qapp: QApplication) -> SnapScene:
    scene = SnapScene(width=400, height=300)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, RasterRegionItem(_stripes()), layer.layer_id))
    return scene


def _painted(item: BlurItem, area: QRectF, blob: bool = False) -> None:
    """Paint *area* of the region's mask opaque, as the brush will (2.3)."""
    mask = item.ensure_mask().copy()
    painter = QPainter(mask)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if blob:
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(area)
    else:
        painter.fillRect(area, QColor(255, 255, 255))
    painter.end()
    item.alpha_mask = mask


def _freeform(scene: SnapScene, rect: QRectF = QRectF(0, 0, 100, 60)) -> BlurItem:
    item = BlurItem(rect=rect)
    item.region_shape = BlurRegionShape.FREEFORM
    item.setPos(40, 40)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def test_a_painted_mask_clips_the_effect_to_what_was_painted(qapp: QApplication) -> None:
    scene = _scene(qapp)
    item = _freeform(scene)
    item.blur_mode = BlurMode.SOLID
    item.fill_color = QColor("#123456")
    _painted(item, QRectF(0, 0, 50, 60))
    image, target = item.rendered(1.0)
    assert image is not None and target == QRectF(0, 0, 100, 60)
    assert image.pixelColor(20, 30).alpha() == 255  # painted: the fill shows
    assert image.pixelColor(20, 30).name() == "#123456"
    assert image.pixelColor(80, 30).alpha() == 0  # unpainted: the original shows
    # The rectangle is what is clicked and what a border follows (2.9)
    assert item.shape().boundingRect() == QRectF(0, 0, 100, 60)


def test_an_empty_mask_obscures_nothing(qapp: QApplication) -> None:
    scene = _scene(qapp)
    item = _freeform(scene)
    item.blur_mode = BlurMode.SOLID
    item.ensure_mask()
    image, _ = item.rendered(1.0)
    assert image is not None
    assert {image.pixelColor(x, 30).alpha() for x in range(0, 100, 10)} == {0}


def test_the_feather_softens_the_painted_edge(qapp: QApplication) -> None:
    scene = _scene(qapp)
    item = _freeform(scene)
    item.blur_mode = BlurMode.SOLID
    _painted(item, QRectF(0, 0, 50, 60))
    item.feather = 10.0
    image, target = item.rendered(1.0)
    assert image is not None and target == QRectF(-10, -10, 120, 80)
    inner = image.pixelColor(int(20 - target.x()), int(30 - target.y())).alpha()
    edge = image.pixelColor(int(50 - target.x()), int(30 - target.y())).alpha()
    outer = image.pixelColor(int(70 - target.x()), int(30 - target.y())).alpha()
    assert inner == 255 and 40 < edge < 220 and outer < edge


def test_inversion_over_a_mask_obscures_everything_unpainted(qapp: QApplication) -> None:
    scene = _scene(qapp)
    item = _freeform(scene)
    item.blur_mode = BlurMode.SOLID
    _painted(item, QRectF(0, 0, 50, 60))
    item.invert_mask = True
    image, target = item.rendered(1.0)
    assert image is not None
    assert target.contains(QRectF(-40, -40, 400, 300))  # the whole canvas
    painted = image.pixelColor(int(20 - target.x()), int(30 - target.y()))
    unpainted = image.pixelColor(int(80 - target.x()), int(30 - target.y()))
    away = image.pixelColor(int(-30 - target.x()), int(-30 - target.y()))
    assert painted.alpha() == 0  # what was painted stays clear
    assert unpainted.alpha() == 255 and away.alpha() == 255


def test_a_resize_resamples_the_mask(qapp: QApplication) -> None:
    scene = _scene(qapp)
    item = _freeform(scene)
    _painted(item, QRectF(0, 0, 50, 60))
    item.scale_geometry(2.0, 1.0)
    mask = item.alpha_mask
    assert mask is not None
    assert (mask.width(), mask.height()) == (200, 60)
    assert mask.pixelColor(40, 30).alpha() == 255  # the painted half grew with the region
    assert mask.pixelColor(160, 30).alpha() == 0


def test_the_mask_round_trips_inline_and_an_old_file_is_unaffected(
    qapp: QApplication, tmp_path: Path
) -> None:
    scene = _scene(qapp)
    item = _freeform(scene)
    _painted(item, QRectF(0, 0, 50, 60), blob=True)
    data = item.serialize()
    assert data["region_shape"] == "freeform"
    assert isinstance(data["alpha_mask_data"], str) and data["alpha_mask_data"]
    assert not data["alpha_mask_data"].startswith("file:")
    restored = BlurItem.deserialize(data)
    assert restored.region_shape is BlurRegionShape.FREEFORM
    mask = restored.alpha_mask
    assert mask is not None and (mask.width(), mask.height()) == (100, 60)
    assert mask.pixelColor(25, 30).alpha() == 255 and mask.pixelColor(95, 5).alpha() == 0

    path = tmp_path / "freeform.smk"
    save_project(scene, path)
    with zipfile.ZipFile(path) as zf:
        assert not [n for n in zf.namelist() if n.startswith("raster/")]
    loaded = load_project(path)
    blur = next(i for i in loaded.annotation_items() if isinstance(i, BlurItem))
    reloaded = blur.alpha_mask
    assert reloaded is not None and reloaded.pixelColor(25, 30).alpha() == 255

    old = BlurItem.deserialize({"type": "BlurItem", "rect": [0, 0, 50, 50], "blur_radius": 8})
    assert old.region_shape is BlurRegionShape.RECTANGLE and old.alpha_mask is None
    whole = BlurItem.deserialize({"rect": [0, 0, 9, 9], "region_shape": "whole_layer"})
    assert whole.region_shape is BlurRegionShape.RECTANGLE  # not built yet


def test_a_mask_past_the_inline_limit_goes_into_the_archive(
    qapp: QApplication, tmp_path: Path
) -> None:
    scene = _scene(qapp)
    item = _freeform(scene, QRectF(0, 0, 1200, 900))
    # Noise compresses poorly, so the PNG passes the 100 KB inline limit of 7.1
    rng = np.random.default_rng(7)
    alpha = rng.integers(0, 256, size=(900, 1200), dtype=np.uint8)
    pixels = np.empty((900, 1200, 4), dtype=np.uint8)
    for channel in range(4):
        pixels[:, :, channel] = alpha
    mask = QImage(
        pixels.tobytes(), 1200, 900, 1200 * 4, QImage.Format.Format_ARGB32_Premultiplied
    ).copy()
    item.alpha_mask = mask
    side = item.mask_side_file()
    assert side is not None
    entry, png = side
    assert entry == f"raster/blur_mask_{item.item_id}.png"
    assert len(png) >= INLINE_LIMIT
    assert item.serialize()["alpha_mask_data"] == f"file:{entry}"

    path = tmp_path / "big.smk"
    save_project(scene, path)
    with zipfile.ZipFile(path) as zf:
        assert entry in zf.namelist()
        stored = decode_mask_png(zf.read(entry))
    assert stored is not None and stored.size() == mask.size()
    loaded = load_project(path)
    blur = next(i for i in loaded.annotation_items() if isinstance(i, BlurItem))
    reloaded = blur.alpha_mask
    assert reloaded is not None and reloaded.size() == mask.size()
    assert reloaded.pixelColor(0, 0).alpha() == mask.pixelColor(0, 0).alpha()


def test_the_inline_field_is_a_base64_png(qapp: QApplication) -> None:
    scene = _scene(qapp)
    item = _freeform(scene)
    _painted(item, QRectF(10, 10, 20, 20))
    raw = base64.b64decode(item.serialize()["alpha_mask_data"], validate=True)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
