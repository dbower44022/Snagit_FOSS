"""TransformHandles — resize/rotate handles displayed around selected items."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsItemGroup, QGraphicsRectItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene

HANDLE_SIZE = 8.0
HANDLE_HALF = HANDLE_SIZE / 2.0


class HandlePosition(Enum):
    TOP_LEFT = auto()
    TOP_CENTER = auto()
    TOP_RIGHT = auto()
    MIDDLE_LEFT = auto()
    MIDDLE_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_CENTER = auto()
    BOTTOM_RIGHT = auto()


_CURSOR_MAP: dict[HandlePosition, Qt.CursorShape] = {
    HandlePosition.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    HandlePosition.TOP_CENTER: Qt.CursorShape.SizeVerCursor,
    HandlePosition.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.MIDDLE_LEFT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.MIDDLE_RIGHT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.BOTTOM_CENTER: Qt.CursorShape.SizeVerCursor,
    HandlePosition.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
}


class HandleItem(QGraphicsRectItem):
    """Small square handle for resizing."""

    def __init__(self, position: HandlePosition) -> None:
        super().__init__(-HANDLE_HALF, -HANDLE_HALF, HANDLE_SIZE, HANDLE_SIZE)
        self.position = position
        self.setPen(QPen(QColor(0, 120, 215), 1))
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setZValue(999998)
        cursor = _CURSOR_MAP.get(position, Qt.CursorShape.ArrowCursor)
        self.setCursor(cursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)


class TransformHandles(QGraphicsItemGroup):
    """8 resize handles displayed around the bounding rect of selected items.

    This is ephemeral UI — not serialized, not part of any layer.
    """

    def __init__(self, scene: SnapScene) -> None:
        super().__init__()
        self._scene = scene
        self.setZValue(999997)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        self._handles: dict[HandlePosition, HandleItem] = {}
        for pos in HandlePosition:
            handle = HandleItem(pos)
            self._handles[pos] = handle
            self.addToGroup(handle)

        self._border = QGraphicsRectItem()
        self._border.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine))
        self._border.setBrush(Qt.GlobalColor.transparent)
        self._border.setZValue(999996)
        self.addToGroup(self._border)

    def update_rect(self, rect: QRectF) -> None:
        """Reposition all handles to surround *rect* (in scene coordinates)."""
        if rect.isEmpty():
            self.setVisible(False)
            return
        self.setVisible(True)
        self._border.setRect(rect)

        cx = rect.center().x()
        cy = rect.center().y()
        positions: dict[HandlePosition, QPointF] = {
            HandlePosition.TOP_LEFT: rect.topLeft(),
            HandlePosition.TOP_CENTER: QPointF(cx, rect.top()),
            HandlePosition.TOP_RIGHT: rect.topRight(),
            HandlePosition.MIDDLE_LEFT: QPointF(rect.left(), cy),
            HandlePosition.MIDDLE_RIGHT: QPointF(rect.right(), cy),
            HandlePosition.BOTTOM_LEFT: rect.bottomLeft(),
            HandlePosition.BOTTOM_CENTER: QPointF(cx, rect.bottom()),
            HandlePosition.BOTTOM_RIGHT: rect.bottomRight(),
        }
        for pos, point in positions.items():
            self._handles[pos].setPos(point)

    def handle_at(self, scene_pos: QPointF) -> HandlePosition | None:
        """Return which handle (if any) is at *scene_pos*."""
        for pos, handle in self._handles.items():
            hr = handle.sceneBoundingRect()
            # Expand hit area slightly for usability
            hr.adjust(-2, -2, 2, 2)
            if hr.contains(scene_pos):
                return pos
        return None

    def add_to_scene(self) -> None:
        if self.scene() is None:
            self._scene.addItem(self)

    def remove_from_scene(self) -> None:
        if self.scene() is not None:
            self._scene.removeItem(self)
