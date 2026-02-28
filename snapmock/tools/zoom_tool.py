"""ZoomTool — click to zoom in/out, drag to zoom to rectangle."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPen
from PyQt6.QtWidgets import QGraphicsRectItem

from snapmock.config.constants import DRAG_THRESHOLD
from snapmock.tools.base_tool import BaseTool


class ZoomTool(BaseTool):
    """Zoom tool: left-click zooms in, Alt+click zooms out, drag draws zoom rect."""

    def __init__(self) -> None:
        super().__init__()
        self._dragging: bool = False
        self._drag_start: QPointF = QPointF()
        self._zoom_rect_item: QGraphicsRectItem | None = None

    @property
    def tool_id(self) -> str:
        return "zoom"

    @property
    def display_name(self) -> str:
        return "Zoom"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def is_active_operation(self) -> bool:
        return self._dragging

    @property
    def status_hint(self) -> str:
        return "Click to zoom in | Alt+click to zoom out | Drag to zoom region"

    def _scene_pos(self, event: QMouseEvent) -> QPointF | None:
        view = self._view
        if view is not None:
            return view.mapToScene(event.pos())
        return None

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        pos = self._scene_pos(event)
        if pos is None:
            return False
        self._drag_start = pos
        self._dragging = True
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if not self._dragging or self._scene is None:
            return False
        pos = self._scene_pos(event)
        if pos is None:
            return False
        rect = QRectF(self._drag_start, pos).normalized()
        if rect.width() < DRAG_THRESHOLD and rect.height() < DRAG_THRESHOLD:
            return True

        if self._zoom_rect_item is None:
            pen = QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine)
            item = QGraphicsRectItem(rect)
            item.setPen(pen)
            item.setBrush(QColor(0, 120, 215, 30))
            item.setZValue(999999)
            self._scene.addItem(item)
            self._zoom_rect_item = item
        else:
            self._zoom_rect_item.setRect(rect)
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if not self._dragging or self._scene is None:
            return False
        self._dragging = False
        pos = self._scene_pos(event)
        view = self._view

        # Remove zoom rect overlay
        if self._zoom_rect_item is not None:
            self._scene.removeItem(self._zoom_rect_item)
            self._zoom_rect_item = None

        if view is None or pos is None:
            return True

        delta = pos - self._drag_start
        if abs(delta.x()) < DRAG_THRESHOLD and abs(delta.y()) < DRAG_THRESHOLD:
            # Click zoom: Alt = zoom out, else zoom in
            alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            if alt:
                view.zoom_out()
            else:
                view.zoom_in()
        else:
            # Drag zoom: fit the rect
            rect = QRectF(self._drag_start, pos).normalized()
            view.zoom_to_rect(rect)
        return True

    def cancel(self) -> None:
        if self._zoom_rect_item is not None and self._scene is not None:
            self._scene.removeItem(self._zoom_rect_item)
            self._zoom_rect_item = None
        self._dragging = False

    def deactivate(self) -> None:
        self.cancel()
        super().deactivate()
