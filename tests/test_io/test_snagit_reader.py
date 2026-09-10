"""Snagit reader and writer: the Background layer type (follow-up step 2, decision 2)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPixmap

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.io.snagit_reader import load_snagx
from snapmock.io.snagit_writer import save_snagx
from snapmock.items.raster_region_item import RasterRegionItem


def _raster(colour: str, size: int = 8) -> RasterRegionItem:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(colour))
    return RasterRegionItem(pixmap=pixmap)


def _add(scene: SnapScene, item: RasterRegionItem, layer_id: str) -> None:
    scene.command_stack.push(AddItemCommand(scene, item, layer_id))


def _written_background(path: Path) -> QPixmap:
    with zipfile.ZipFile(path) as archive:
        page_name = json.loads(archive.read("index.json"))["Pages"][0]
        page = json.loads(archive.read(page_name))
        data = archive.read(page["CaptureBackgroundImage"])
    pixmap = QPixmap()
    assert pixmap.loadFromData(data, "PNG")
    return pixmap


def test_reader_types_the_background_layer(scene: SnapScene, tmp_path: Path) -> None:
    layer = scene.layer_manager.layers[0]
    _add(scene, _raster("red"), layer.layer_id)
    path = tmp_path / "typed.snagx"
    assert save_snagx(scene, path) == []
    loaded = load_snagx(path)
    layers = loaded.layer_manager.layers
    assert [layer.name for layer in layers] == ["Background", "Annotations"]
    assert [layer.layer_type for layer in layers] == ["Background", "Annotation"]
    assert loaded.layer_manager.background_layer is layers[0]
    assert loaded.layer_manager.active_layer is layers[1]


def test_writer_prefers_the_background_layers_raster(scene: SnapScene, tmp_path: Path) -> None:
    lm = scene.layer_manager
    marks = lm.add_layer("Marks")
    background = lm.layers[0]
    lm.set_layer_type(background.layer_id, "Background")
    photo = _raster("blue", 10)
    _add(scene, photo, background.layer_id)
    pasted = _raster("red", 6)
    pasted.setPos(QPointF(20, 20))
    _add(scene, pasted, marks.layer_id)
    path = tmp_path / "preferred.snagx"
    assert save_snagx(scene, path) == []
    assert _written_background(path).width() == 10  # the Background layer's raster


def test_writer_falls_back_to_the_lowest_raster(scene: SnapScene, tmp_path: Path) -> None:
    lm = scene.layer_manager
    background = lm.layers[0]
    lm.set_layer_type(background.layer_id, "Background")
    marks = lm.add_layer("Marks")
    # The Background layer holds no raster, so the lowest raster anywhere is written
    _add(scene, _raster("red", 6), marks.layer_id)
    path = tmp_path / "fallback.snagx"
    assert save_snagx(scene, path) == []
    assert _written_background(path).width() == 6
