"""EyedropperTool — pick a color from the canvas."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QMouseEvent

from snapmock.tools.base_tool import BaseTool


class EyedropperTool(BaseTool):
    """Click on the canvas to sample a color.

    Since BaseTool doesn't inherit QObject, the picked color is stored
    and can be queried after mouse_press returns True.
    """

    def __init__(self) -> None:
        super().__init__()
        self._picked_color: QColor = QColor()

    @property
    def tool_id(self) -> str:
        return "eyedropper"

    @property
    def display_name(self) -> str:
        return "Eyedropper"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def picked_color(self) -> QColor:
        return QColor(self._picked_color)

    @property
    def status_hint(self) -> str:
        return "Click to sample color"

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        # Sample the color from the scene at the click position
        scene_pos = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        # Use a 1x1 render to pick the pixel color
        from PyQt6.QtGui import QImage, QPainter

        img = QImage(1, 1, QImage.Format.Format_ARGB32)
        painter = QPainter(img)
        self._scene.render(
            painter,
            target=QRectF(0, 0, 1, 1),
            source=QRectF(scene_pos.x(), scene_pos.y(), 1, 1),
        )
        painter.end()
        self._picked_color = QColor(img.pixel(0, 0))
        return True
