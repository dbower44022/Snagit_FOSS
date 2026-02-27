"""Tests for item classes and add/remove commands."""

import pytest
from PyQt6.QtCore import QLineF, QPointF, QRectF
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
