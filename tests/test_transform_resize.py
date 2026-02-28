"""Tests for transform handles, scale_geometry, and TransformItemCommand."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QLineF, QPointF, QRectF
from PyQt6.QtGui import QPixmap, QTransform
from PyQt6.QtWidgets import QApplication

from snapmock.commands.transform_item import TransformItemCommand
from snapmock.core.scene import SnapScene
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.blur_item import BlurItem
from snapmock.items.callout_item import CalloutItem
from snapmock.items.ellipse_item import EllipseItem
from snapmock.items.freehand_item import FreehandItem
from snapmock.items.highlight_item import HighlightItem
from snapmock.items.line_item import LineItem
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.stamp_item import StampItem
from snapmock.items.text_item import TextItem
from snapmock.ui.transform_handles import HandlePosition, TransformHandles


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


# --- scale_geometry ---


def test_rectangle_scale_geometry() -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 50), corner_radius=10.0)
    item.scale_geometry(2.0, 2.0)
    assert item._rect.width() == pytest.approx(200)  # noqa: SLF001
    assert item._rect.height() == pytest.approx(100)  # noqa: SLF001
    assert item._corner_radius == pytest.approx(20.0)  # noqa: SLF001


def test_ellipse_scale_geometry() -> None:
    item = EllipseItem(rect=QRectF(0, 0, 80, 40))
    item.scale_geometry(0.5, 0.5)
    assert item._rect.width() == pytest.approx(40)  # noqa: SLF001
    assert item._rect.height() == pytest.approx(20)  # noqa: SLF001


def test_line_scale_geometry() -> None:
    item = LineItem(line=QLineF(0, 0, 100, 50))
    item.scale_geometry(2.0, 3.0)
    assert item._line.x2() == pytest.approx(200)  # noqa: SLF001
    assert item._line.y2() == pytest.approx(150)  # noqa: SLF001


def test_arrow_scale_geometry() -> None:
    item = ArrowItem(line=QLineF(10, 20, 110, 70))
    item.scale_geometry(2.0, 2.0)
    assert item._line.x1() == pytest.approx(20)  # noqa: SLF001
    assert item._line.y1() == pytest.approx(40)  # noqa: SLF001


def test_freehand_scale_geometry() -> None:
    item = FreehandItem()
    item.add_point(QPointF(0, 0))
    item.add_point(QPointF(50, 100))
    item.scale_geometry(2.0, 0.5)
    assert item._points[1] == (100.0, 50.0)  # noqa: SLF001


def test_highlight_scale_geometry() -> None:
    item = HighlightItem()
    item.add_point(0, 0)
    item.add_point(100, 200)
    item.scale_geometry(3.0, 1.5)
    assert item._points[1] == (300.0, 300.0)  # noqa: SLF001


def test_text_scale_geometry() -> None:
    item = TextItem(text="Hello")
    original_size = item._font.pointSize()  # noqa: SLF001
    item.scale_geometry(2.0, 2.0)
    assert item._font.pointSize() == max(1, int(original_size * 2.0))  # noqa: SLF001
    assert item._width == pytest.approx(400.0)  # noqa: SLF001


def test_callout_scale_geometry() -> None:
    item = CalloutItem(rect=QRectF(0, 0, 150, 60), tail_tip=QPointF(75, 90))
    item.scale_geometry(2.0, 2.0)
    assert item._rect.width() == pytest.approx(300)  # noqa: SLF001
    assert item._tail_tip.x() == pytest.approx(150)  # noqa: SLF001
    assert item._tail_tip.y() == pytest.approx(180)  # noqa: SLF001


def test_blur_scale_geometry() -> None:
    item = BlurItem(rect=QRectF(0, 0, 100, 100), blur_radius=10.0)
    item.scale_geometry(2.0, 2.0)
    assert item._rect.width() == pytest.approx(200)  # noqa: SLF001
    assert item._blur_radius == pytest.approx(20.0)  # noqa: SLF001


def test_raster_region_scale_geometry(qapp: QApplication) -> None:
    pm = QPixmap(100, 80)
    item = RasterRegionItem(pixmap=pm)
    item.scale_geometry(2.0, 2.0)
    assert item._pixmap.width() == 200  # noqa: SLF001
    assert item._pixmap.height() == 160  # noqa: SLF001


def test_numbered_step_scale_geometry() -> None:
    item = NumberedStepItem(number=1)
    original_radius = item._radius  # noqa: SLF001
    item.scale_geometry(3.0, 3.0)
    assert item._radius == pytest.approx(original_radius * 3.0)  # noqa: SLF001


def test_stamp_scale_geometry(qapp: QApplication) -> None:
    pm = QPixmap(64, 64)
    item = StampItem(pixmap=pm)
    item.scale_geometry(2.0, 2.0)
    assert item._pixmap.width() == 128  # noqa: SLF001
    assert item._pixmap.height() == 128  # noqa: SLF001


# --- TransformHandles ---


def test_transform_handles_handle_positions(scene: SnapScene) -> None:
    handles = TransformHandles(scene)
    scene.addItem(handles)
    rect = QRectF(100, 100, 200, 150)
    handles.update_rect(rect)

    # Rotate handle should be above top-center
    assert handles.handle_at(QPointF(200, 70)) == HandlePosition.ROTATE

    # Corners
    assert handles.handle_at(rect.topLeft()) == HandlePosition.TOP_LEFT
    assert handles.handle_at(rect.bottomRight()) == HandlePosition.BOTTOM_RIGHT

    # Nothing in the middle
    assert handles.handle_at(QPointF(200, 175)) is None


def test_transform_handles_anchor_for_corner(scene: SnapScene) -> None:
    handles = TransformHandles(scene)
    rect = QRectF(0, 0, 100, 100)
    handles.update_rect(rect)

    anchor = handles.anchor_for_handle(HandlePosition.TOP_LEFT)
    assert anchor.x() == pytest.approx(100)
    assert anchor.y() == pytest.approx(100)


# --- TransformItemCommand ---


def test_transform_item_command_redo_undo(scene: SnapScene) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    scene.addItem(item)

    old_pos = QPointF(10, 20)
    new_pos = QPointF(100, 200)
    old_xform = QTransform()
    new_xform = QTransform()
    new_xform.scale(2.0, 2.0)

    item.setPos(old_pos)
    cmd = TransformItemCommand(item, old_pos, new_pos, old_xform, new_xform)
    cmd.redo()

    assert item.pos().x() == pytest.approx(100)
    assert item.transform().m11() == pytest.approx(2.0)

    cmd.undo()
    assert item.pos().x() == pytest.approx(10)
    assert item.transform().m11() == pytest.approx(1.0)
