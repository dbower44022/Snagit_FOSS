"""StampItem (Numbered Steps, Stamps & Emoji PRD 3.5, 3.9, 3.10, 5.2, 7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import MARKER_MIN_HIT_SIZE
from snapmock.core.scene import SnapScene
from snapmock.core.stamp_library import (
    BUILTIN,
    CUSTOM,
    EMBEDDED,
    StampLibrary,
    set_stamp_library,
)
from snapmock.io.project_serializer import ITEM_REGISTRY, load_project, save_project
from snapmock.items.shadow import SHADOW_KEYS
from snapmock.items.stamp_item import StampItem

SQUARE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
    '<rect x="0" y="0" width="64" height="64" fill="#FF0000"/>'
    '<rect x="16" y="16" width="32" height="32" fill="#0000FF"/></svg>'
)
WIDE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="32" viewBox="0 0 64 32">'
    '<rect x="0" y="0" width="64" height="32" fill="#FF0000"/></svg>'
)


@pytest.fixture()
def library(tmp_path: Path) -> StampLibrary:
    lib = StampLibrary(custom_dir=tmp_path / "custom")
    set_stamp_library(lib)
    yield lib  # type: ignore[misc]
    set_stamp_library(None)


def _render(item: StampItem, size: int = 200) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.translate(size / 2, size / 2)
    item.paint(painter, None)
    painter.end()
    return image


def _custom(library: StampLibrary, tmp_path: Path, svg: str = SQUARE_SVG, name: str = "sq"):  # type: ignore[no-untyped-def]
    path = tmp_path / f"{name}.svg"
    path.write_text(svg)
    return library.import_svg(path, name=name.title())


# --- the item (Sections 3.5 and 5.2) ---


def test_stamp_item_defaults_and_registry(qapp: QApplication, library: StampLibrary) -> None:
    item = StampItem("status/approved")
    assert item.stamp_id == "status/approved"
    assert item.stamp_source == BUILTIN
    assert item.stamp_name == "Approved"
    assert item.stamp_size == 48.0
    assert item.default_size == 48.0
    assert item.stamp_color.name() == "#cc0000"
    assert item.stamp_secondary_color.name() == "#ffffff"
    assert item.colorizable is True
    assert item.shadow_enabled is False
    assert item.opacity() == 1.0
    assert not item.is_missing
    assert item.type_name == "Stamp"
    assert ITEM_REGISTRY["StampItem"] is StampItem
    assert item.stamp_rect() == QRectF(-24, -24, 48, 48)


def test_stamp_size_is_clamped_and_the_aspect_follows_the_svg(
    qapp: QApplication, library: StampLibrary, tmp_path: Path
) -> None:
    info = _custom(library, tmp_path, WIDE_SVG, "wide")
    item = StampItem(info.id, stamp_size=64.0)
    rect = item.stamp_rect()
    assert rect.width() == pytest.approx(64.0)
    assert rect.height() == pytest.approx(32.0)
    item.stamp_size = 4.0
    assert item.stamp_size == 16.0
    item.stamp_size = 9999.0
    assert item.stamp_size == 512.0


def test_shape_is_the_rectangle_with_the_24_px_minimum(
    qapp: QApplication, library: StampLibrary
) -> None:
    small = StampItem("status/approved", stamp_size=16.0)
    rect = small.shape().boundingRect()
    assert rect.width() >= MARKER_MIN_HIT_SIZE and rect.height() >= MARKER_MIN_HIT_SIZE
    big = StampItem("status/approved", stamp_size=64.0)
    assert big.shape().boundingRect() == QRectF(-32, -32, 64, 64)
    assert big.boundingRect().contains(big.shape().boundingRect())


# --- rendering (Section 3.9) ---


def test_colorizable_stamp_recolours_and_a_fixed_one_does_not(
    qapp: QApplication, library: StampLibrary, tmp_path: Path
) -> None:
    info = _custom(library, tmp_path)
    item = StampItem(info.id, stamp_size=100.0)
    item.stamp_color = QColor("#00aa00")
    item.stamp_secondary_color = QColor("#0000aa")
    image = _render(item)
    assert image.pixelColor(100 - 45, 100).name() == "#00aa00"  # the outer square
    assert image.pixelColor(100, 100).name() == "#0000aa"  # the inner square
    item.colorizable = False
    image = _render(item)
    assert image.pixelColor(100 - 45, 100).name() == "#ff0000"
    assert image.pixelColor(100, 100).name() == "#0000ff"


def test_flip_and_shadow_render(qapp: QApplication, library: StampLibrary, tmp_path: Path) -> None:
    info = _custom(library, tmp_path, WIDE_SVG.replace('<rect x="0"', '<rect x="32"'), "half")
    item = StampItem(info.id, stamp_size=100.0)
    plain = _render(item)
    assert plain.pixelColor(100 + 20, 100).name() == "#cc0000"  # the right half is painted
    assert plain.pixelColor(100 - 20, 100).name() == "#ffffff"
    item.flip_horizontal = True
    flipped = _render(item)
    assert flipped.pixelColor(100 - 20, 100).name() == "#cc0000"
    assert flipped.pixelColor(100 + 20, 100).name() == "#ffffff"
    item.flip_horizontal = False
    item.shadow_enabled = True
    item.shadow_offset_x = 10.0
    item.shadow_offset_y = 10.0
    item.shadow_blur = 1.0
    shadowed = _render(item)
    assert shadowed.pixelColor(100 + 55, 100 + 30).name() != "#ffffff"
    assert item.boundingRect().width() > 100.0


def test_missing_stamp_renders_the_placeholder(qapp: QApplication, library: StampLibrary) -> None:
    item = StampItem("status/no-such-stamp", stamp_size=64.0)
    assert item.is_missing
    assert item.stamp_name == "No Such Stamp"
    image = _render(item)
    # The placeholder's dashed frame sits 6 of 64 units inside the stamp rect
    assert any(image.pixelColor(x, 100 - 32 + 6).name() != "#ffffff" for x in range(70, 130))


# --- serialization (Sections 5.2 and 7.2) ---


def test_builtin_stamp_serializes_by_id_without_svg(
    qapp: QApplication, library: StampLibrary
) -> None:
    item = StampItem("status/approved", stamp_size=40.0)
    item.setPos(10, 20)
    item.stamp_color = QColor("#112233")
    item.flip_vertical = True
    item.shadow_enabled = True
    data = item.serialize()
    assert data["type"] == "StampItem"
    assert data["stamp_source"] == BUILTIN
    assert "svg_data" not in data
    assert {
        "stamp_id",
        "stamp_size",
        "stamp_color",
        "stamp_secondary_color",
        "colorizable",
    } <= set(data)
    assert set(SHADOW_KEYS) <= set(data)
    restored = StampItem.deserialize(data)
    assert restored.stamp_id == "status/approved"
    assert restored.stamp_name == "Approved"
    assert restored.pos() == QPointF(10, 20)
    assert restored.stamp_color.name() == "#112233"
    assert restored.flip_vertical is True
    assert restored.shadow_enabled is True
    assert not restored.is_missing
    assert restored.serialize() == data


def test_custom_stamp_is_embedded_on_save_and_loads_without_the_library(
    qapp: QApplication, library: StampLibrary, tmp_path: Path
) -> None:
    info = _custom(library, tmp_path)
    item = StampItem(info.id)
    assert item.stamp_source == CUSTOM
    data = item.serialize()
    assert data["stamp_source"] == EMBEDDED
    assert data["svg_data"] == SQUARE_SVG
    # A machine without the custom stamp: the embedded SVG stands in
    bare = StampLibrary(custom_dir=tmp_path / "elsewhere")
    set_stamp_library(bare)
    restored = StampItem.deserialize(data)
    assert restored.stamp_source == EMBEDDED
    assert restored.svg_data == SQUARE_SVG
    assert not restored.is_missing
    assert restored.stamp_name == "Sq"
    # ... and stays embedded when saved again
    assert restored.serialize()["svg_data"] == SQUARE_SVG


def test_load_prefers_the_local_stamp_over_embedded_data(
    qapp: QApplication, library: StampLibrary, tmp_path: Path
) -> None:
    info = _custom(library, tmp_path)
    data = StampItem(info.id).serialize()
    data["svg_data"] = WIDE_SVG  # stale embedded data; the local file is newer
    restored = StampItem.deserialize(data)
    assert restored.stamp_source == CUSTOM
    assert restored.svg_data == SQUARE_SVG


def test_load_without_local_or_embedded_data_gives_a_placeholder(
    qapp: QApplication, library: StampLibrary
) -> None:
    data = {"type": "StampItem", "stamp_id": "status/vanished", "stamp_source": "builtin"}
    restored = StampItem.deserialize(data)
    assert restored.is_missing
    assert restored.stamp_source == BUILTIN
    assert restored.serialize()["stamp_id"] == "status/vanished"  # the reference survives


def test_project_round_trip_and_non_uniform_stretch(
    qapp: QApplication, library: StampLibrary, tmp_path: Path, scene: SnapScene
) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    info = _custom(library, tmp_path)
    builtin = StampItem("shapes/lock", stamp_size=64.0)
    custom = StampItem(info.id, stamp_size=32.0)
    custom.scale_geometry(2.0, 1.0)
    for item in (builtin, custom):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    path = tmp_path / "stamps.smk"
    save_project(scene, path)
    loaded = load_project(path)
    by_id = {i.item_id: i for i in loaded.annotation_items()}
    lb = by_id[builtin.item_id]
    lc = by_id[custom.item_id]
    assert isinstance(lb, StampItem) and isinstance(lc, StampItem)
    assert lb.stamp_id == "shapes/lock" and lb.stamp_source == BUILTIN
    assert lc.stamp_source == CUSTOM  # the library still has it locally
    assert lc.stamp_rect().width() == pytest.approx(64.0)
    assert lc.stamp_rect().height() == pytest.approx(32.0)


def test_clone_keeps_the_stamp_with_a_new_id(qapp: QApplication, library: StampLibrary) -> None:
    item = StampItem("status/heart", stamp_size=72.0)
    copy = item.clone()
    assert isinstance(copy, StampItem)
    assert copy.item_id != item.item_id
    assert copy.stamp_id == "status/heart"
    assert copy.stamp_size == 72.0
