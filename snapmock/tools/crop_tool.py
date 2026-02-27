"""CropTool — draw a crop rectangle on the canvas."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.raster_commands import CropCanvasCommand
from snapmock.tools.base_tool import BaseTool


class CropTool(BaseTool):
    """Interactive crop tool — drag to define crop region."""

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._end: QPointF = QPointF()
        self._dragging: bool = False

    @property
    def tool_id(self) -> str:
        return "crop"

    @property
    def display_name(self) -> str:
        return "Crop"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

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
        self._end = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if not self._dragging or self._scene is None:
            return False
        self._end = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._dragging = False
        crop_rect = QRectF(self._start, self._end).normalized()
        if crop_rect.width() > 10 and crop_rect.height() > 10:
            cmd = CropCanvasCommand(self._scene, crop_rect)
            self._scene.command_stack.push(cmd)
        return True
