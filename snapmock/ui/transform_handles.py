"""TransformHandles — resize/rotate handles displayed around selected items."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsRectItem,
)

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene

HANDLE_SIZE = 8.0
HANDLE_HALF = HANDLE_SIZE / 2.0
ROTATE_HANDLE_OFFSET = 30.0
ROTATE_HANDLE_RADIUS = 5.0


class HandlePosition(Enum):
    TOP_LEFT = auto()
    TOP_CENTER = auto()
    TOP_RIGHT = auto()
    MIDDLE_LEFT = auto()
    MIDDLE_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_CENTER = auto()
    BOTTOM_RIGHT = auto()
    ROTATE = auto()


_CURSOR_MAP: dict[HandlePosition, Qt.CursorShape] = {
    HandlePosition.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    HandlePosition.TOP_CENTER: Qt.CursorShape.SizeVerCursor,
    HandlePosition.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.MIDDLE_LEFT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.MIDDLE_RIGHT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.BOTTOM_CENTER: Qt.CursorShape.SizeVerCursor,
    HandlePosition.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    HandlePosition.ROTATE: Qt.CursorShape.CrossCursor,
}

# Corner handles used for proportional resize
CORNER_HANDLES = {
    HandlePosition.TOP_LEFT,
    HandlePosition.TOP_RIGHT,
    HandlePosition.BOTTOM_LEFT,
    HandlePosition.BOTTOM_RIGHT,
}

# Edge midpoint handles for single-axis resize
EDGE_HANDLES = {
    HandlePosition.TOP_CENTER,
    HandlePosition.BOTTOM_CENTER,
    HandlePosition.MIDDLE_LEFT,
    HandlePosition.MIDDLE_RIGHT,
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


class RotateHandleItem(QGraphicsEllipseItem):
    """Circular handle for rotation."""

    def __init__(self) -> None:
        r = ROTATE_HANDLE_RADIUS
        super().__init__(-r, -r, r * 2, r * 2)
        self.position = HandlePosition.ROTATE
        self.setPen(QPen(QColor(0, 120, 215), 1))
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setZValue(999998)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)


class TransformHandles(QGraphicsItemGroup):
    """8 resize handles + 1 rotate handle around the bounding rect.

    This is ephemeral UI — not serialized, not part of any layer.
    """

    def __init__(self, scene: SnapScene) -> None:
        super().__init__()
        self._scene = scene
        self.setZValue(999997)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        self._handles: dict[HandlePosition, HandleItem | RotateHandleItem] = {}
        for pos in HandlePosition:
            if pos == HandlePosition.ROTATE:
                continue
            handle = HandleItem(pos)
            self._handles[pos] = handle
            self.addToGroup(handle)

        # Rotate handle (circular, above top-center)
        self._rotate_handle = RotateHandleItem()
        self._handles[HandlePosition.ROTATE] = self._rotate_handle
        self.addToGroup(self._rotate_handle)

        # Line from top-center to rotate handle
        self._rotate_line = QGraphicsLineItem()
        self._rotate_line.setPen(QPen(QColor(0, 120, 215), 1))
        self._rotate_line.setZValue(999997)
        self.addToGroup(self._rotate_line)

        self._border = QGraphicsRectItem()
        self._border.setPen(
            QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine)
        )
        self._border.setBrush(Qt.GlobalColor.transparent)
        self._border.setZValue(999996)
        self.addToGroup(self._border)

        self._current_rect = QRectF()

    @property
    def current_rect(self) -> QRectF:
        return QRectF(self._current_rect)

    def update_rect(self, rect: QRectF) -> None:
        """Reposition all handles to surround *rect* (scene coords)."""
        if rect.isEmpty():
            self.setVisible(False)
            return
        self.setVisible(True)
        self._current_rect = QRectF(rect)
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

        # Rotate handle above top-center
        rotate_pos = QPointF(cx, rect.top() - ROTATE_HANDLE_OFFSET)
        self._rotate_handle.setPos(rotate_pos)
        self._rotate_line.setLine(
            cx, rect.top(), cx, rect.top() - ROTATE_HANDLE_OFFSET
        )

    def handle_at(self, scene_pos: QPointF) -> HandlePosition | None:
        """Return which handle (if any) is at *scene_pos*."""
        # Check rotate handle first (it's above the border)
        rr = self._rotate_handle.sceneBoundingRect()
        rr.adjust(-3, -3, 3, 3)
        if rr.contains(scene_pos):
            return HandlePosition.ROTATE

        for pos, handle in self._handles.items():
            if pos == HandlePosition.ROTATE:
                continue
            hr = handle.sceneBoundingRect()
            hr.adjust(-2, -2, 2, 2)
            if hr.contains(scene_pos):
                return pos
        return None

    def anchor_for_handle(self, handle_pos: HandlePosition) -> QPointF:
        """Return the anchor point (opposite corner/edge) for a resize handle."""
        r = self._current_rect
        cx, cy = r.center().x(), r.center().y()
        anchor_map: dict[HandlePosition, QPointF] = {
            HandlePosition.TOP_LEFT: r.bottomRight(),
            HandlePosition.TOP_CENTER: QPointF(cx, r.bottom()),
            HandlePosition.TOP_RIGHT: r.bottomLeft(),
            HandlePosition.MIDDLE_LEFT: QPointF(r.right(), cy),
            HandlePosition.MIDDLE_RIGHT: QPointF(r.left(), cy),
            HandlePosition.BOTTOM_LEFT: r.topRight(),
            HandlePosition.BOTTOM_CENTER: QPointF(cx, r.top()),
            HandlePosition.BOTTOM_RIGHT: r.topLeft(),
            HandlePosition.ROTATE: QPointF(cx, cy),  # center for rotation
        }
        return anchor_map.get(handle_pos, QPointF(cx, cy))

    def add_to_scene(self) -> None:
        if self.scene() is None:
            self._scene.addItem(self)

    def remove_from_scene(self) -> None:
        if self.scene() is not None:
            self._scene.removeItem(self)
