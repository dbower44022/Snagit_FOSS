"""Tests for item classes and add/remove commands."""

import pytest
from PyQt6.QtCore import QLineF, QPointF, QRectF
from PyQt6.QtGui import QColor, QTransform
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.remove_item import RemoveItemCommand
from snapmock.core.scene import SnapScene
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.ellipse_item import EllipseItem
from snapmock.items.line_item import LineItem
from snapmock.items.rectangle_item import RectangleItem


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    """SnapScene that requires QApplication."""
    return SnapScene(width=800, height=600)


# --- RectangleItem ---


def test_rectangle_defaults() -> None:
    item = RectangleItem()
    assert item.rect == QRectF(0, 0, 100, 60)
    assert item.corner_radius == 0.0


def test_rectangle_custom_rect() -> None:
    item = RectangleItem(rect=QRectF(10, 20, 200, 150))
    assert item.rect.width() == 200


def test_rectangle_bounding_rect_includes_stroke() -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 50))
    br = item.boundingRect()
    assert br.width() > 100


def test_rectangle_serialize_roundtrip() -> None:
    item = RectangleItem(rect=QRectF(5, 10, 200, 100), corner_radius=8.0)
    item.setPos(50, 60)
    data = item.serialize()
    restored = RectangleItem.deserialize(data)
    assert restored.rect == item.rect
    assert restored.corner_radius == 8.0
    assert restored.pos().x() == 50


# --- Hit testing: transparent fill selects near the border only ---
# Basic Shape Annotation Tools PRD, Sections 5.6 and 6.6.


def test_rectangle_transparent_fill_hit_border_only() -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    assert item.fill_color.alpha() == 0  # default fill is transparent
    shape = item.shape()
    assert not shape.contains(QPointF(50, 30))  # centre
    assert shape.contains(QPointF(0, 30))  # on the left edge
    assert shape.contains(QPointF(2, 30))  # inside the padding band
    assert shape.contains(QPointF(-2, 30))  # outside the edge, still in the band


def test_rectangle_filled_hit_anywhere_inside() -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.fill_color = QColor("#FF0000")
    assert item.shape().contains(QPointF(50, 30))


def test_rectangle_faint_fill_counts_as_filled() -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.fill_color = QColor(255, 0, 0, 1)  # alpha 1 of 255
    assert item.shape().contains(QPointF(50, 30))


def test_rectangle_transparent_fill_band_follows_stroke_width() -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.stroke_width = 20.0  # band is (20 + 4) / 2 = 12 px each side
    shape = item.shape()
    assert shape.contains(QPointF(10, 30))
    assert not shape.contains(QPointF(14, 30))


def test_rounded_rectangle_transparent_fill_follows_rounded_outline() -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 100), corner_radius=30.0)
    shape = item.shape()
    assert not shape.contains(QPointF(50, 50))
    assert not shape.contains(QPointF(1, 1))  # sharp corner is outside the rounded outline
    assert shape.contains(QPointF(50, 0))


def test_ellipse_transparent_fill_hit_border_only() -> None:
    item = EllipseItem(rect=QRectF(0, 0, 100, 100))
    shape = item.shape()
    assert not shape.contains(QPointF(50, 50))
    assert shape.contains(QPointF(50, 0))
    assert not shape.contains(QPointF(2, 2))  # bounding-box corner is not on the ellipse


def test_ellipse_filled_hit_anywhere_inside() -> None:
    item = EllipseItem(rect=QRectF(0, 0, 100, 100))
    item.fill_color = QColor("#00FF00")
    assert item.shape().contains(QPointF(50, 50))


def test_scene_click_selects_transparent_rectangle_by_border_only(scene: SnapScene) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    scene.addItem(item)
    item.setPos(100, 100)
    assert scene.itemAt(QPointF(150, 130), QTransform()) is not item
    assert scene.itemAt(QPointF(100, 130), QTransform()) is item


# --- EllipseItem ---


def test_ellipse_defaults() -> None:
    item = EllipseItem()
    assert item.rect == QRectF(0, 0, 100, 100)


def test_ellipse_serialize_roundtrip() -> None:
    item = EllipseItem(rect=QRectF(0, 0, 80, 40))
    data = item.serialize()
    restored = EllipseItem.deserialize(data)
    assert restored.rect == item.rect


# --- LineItem ---


def test_line_defaults() -> None:
    item = LineItem()
    assert item.line == QLineF(0, 0, 100, 0)


def test_line_serialize_roundtrip() -> None:
    item = LineItem(line=QLineF(QPointF(10, 20), QPointF(100, 200)))
    data = item.serialize()
    restored = LineItem.deserialize(data)
    assert restored.line.p1() == item.line.p1()
    assert restored.line.p2() == item.line.p2()


# --- ArrowItem ---


def test_arrow_defaults() -> None:
    item = ArrowItem()
    assert item.line == QLineF(0, 0, 100, 0)


def test_arrow_serialize_roundtrip() -> None:
    item = ArrowItem(line=QLineF(QPointF(0, 0), QPointF(50, 50)))
    data = item.serialize()
    restored = ArrowItem.deserialize(data)
    assert restored.line.p2() == item.line.p2()


# --- AddItemCommand / RemoveItemCommand ---


def test_add_item_command(scene: SnapScene) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem()
    cmd = AddItemCommand(scene, item, layer.layer_id)
    scene.command_stack.push(cmd)
    assert item.scene() is scene
    assert item.item_id in layer.item_ids


def test_undo_add_item(scene: SnapScene) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem()
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    scene.command_stack.undo()
    assert item.scene() is None
    assert item.item_id not in layer.item_ids


def test_remove_item_command(scene: SnapScene) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = EllipseItem()
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    scene.command_stack.push(RemoveItemCommand(scene, item))
    assert item.scene() is None
    assert item.item_id not in layer.item_ids
    scene.command_stack.undo()
    assert item.scene() is scene
    assert item.item_id in layer.item_ids
