"""Tests for arrange commands (z-order, align, distribute)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF

from snapmock.commands.arrange_commands import (
    AlignItemsCommand,
    AlignToCanvasCommand,
    ChangeZOrderCommand,
    DistributeItemsCommand,
)
from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem


def _make_rect(
    scene: SnapScene, x: float, y: float, w: float = 50, h: float = 50
) -> RectangleItem:
    """Create a rectangle item at (x, y) and add to the scene's active layer."""
    item = RectangleItem(rect=QRectF(0, 0, w, h))
    item.setPos(x, y)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.addItem(item)
    item.layer_id = layer.layer_id
    layer.item_ids.append(item.item_id)
    item.setZValue(layer.z_base + len(layer.item_ids) - 1)
    return item


@pytest.fixture()
def scene() -> SnapScene:
    return SnapScene()


# ---- Z-Order tests ----


class TestChangeZOrder:
    def test_bring_to_front(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0)
        b = _make_rect(scene, 10, 10)
        c = _make_rect(scene, 20, 20)
        layer = scene.layer_manager.active_layer
        assert layer is not None
        assert layer.item_ids == [a.item_id, b.item_id, c.item_id]

        cmd = ChangeZOrderCommand(scene, [a], "front")
        cmd.redo()
        assert layer.item_ids == [b.item_id, c.item_id, a.item_id]

    def test_send_to_back(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0)
        b = _make_rect(scene, 10, 10)
        c = _make_rect(scene, 20, 20)
        layer = scene.layer_manager.active_layer
        assert layer is not None

        cmd = ChangeZOrderCommand(scene, [c], "back")
        cmd.redo()
        assert layer.item_ids == [c.item_id, a.item_id, b.item_id]

    def test_bring_forward(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0)
        b = _make_rect(scene, 10, 10)
        c = _make_rect(scene, 20, 20)
        layer = scene.layer_manager.active_layer
        assert layer is not None

        cmd = ChangeZOrderCommand(scene, [a], "forward")
        cmd.redo()
        assert layer.item_ids == [b.item_id, a.item_id, c.item_id]

    def test_send_backward(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0)
        b = _make_rect(scene, 10, 10)
        c = _make_rect(scene, 20, 20)
        layer = scene.layer_manager.active_layer
        assert layer is not None

        cmd = ChangeZOrderCommand(scene, [c], "backward")
        cmd.redo()
        assert layer.item_ids == [a.item_id, c.item_id, b.item_id]

    def test_undo_restores_order(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0)
        _b = _make_rect(scene, 10, 10)
        layer = scene.layer_manager.active_layer
        assert layer is not None
        original = list(layer.item_ids)

        cmd = ChangeZOrderCommand(scene, [a], "front")
        cmd.redo()
        assert layer.item_ids != original
        cmd.undo()
        assert layer.item_ids == original


# ---- Align tests ----


class TestAlignItems:
    def test_align_left(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 100, 50)
        b = _make_rect(scene, 200, 80)
        cmd = AlignItemsCommand([a, b], "left")
        cmd.redo()
        # Both should have their left edges at 100
        assert abs(a.sceneBoundingRect().left() - b.sceneBoundingRect().left()) < 0.01

    def test_align_right(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 100, 50, 50, 50)
        b = _make_rect(scene, 200, 80, 50, 50)
        cmd = AlignItemsCommand([a, b], "right")
        cmd.redo()
        assert abs(a.sceneBoundingRect().right() - b.sceneBoundingRect().right()) < 0.01

    def test_align_top(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 50, 100)
        b = _make_rect(scene, 80, 200)
        cmd = AlignItemsCommand([a, b], "top")
        cmd.redo()
        assert abs(a.sceneBoundingRect().top() - b.sceneBoundingRect().top()) < 0.01

    def test_align_bottom(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 50, 100, 50, 50)
        b = _make_rect(scene, 80, 200, 50, 50)
        cmd = AlignItemsCommand([a, b], "bottom")
        cmd.redo()
        assert abs(a.sceneBoundingRect().bottom() - b.sceneBoundingRect().bottom()) < 0.01

    def test_align_center_h(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 100, 50, 50, 50)
        b = _make_rect(scene, 200, 80, 50, 50)
        cmd = AlignItemsCommand([a, b], "center_h")
        cmd.redo()
        assert abs(a.sceneBoundingRect().center().x() - b.sceneBoundingRect().center().x()) < 0.01

    def test_align_middle_v(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 50, 100, 50, 50)
        b = _make_rect(scene, 80, 200, 50, 50)
        cmd = AlignItemsCommand([a, b], "middle_v")
        cmd.redo()
        assert abs(a.sceneBoundingRect().center().y() - b.sceneBoundingRect().center().y()) < 0.01

    def test_undo_restores_positions(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 100, 50)
        b = _make_rect(scene, 200, 80)
        old_a = a.pos()
        old_b = b.pos()
        cmd = AlignItemsCommand([a, b], "left")
        cmd.redo()
        cmd.undo()
        assert abs(a.pos().x() - old_a.x()) < 0.01
        assert abs(a.pos().y() - old_a.y()) < 0.01
        assert abs(b.pos().x() - old_b.x()) < 0.01
        assert abs(b.pos().y() - old_b.y()) < 0.01


# ---- Distribute tests ----


class TestDistributeItems:
    def test_distribute_horizontal(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0, 20, 20)
        b = _make_rect(scene, 100, 0, 20, 20)
        c = _make_rect(scene, 200, 0, 20, 20)
        cmd = DistributeItemsCommand([a, b, c], "horizontal")
        cmd.redo()
        # After distributing, gaps between items should be equal
        rects = sorted(
            [a.sceneBoundingRect(), b.sceneBoundingRect(), c.sceneBoundingRect()],
            key=lambda r: r.left(),
        )
        gap1 = rects[1].left() - rects[0].right()
        gap2 = rects[2].left() - rects[1].right()
        assert abs(gap1 - gap2) < 0.01

    def test_distribute_vertical(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0, 20, 20)
        b = _make_rect(scene, 0, 100, 20, 20)
        c = _make_rect(scene, 0, 200, 20, 20)
        cmd = DistributeItemsCommand([a, b, c], "vertical")
        cmd.redo()
        rects = sorted(
            [a.sceneBoundingRect(), b.sceneBoundingRect(), c.sceneBoundingRect()],
            key=lambda r: r.top(),
        )
        gap1 = rects[1].top() - rects[0].bottom()
        gap2 = rects[2].top() - rects[1].bottom()
        assert abs(gap1 - gap2) < 0.01

    def test_undo_restores_positions(self, scene: SnapScene) -> None:
        a = _make_rect(scene, 0, 0, 20, 20)
        b = _make_rect(scene, 50, 0, 20, 20)
        c = _make_rect(scene, 200, 0, 20, 20)
        old_b_x = b.pos().x()
        cmd = DistributeItemsCommand([a, b, c], "horizontal")
        cmd.redo()
        cmd.undo()
        assert abs(b.pos().x() - old_b_x) < 0.01


# ---- Align to Canvas tests ----


class TestAlignToCanvas:
    def test_centers_items_on_canvas(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 0, 0, 100, 100)
        cmd = AlignToCanvasCommand(scene, [item])
        cmd.redo()
        canvas = scene.canvas_size
        center_x = canvas.width() / 2
        center_y = canvas.height() / 2
        item_center = item.sceneBoundingRect().center()
        assert abs(item_center.x() - center_x) < 0.01
        assert abs(item_center.y() - center_y) < 0.01

    def test_undo_restores_position(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 42, 73)
        old_pos = item.pos()
        cmd = AlignToCanvasCommand(scene, [item])
        cmd.redo()
        cmd.undo()
        assert abs(item.pos().x() - old_pos.x()) < 0.01
        assert abs(item.pos().y() - old_pos.y()) < 0.01
