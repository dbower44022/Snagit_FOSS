"""The text box's and the callout's shadow and opacities (Text and Callout PRD 3.7, 4.8,
7.2, 8.3; Vector Item Properties decision 1, option B)."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from snapmock.config.constants import (
    DEFAULT_VECTOR_SHADOW_BLUR,
    DEFAULT_VECTOR_SHADOW_COLOR,
    BubbleShape,
)
from snapmock.items.callout_item import CalloutItem
from snapmock.items.shadow import SHADOW_KEYS, ShadowMixin
from snapmock.items.text_item import TextItem
from snapmock.items.vector_item import VectorItem

SIZE = 400
ORIGIN = QPointF(60, 60)


def _render(item: TextItem | CalloutItem) -> QImage:
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


def _text_box() -> TextItem:
    item = TextItem("Hi")
    item.auto_width = False
    item.auto_size = False
    item.text_width = 120.0
    item.text_height = 60.0
    item.bg_color = QColor("#00ff00")
    item.border_color = QColor("#0000ff")
    item.border_width = 4.0
    return item


def _callout() -> CalloutItem:
    item = CalloutItem("Hi", rect=QRectF(0, 0, 120, 60), tail_tip=QPointF(60, 150))
    item.auto_height = False
    return item


def test_text_items_sit_beside_vector_item_and_carry_the_shared_defaults(
    qapp: QApplication,
) -> None:
    for item in (_text_box(), _callout()):
        assert isinstance(item, ShadowMixin) and not isinstance(item, VectorItem)
        assert (item.fill_opacity, item.stroke_opacity) == (1.0, 1.0)
        assert item.shadow_enabled is False
        assert item.shadow_color.name(QColor.NameFormat.HexArgb) == DEFAULT_VECTOR_SHADOW_COLOR
        assert item.shadow_blur == DEFAULT_VECTOR_SHADOW_BLUR


def test_the_callout_shadow_follows_the_tail(qapp: QApplication) -> None:
    item = _callout()
    item.shadow_offset_x = 10.0
    item.shadow_offset_y = 10.0
    item.shadow_blur = 1.0
    beside_tail = QPointF(70.0, 140.0)  # just right of the tail near its tip
    assert _pixel(_render(item), beside_tail).name() == "#ffffff"
    item.shadow_enabled = True
    assert _pixel(_render(item), beside_tail).name() != "#ffffff"
    assert item.boundingRect().contains(beside_tail)
    # The cloud's tail circles are shadowed too
    item.bubble_shape = BubbleShape.CLOUD
    item.shadow_enabled = False
    circle = QPointF(70.0, 124.0)  # the third tail circle, moved by the offset
    assert _pixel(_render(item), circle).name() == "#ffffff"
    item.shadow_enabled = True
    assert _pixel(_render(item), circle).name() != "#ffffff"


def test_the_text_box_shadow_follows_the_border_radius(qapp: QApplication) -> None:
    item = _text_box()
    item.shadow_enabled = True
    item.shadow_offset_x = 0.0
    item.shadow_offset_y = 0.0
    item.shadow_blur = 0.0
    item.shadow_color = QColor(0, 0, 0, 255)
    item.bg_color = QColor("#00000000")
    item.border_width = 0.0
    corner = QPointF(1.5, 1.5)
    assert _pixel(_render(item), corner).name() == "#000000"
    item.border_radius = 30.0
    assert _pixel(_render(item), corner).name() == "#ffffff"


def test_the_opacities_lighten_the_background_and_the_border(qapp: QApplication) -> None:
    for item, inside, edge in (
        (_text_box(), QPointF(100.0, 45.0), QPointF(60.0, 0.0)),
        (_callout(), QPointF(100.0, 45.0), QPointF(60.0, 0.0)),
    ):
        if isinstance(item, CalloutItem):
            item.bg_color = QColor("#00ff00")
            item.border_color = QColor("#0000ff")
            item.border_width = 4.0
        solid = _render(item)
        item.fill_opacity = 0.5
        faded_fill = _render(item)
        assert _pixel(faded_fill, inside).red() > _pixel(solid, inside).red()
        assert _pixel(faded_fill, edge) == _pixel(solid, edge)
        item.fill_opacity = 1.0
        item.stroke_opacity = 0.5
        faded_stroke = _render(item)
        assert _pixel(faded_stroke, edge).blue() < _pixel(solid, edge).blue()
        assert _pixel(faded_stroke, inside) == _pixel(solid, inside)


def test_the_new_keys_round_trip_and_absent_keys_read_as_defaults(qapp: QApplication) -> None:
    for item in (_text_box(), _callout()):
        item.fill_opacity = 0.3
        item.stroke_opacity = 0.6
        item.shadow_enabled = True
        item.shadow_color = QColor(1, 2, 3, 4)
        item.shadow_offset_x = 7.0
        item.shadow_offset_y = 8.0
        item.shadow_blur = 2.5
        data = item.serialize()
        for key in ("fill_opacity", "stroke_opacity", *SHADOW_KEYS):
            assert key in data, key
        restored = type(item).deserialize(data)
        assert (restored.fill_opacity, restored.stroke_opacity) == (0.3, 0.6)
        assert restored.shadow_enabled is True
        assert restored.shadow_color.name(QColor.NameFormat.HexArgb) == "#04010203"
        assert (restored.shadow_offset_x, restored.shadow_offset_y) == (7.0, 8.0)
        assert restored.shadow_blur == 2.5
        for key in ("fill_opacity", "stroke_opacity", *SHADOW_KEYS):
            data.pop(key)
        old = type(item).deserialize(data)
        assert (old.fill_opacity, old.stroke_opacity) == (1.0, 1.0)
        assert old.shadow_enabled is False
        assert old.shadow_blur == DEFAULT_VECTOR_SHADOW_BLUR
