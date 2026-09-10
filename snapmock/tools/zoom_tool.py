"""ZoomTool — click to zoom in/out, drag to zoom to rectangle."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QContextMenuEvent, QCursor, QKeyEvent, QMouseEvent, QPen
from PyQt6.QtWidgets import QGraphicsRectItem

from snapmock.config.constants import DRAG_THRESHOLD
from snapmock.tools.base_tool import BaseTool
from snapmock.ui.cursors import zoom_in_cursor, zoom_out_cursor


class ZoomTool(BaseTool):
    """Zoom tool: left-click zooms in, Alt+click or right-click zooms out, drag draws a
    zoom rectangle (Navigation and Raster Operations PRD 4.3.2).

    Alt is read at the press as well as at the release, and right-click is a second
    zoom-out route, because a desktop may take Alt+left-button as its window-move gesture
    before the click reaches the view (Cinnamon's default; follow-up silence 8).
    """

    def __init__(self) -> None:
        super().__init__()
        self._dragging: bool = False
        self._drag_start: QPointF = QPointF()
        self._zoom_rect_item: QGraphicsRectItem | None = None
        self._alt_at_press: bool = False
        self._right_press: bool = False

    @property
    def tool_id(self) -> str:
        return "zoom"

    @property
    def display_name(self) -> str:
        return "Zoom"

    @property
    def cursor(self) -> QCursor:
        """Magnifier with a plus; Alt swaps in the minus (General UI PRD 6.6)."""
        return zoom_in_cursor()

    @property
    def is_active_operation(self) -> bool:
        return self._dragging

    def _show_alt_cursor(self, alt: bool) -> None:
        view = self._view
        if view is not None:
            view.set_hover_cursor(zoom_out_cursor() if alt else None)

    def key_press(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Alt:
            self._show_alt_cursor(True)
        return False

    def key_release(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Alt:
            self._show_alt_cursor(False)
        return False

    @property
    def status_hint(self) -> str:
        return "Click to zoom in | Alt+click or right-click to zoom out | Drag to zoom region"

    def _scene_pos(self, event: QMouseEvent) -> QPointF | None:
        view = self._view
        if view is not None:
            return view.mapToScene(event.pos())
        return None

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None:
            return False
        if event.button() == Qt.MouseButton.RightButton:
            self._right_press = True
            return True
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        pos = self._scene_pos(event)
        if pos is None:
            return False
        self._drag_start = pos
        self._dragging = True
        self._alt_at_press = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if not self._dragging or self._scene is None:
            self._show_alt_cursor(bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
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
        if self._scene is None:
            return False
        if event.button() == Qt.MouseButton.RightButton:
            # The second zoom-out route; the canvas context menu stays closed
            pressed_here = self._right_press
            self._right_press = False
            if pressed_here and self._view is not None:
                self._view.zoom_out()
            return pressed_here
        if not self._dragging:
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
            # Click zoom: Alt at the press or the release = zoom out, else zoom in
            alt = self._alt_at_press or bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            self._alt_at_press = False
            if alt:
                view.zoom_out()
            else:
                view.zoom_in()
        else:
            # Drag zoom: fit the rect
            rect = QRectF(self._drag_start, pos).normalized()
            view.zoom_to_rect(rect)
        return True

    def context_menu(self, event: QContextMenuEvent) -> bool:
        """Right-click zooms out, so the canvas context menu does not open."""
        return True

    def cancel(self) -> None:
        if self._zoom_rect_item is not None and self._scene is not None:
            self._scene.removeItem(self._zoom_rect_item)
            self._zoom_rect_item = None
        self._dragging = False
        self._alt_at_press = False
        self._right_press = False

    def deactivate(self) -> None:
        self.cancel()
        super().deactivate()
