"""Image placement: the background layer on an empty project (follow-up step 5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QFileDialog

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.io.importer import import_image, place_image, takes_background
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow


def _pixmap(w: int = 30, h: int = 20) -> QPixmap:
    pixmap = QPixmap(w, h)
    pixmap.fill(QColor("red"))
    return pixmap


def _regions(scene: SnapScene) -> list[RasterRegionItem]:
    return [i for i in scene.annotation_items() if isinstance(i, RasterRegionItem)]


def _add_rect(scene: SnapScene) -> RectangleItem:
    item = RectangleItem(QRectF(0, 0, 10, 10))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def test_empty_project_takes_the_image_as_its_background(scene: SnapScene) -> None:
    lm = scene.layer_manager
    marks = lm.layers[0]
    before = (scene.canvas_size.width(), scene.canvas_size.height())
    assert takes_background(scene)
    item = place_image(scene, _pixmap(), QPointF(100, 100))
    assert item is not None and item.pos() == QPointF(0, 0)
    background = lm.layers[0]
    assert background.is_background and background.name == "Background"
    assert lm.background_layer is background and lm.count == 2
    assert item.layer_id == background.layer_id and background.item_ids == [item.item_id]
    assert item.zValue() == background.z_base
    # The canvas takes the image's size exactly (General UI PRD 6.2); the active layer stays
    assert (scene.canvas_size.width(), scene.canvas_size.height()) == (30, 20)
    assert lm.active_layer is marks
    assert scene.command_stack.undo_text == "Add background image"
    assert not takes_background(scene)
    scene.command_stack.undo()
    assert lm.count == 1 and lm.background_layer is None and _regions(scene) == []
    assert (scene.canvas_size.width(), scene.canvas_size.height()) == before
    assert lm.active_layer is marks
    scene.command_stack.redo()
    assert lm.background_layer is background and _regions(scene) == [item]


def test_project_with_content_takes_a_region_on_the_active_layer(scene: SnapScene) -> None:
    lm = scene.layer_manager
    _add_rect(scene)
    before = (scene.canvas_size.width(), scene.canvas_size.height())
    assert not takes_background(scene)
    item = place_image(scene, _pixmap(), QPointF(40, 50))
    assert item is not None and item.pos() == QPointF(40, 50)
    assert item.layer_id == lm.active_layer_id and lm.count == 1
    assert (scene.canvas_size.width(), scene.canvas_size.height()) == before
    assert scene.command_stack.undo_text == "Add RasterRegionItem"


def test_project_with_a_background_layer_never_replaces_it(scene: SnapScene) -> None:
    """Silence 6: a second image is a raster region, whatever the Background layer holds."""
    lm = scene.layer_manager
    marks = lm.add_layer("Marks")
    lm.set_active(marks.layer_id)
    first = place_image(scene, _pixmap(), QPointF(0, 0))
    assert first is not None and lm.background_layer is not None
    second = place_image(scene, _pixmap(10, 10), QPointF(5, 5))
    assert second is not None and second.layer_id == marks.layer_id
    assert lm.count == 3 and (scene.canvas_size.width(), scene.canvas_size.height()) == (30, 20)


def test_null_pixmap_places_nothing(scene: SnapScene) -> None:
    assert place_image(scene, QPixmap(), QPointF(0, 0)) is None
    assert scene.layer_manager.count == 1 and scene.command_stack.undo_text == ""


def test_import_image_route(
    main_window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "shot.png"
    assert _pixmap(50, 40).save(str(path), "PNG")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), "Images"))
    scene = main_window.scene
    assert main_window._file_import_image()  # noqa: SLF001
    assert scene.layer_manager.background_layer is scene.layer_manager.layers[0]
    assert (scene.canvas_size.width(), scene.canvas_size.height()) == (50, 40)
    # A second import on the project with a background is a region at the origin
    assert main_window._file_import_image()  # noqa: SLF001
    regions = _regions(scene)
    assert len(regions) == 2 and scene.layer_manager.count == 2
    active = scene.layer_manager.active_layer_id
    assert [r.layer_id for r in regions if r.layer_id == active] and regions[0].pos() == QPointF(
        0, 0
    )
    # A cancelled dialog imports nothing
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    assert not main_window._file_import_image()  # noqa: SLF001
    assert import_image(scene, tmp_path / "missing.png") is None
