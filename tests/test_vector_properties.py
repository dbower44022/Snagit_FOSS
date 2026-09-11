"""The shared vector item properties (Basic Shape PRD 2.2; Technical Architecture PRD 4.3):
stroke style, cap, join, the two opacities, and the shadow on ``VectorItem`` and its items.
"""

from __future__ import annotations

from typing import Any

import pytest
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from snapmock.config.constants import (
    DEFAULT_SHADOW_BLUR,
    DEFAULT_SHADOW_COLOR,
    DEFAULT_SHADOW_OFFSET,
    DEFAULT_VECTOR_SHADOW_BLUR,
    DEFAULT_VECTOR_SHADOW_COLOR,
    DEFAULT_VECTOR_SHADOW_OFFSET,
    BorderStyle,
    StrokeCap,
    StrokeJoin,
)
from snapmock.io.project_serializer import ITEM_REGISTRY
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.ellipse_item import EllipseItem
from snapmock.items.freehand_item import FreehandItem
from snapmock.items.highlight_item import HighlightItem
from snapmock.items.line_item import LineItem
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.shadow import SHADOW_KEYS, ShadowMixin
from snapmock.items.vector_item import VectorItem

SIZE = 240
ORIGIN = QPointF(60, 60)

NEW_KEYS = ("stroke_style", "stroke_cap", "stroke_join", "fill_opacity", "stroke_opacity")


def _render(item: VectorItem) -> QImage:
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(ORIGIN)
    item.paint(painter, None)
    painter.end()
    return image


def _pixel(image: QImage, local: QPointF) -> QColor:
    return image.pixelColor(int(ORIGIN.x() + local.x()), int(ORIGIN.y() + local.y()))


def _freehand(points: list[tuple[float, float]]) -> FreehandItem:
    item = FreehandItem()
    for x, y in points:
        item.add_point(QPointF(x, y))
    return item


def _highlight(points: list[tuple[float, float]]) -> HighlightItem:
    item = HighlightItem()
    for x, y in points:
        item.add_point(x, y)
    return item


def _shapes() -> list[VectorItem]:
    return [
        RectangleItem(rect=QRectF(0, 0, 100, 60)),
        EllipseItem(rect=QRectF(0, 0, 100, 60)),
        LineItem(line=QLineF(0, 0, 100, 0)),
        ArrowItem(line=QLineF(0, 0, 100, 0)),
        _freehand([(0, 0), (50, 10), (100, 0)]),
        _highlight([(0, 0), (50, 10), (100, 0)]),
    ]


# --- defaults (2.2) ---


def test_every_vector_item_carries_the_shared_properties_with_the_prd_defaults(
    qapp: QApplication,
) -> None:
    for item in _shapes():
        assert isinstance(item, ShadowMixin)
        assert item.stroke_style is BorderStyle.SOLID
        assert item.stroke_join is StrokeJoin.ROUND
        assert (item.fill_opacity, item.stroke_opacity) == (1.0, 1.0)
        assert item.shadow_enabled is False
        assert item.shadow_color.name(QColor.NameFormat.HexArgb) == DEFAULT_VECTOR_SHADOW_COLOR
        assert (item.shadow_offset_x, item.shadow_offset_y) == (
            DEFAULT_VECTOR_SHADOW_OFFSET,
            DEFAULT_VECTOR_SHADOW_OFFSET,
        )
        assert item.shadow_blur == DEFAULT_VECTOR_SHADOW_BLUR
        expected_cap = StrokeCap.FLAT if isinstance(item, HighlightItem) else StrokeCap.ROUND
        assert item.stroke_cap is expected_cap, type(item).__name__


def test_the_numbered_step_keeps_the_marker_shadow_defaults(qapp: QApplication) -> None:
    step = NumberedStepItem()
    assert step.shadow_enabled is True
    assert step.shadow_color.name(QColor.NameFormat.HexArgb) == DEFAULT_SHADOW_COLOR
    assert (step.shadow_offset_x, step.shadow_blur) == (DEFAULT_SHADOW_OFFSET, DEFAULT_SHADOW_BLUR)
    step.border_style = BorderStyle.DASHED
    assert step.stroke_style is BorderStyle.DASHED
    assert step.serialize()["border_style"] == "dashed"
    assert "stroke_style" not in step.serialize()


def test_opacities_and_blur_are_clamped(qapp: QApplication) -> None:
    item = RectangleItem()
    item.fill_opacity = 1.7
    item.stroke_opacity = -0.2
    assert (item.fill_opacity, item.stroke_opacity) == (1.0, 0.0)


# --- rendering ---


def test_shadow_paints_outside_every_shape_when_enabled(qapp: QApplication) -> None:
    probes = {
        RectangleItem: QPointF(104.0, 64.0),
        EllipseItem: QPointF(54.0, 64.0),
        LineItem: QPointF(50.0, 8.0),
        ArrowItem: QPointF(50.0, 8.0),
        FreehandItem: QPointF(50.0, 17.0),
        HighlightItem: QPointF(50.0, 17.0),
    }
    for item in _shapes():
        item.fill_color = QColor("#00ff00")
        item.stroke_color = QColor("#0000ff")
        item.stroke_width = 4.0
        item.shadow_offset_x = 8.0
        item.shadow_offset_y = 8.0
        item.shadow_blur = 1.0
        probe = probes[type(item)]
        without = _render(item)
        assert _pixel(without, probe).name() == "#ffffff", type(item).__name__
        item.shadow_enabled = True
        with_shadow = _render(item)
        assert _pixel(with_shadow, probe).name() != "#ffffff", type(item).__name__
        assert item.boundingRect().contains(probe), type(item).__name__


def test_shadow_of_an_unfilled_shape_follows_the_stroke_only(qapp: QApplication) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.shadow_enabled = True
    item.shadow_offset_x = 0.0
    item.shadow_offset_y = 0.0
    item.shadow_blur = 0.0
    item.stroke_width = 2.0
    assert item.fill_color.alpha() == 0
    assert _pixel(_render(item), QPointF(50, 30)).name() == "#ffffff"
    item.fill_color = QColor("#00ff00")
    assert _pixel(_render(item), QPointF(50, 30)).name() == "#00ff00"


def test_fill_and_stroke_opacity_lighten_the_paint_separately(qapp: QApplication) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.fill_color = QColor("#0000ff")
    item.stroke_color = QColor("#ff0000")
    item.stroke_width = 6.0
    solid = _render(item)
    inside, edge = QPointF(50, 30), QPointF(50, 0)
    item.fill_opacity = 0.5
    faded_fill = _render(item)
    assert _pixel(faded_fill, inside).red() > _pixel(solid, inside).red()
    assert _pixel(faded_fill, edge) == _pixel(solid, edge)
    item.fill_opacity = 1.0
    item.stroke_opacity = 0.5
    faded_stroke = _render(item)
    assert _pixel(faded_stroke, edge).blue() > _pixel(solid, edge).blue()
    assert _pixel(faded_stroke, inside) == _pixel(solid, inside)


def test_stroke_opacity_reaches_the_arrowhead(qapp: QApplication) -> None:
    item = ArrowItem(line=QLineF(0, 0, 100, 0))
    item.stroke_color = QColor("#ff0000")
    solid = _render(item)
    item.stroke_opacity = 0.3
    faded = _render(item)
    head = QPointF(96.0, 0.0)
    assert _pixel(solid, head).name() == "#ff0000"
    assert _pixel(faded, head).green() > 100


def test_a_dashed_stroke_has_gaps(qapp: QApplication) -> None:
    item = LineItem(line=QLineF(0, 0, 120, 0))
    item.stroke_color = QColor("#000000")
    item.stroke_width = 4.0
    solid = _render(item)
    assert all(_pixel(solid, QPointF(x, 0)).name() == "#000000" for x in range(4, 116, 2))
    item.stroke_style = BorderStyle.DASHED
    dashed = _render(item)
    on = sum(_pixel(dashed, QPointF(x, 0)).name() == "#000000" for x in range(4, 116, 2))
    off = sum(_pixel(dashed, QPointF(x, 0)).name() == "#ffffff" for x in range(4, 116, 2))
    assert on > 0 and off > 0


def test_the_cap_decides_whether_the_stroke_passes_the_endpoint(qapp: QApplication) -> None:
    item = LineItem(line=QLineF(0, 0, 100, 0))
    item.stroke_color = QColor("#000000")
    item.stroke_width = 12.0
    beyond = QPointF(103.0, 0.0)
    assert item.stroke_cap is StrokeCap.ROUND
    assert _pixel(_render(item), beyond).name() == "#000000"
    item.stroke_cap = StrokeCap.FLAT
    assert _pixel(_render(item), beyond).name() == "#ffffff"
    item.stroke_cap = StrokeCap.SQUARE
    assert _pixel(_render(item), beyond).name() == "#000000"
    assert item.boundingRect().contains(QPointF(106.0, 0.0))


def test_the_join_decides_the_corner(qapp: QApplication) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.stroke_color = QColor("#000000")
    item.stroke_width = 10.0
    corner = QPointF(-4.5, -4.5)  # outside a rounded or bevelled corner, inside a mitre
    assert _pixel(_render(item), corner).name() == "#ffffff"
    item.stroke_join = StrokeJoin.MITER
    assert _pixel(_render(item), corner).name() == "#000000"
    assert item.boundingRect().contains(corner)


def test_the_highlighter_paints_through_the_shared_pen(qapp: QApplication) -> None:
    item = _highlight([(0, 0), (100, 0)])
    item.stroke_color = QColor(255, 255, 0, 128)
    item.stroke_width = 20.0
    band = _pixel(_render(item), QPointF(50, 0))
    assert band.red() == 255 and band.blue() < 200
    # Flat cap: nothing beyond the endpoint.
    assert _pixel(_render(item), QPointF(104, 0)).name() == "#ffffff"


# --- hit testing (silence 4) ---


def test_a_fill_at_zero_opacity_still_takes_the_interior_hit(qapp: QApplication) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.fill_color = QColor("#00ff00")
    item.fill_opacity = 0.0
    assert item.shape().contains(QPointF(50, 30))
    item.fill_color = QColor("#0000ff00")
    assert not item.shape().contains(QPointF(50, 30))


# --- serialization ---


@pytest.mark.parametrize("item", _shapes(), ids=lambda i: type(i).__name__)
def test_every_new_key_round_trips(qapp: QApplication, item: VectorItem) -> None:
    item.stroke_style = BorderStyle.DASHDOT
    item.stroke_cap = StrokeCap.SQUARE
    item.stroke_join = StrokeJoin.BEVEL
    item.fill_opacity = 0.4
    item.stroke_opacity = 0.7
    item.shadow_enabled = True
    item.shadow_color = QColor(10, 20, 30, 40)
    item.shadow_offset_x = 5.0
    item.shadow_offset_y = -2.0
    item.shadow_blur = 9.0
    data = item.serialize()
    for key in NEW_KEYS + SHADOW_KEYS:
        assert key in data, key
    restored: Any = ITEM_REGISTRY[data["type"]].deserialize(data)
    assert restored.stroke_style is BorderStyle.DASHDOT
    assert restored.stroke_cap is StrokeCap.SQUARE
    assert restored.stroke_join is StrokeJoin.BEVEL
    assert restored.fill_opacity == pytest.approx(0.4)
    assert restored.stroke_opacity == pytest.approx(0.7)
    assert restored.shadow_enabled is True
    assert restored.shadow_color.name(QColor.NameFormat.HexArgb) == "#280a141e"
    assert (restored.shadow_offset_x, restored.shadow_offset_y, restored.shadow_blur) == (
        5.0,
        -2.0,
        9.0,
    )


def test_a_file_saved_before_this_work_loads_with_the_defaults(qapp: QApplication) -> None:
    """The keys c1c35c5 wrote, and nothing else: every new property reads as its default."""
    old = {
        "item_id": "abc",
        "layer_id": "",
        "pos": [10.0, 20.0],
        "rotation": 0.0,
        "opacity": 1.0,
        "transform": [1, 0, 0, 0, 1, 0, 0, 0, 1],
        "stroke_color": "#ffff0000",
        "stroke_width": 3.0,
        "fill_color": "#8000ff00",
        "flip_horizontal": False,
        "flip_vertical": False,
        "type": "RectangleItem",
        "rect": [0, 0, 50, 40],
        "corner_radius": 0.0,
    }
    item = RectangleItem.deserialize(old)
    assert item.stroke_width == 3.0 and item.fill_color.alpha() == 128
    assert item.stroke_style is BorderStyle.SOLID
    assert item.stroke_cap is StrokeCap.ROUND and item.stroke_join is StrokeJoin.ROUND
    assert (item.fill_opacity, item.stroke_opacity) == (1.0, 1.0)
    assert item.shadow_enabled is False
    assert item.shadow_blur == DEFAULT_VECTOR_SHADOW_BLUR
    old["type"] = "HighlightItem"
    old["points"] = [[0, 0], [10, 0]]
    assert HighlightItem.deserialize(old).stroke_cap is StrokeCap.FLAT


def test_unknown_enum_values_read_as_the_defaults(qapp: QApplication) -> None:
    data = RectangleItem().serialize()
    data.update({"stroke_style": "wavy", "stroke_cap": "bulb", "stroke_join": "knot"})
    item = RectangleItem.deserialize(data)
    assert item.stroke_style is BorderStyle.SOLID
    assert item.stroke_cap is StrokeCap.ROUND and item.stroke_join is StrokeJoin.ROUND


def test_property_setters_reach_qt(qapp: QApplication) -> None:
    """The shadow helper's stand-in methods no longer hide Qt's ``update`` and
    ``prepareGeometryChange`` from the items that mix it in."""
    for item in (RectangleItem(), NumberedStepItem()):
        assert type(item).update is not ShadowMixin.__dict__.get("update")
        assert "update" not in ShadowMixin.__dict__
        assert "prepareGeometryChange" not in ShadowMixin.__dict__
