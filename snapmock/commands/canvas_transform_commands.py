"""Canvas transform commands — rotate and flip the entire canvas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QSizeF

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


class RotateCanvasCommand(BaseCommand):
    """Rotate the canvas 90 degrees clockwise or counter-clockwise.

    Swaps width/height and rotates each item's position around the canvas center.
    """

    def __init__(self, scene: SnapScene, *, clockwise: bool = True) -> None:
        self._scene = scene
        self._clockwise = clockwise
        self._old_size = QSizeF(scene.canvas_size)
        self._old_positions: dict[str, QPointF] = {}

    def redo(self) -> None:
        w = self._old_size.width()
        h = self._old_size.height()

        # Save old positions
        self._old_positions.clear()
        for scene_item in self._scene.items():
            if isinstance(scene_item, SnapGraphicsItem):
                self._old_positions[scene_item.item_id] = QPointF(scene_item.pos())

        # Swap canvas dimensions
        new_size = QSizeF(h, w)
        self._scene.set_canvas_size(new_size)

        # Rotate each item's position around old canvas center
        for scene_item in self._scene.items():
            if isinstance(scene_item, SnapGraphicsItem):
                pos = self._old_positions.get(scene_item.item_id)
                if pos is None:
                    continue
                if self._clockwise:
                    # (x, y) -> (h - y, x) when rotating CW (old h becomes new w)
                    new_x = h - pos.y()
                    new_y = pos.x()
                else:
                    # (x, y) -> (y, w - x) when rotating CCW
                    new_x = pos.y()
                    new_y = w - pos.x()
                scene_item.setPos(new_x, new_y)

    def undo(self) -> None:
        # Restore canvas size
        self._scene.set_canvas_size(self._old_size)
        # Restore positions
        for scene_item in self._scene.items():
            if isinstance(scene_item, SnapGraphicsItem):
                old_pos = self._old_positions.get(scene_item.item_id)
                if old_pos is not None:
                    scene_item.setPos(old_pos)

    @property
    def description(self) -> str:
        direction = "CW" if self._clockwise else "CCW"
        return f"Rotate Canvas 90° {direction}"


class FlipCanvasCommand(BaseCommand):
    """Flip (mirror) the canvas horizontally or vertically.

    Mirrors each item's position across the canvas center axis.
    """

    def __init__(self, scene: SnapScene, *, horizontal: bool = True) -> None:
        self._scene = scene
        self._horizontal = horizontal
        self._old_positions: dict[str, QPointF] = {}

    def redo(self) -> None:
        canvas = self._scene.canvas_size
        w = canvas.width()
        h = canvas.height()

        self._old_positions.clear()
        for scene_item in self._scene.items():
            if isinstance(scene_item, SnapGraphicsItem):
                self._old_positions[scene_item.item_id] = QPointF(scene_item.pos())

        for scene_item in self._scene.items():
            if isinstance(scene_item, SnapGraphicsItem):
                pos = scene_item.pos()
                rect = scene_item.boundingRect()
                if self._horizontal:
                    # Mirror across vertical center axis
                    new_x = w - pos.x() - rect.width()
                    scene_item.setPos(new_x, pos.y())
                else:
                    # Mirror across horizontal center axis
                    new_y = h - pos.y() - rect.height()
                    scene_item.setPos(pos.x(), new_y)

    def undo(self) -> None:
        for scene_item in self._scene.items():
            if isinstance(scene_item, SnapGraphicsItem):
                old_pos = self._old_positions.get(scene_item.item_id)
                if old_pos is not None:
                    scene_item.setPos(old_pos)

    @property
    def description(self) -> str:
        direction = "Horizontal" if self._horizontal else "Vertical"
        return f"Flip Canvas {direction}"
