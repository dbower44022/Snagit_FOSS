"""Tests for canvas transform commands (rotate, flip)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF

from snapmock.commands.canvas_transform_commands import FlipCanvasCommand, RotateCanvasCommand
from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem


def _make_rect(
    scene: SnapScene, x: float, y: float, w: float = 50, h: float = 50
) -> RectangleItem:
    item = RectangleItem(rect=QRectF(0, 0, w, h))
    item.setPos(x, y)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.addItem(item)
    item.layer_id = layer.layer_id
    layer.item_ids.append(item.item_id)
    return item


@pytest.fixture()
def scene() -> SnapScene:
    return SnapScene(width=1920, height=1080)


class TestRotateCanvas:
    def test_rotate_cw_swaps_dimensions(self, scene: SnapScene) -> None:
        cmd = RotateCanvasCommand(scene, clockwise=True)
        cmd.redo()
        assert abs(scene.canvas_size.width() - 1080) < 0.01
        assert abs(scene.canvas_size.height() - 1920) < 0.01

    def test_rotate_ccw_swaps_dimensions(self, scene: SnapScene) -> None:
        cmd = RotateCanvasCommand(scene, clockwise=False)
        cmd.redo()
        assert abs(scene.canvas_size.width() - 1080) < 0.01
        assert abs(scene.canvas_size.height() - 1920) < 0.01

    def test_rotate_cw_repositions_item(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 100, 200)
        cmd = RotateCanvasCommand(scene, clockwise=True)
        cmd.redo()
        # CW: (x, y) -> (h - y, x) where h=1080
        assert abs(item.pos().x() - (1080 - 200)) < 0.01
        assert abs(item.pos().y() - 100) < 0.01

    def test_rotate_ccw_repositions_item(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 100, 200)
        cmd = RotateCanvasCommand(scene, clockwise=False)
        cmd.redo()
        # CCW: (x, y) -> (y, w - x) where w=1920
        assert abs(item.pos().x() - 200) < 0.01
        assert abs(item.pos().y() - (1920 - 100)) < 0.01

    def test_undo_restores_dimensions_and_position(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 100, 200)
        cmd = RotateCanvasCommand(scene, clockwise=True)
        cmd.redo()
        cmd.undo()
        assert abs(scene.canvas_size.width() - 1920) < 0.01
        assert abs(scene.canvas_size.height() - 1080) < 0.01
        assert abs(item.pos().x() - 100) < 0.01
        assert abs(item.pos().y() - 200) < 0.01


class TestFlipCanvas:
    def test_flip_horizontal_mirrors_position(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 100, 200, 50, 50)
        # boundingRect includes stroke padding, so width != 50 exactly
        br_w = item.boundingRect().width()
        cmd = FlipCanvasCommand(scene, horizontal=True)
        cmd.redo()
        # Horizontal flip: new_x = canvas_w - x - boundingRect_w
        expected_x = 1920 - 100 - br_w
        assert abs(item.pos().x() - expected_x) < 0.01
        assert abs(item.pos().y() - 200) < 0.01

    def test_flip_vertical_mirrors_position(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 100, 200, 50, 50)
        br_h = item.boundingRect().height()
        cmd = FlipCanvasCommand(scene, horizontal=False)
        cmd.redo()
        # Vertical flip: new_y = canvas_h - y - boundingRect_h
        expected_y = 1080 - 200 - br_h
        assert abs(item.pos().x() - 100) < 0.01
        assert abs(item.pos().y() - expected_y) < 0.01

    def test_undo_restores_position(self, scene: SnapScene) -> None:
        item = _make_rect(scene, 100, 200, 50, 50)
        cmd = FlipCanvasCommand(scene, horizontal=True)
        cmd.redo()
        cmd.undo()
        assert abs(item.pos().x() - 100) < 0.01
        assert abs(item.pos().y() - 200) < 0.01
