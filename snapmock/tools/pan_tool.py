"""PanTool — click-drag to pan the viewport."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.tools.base_tool import BaseTool


class PanTool(BaseTool):
    """Hand tool for panning the viewport by click-drag."""

    def __init__(self) -> None:
        super().__init__()
        self._panning: bool = False
        self._pan_start: QPoint = QPoint()

    @property
    def tool_id(self) -> str:
        return "pan"

    @property
    def display_name(self) -> str:
        return "Pan"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.OpenHandCursor

    @property
    def is_active_operation(self) -> bool:
        return self._panning

    @property
    def status_hint(self) -> str:
        return "Click and drag to pan | Middle-mouse also pans"

    def mouse_press(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        view = self._view
        if view is None:
            return False
        self._panning = True
        self._pan_start = event.pos()
        view.setCursor(Qt.CursorShape.ClosedHandCursor)
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if not self._panning:
            return False
        view = self._view
        if view is None:
            return False
        delta = event.pos() - self._pan_start
        self._pan_start = event.pos()
        h_bar = view.horizontalScrollBar()
        v_bar = view.verticalScrollBar()
        if h_bar is not None:
            h_bar.setValue(h_bar.value() - delta.x())
        if v_bar is not None:
            v_bar.setValue(v_bar.value() - delta.y())
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if not self._panning:
            return False
        self._panning = False
        view = self._view
        if view is not None:
            view.setCursor(Qt.CursorShape.OpenHandCursor)
        return True

    def cancel(self) -> None:
        self._panning = False
        view = self._view
        if view is not None:
            view.unsetCursor()

    def deactivate(self) -> None:
        self.cancel()
        super().deactivate()
