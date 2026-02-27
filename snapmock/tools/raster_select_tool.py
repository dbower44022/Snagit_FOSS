"""RasterSelectTool — rectangular pixel selection on the canvas."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.tools.base_tool import BaseTool


class RasterSelectTool(BaseTool):
    """Draw a rectangular selection for raster copy/cut/paste operations."""

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._selection_rect: QRectF = QRectF()
        self._dragging: bool = False

    @property
    def tool_id(self) -> str:
        return "raster_select"

    @property
    def display_name(self) -> str:
        return "Raster Select"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def selection_rect(self) -> QRectF:
        return QRectF(self._selection_rect)

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._start = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._dragging = True
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if not self._dragging or self._scene is None:
            return False
        current = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._selection_rect = QRectF(self._start, current).normalized()
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if not self._dragging:
            return False
        self._dragging = False
        return True
