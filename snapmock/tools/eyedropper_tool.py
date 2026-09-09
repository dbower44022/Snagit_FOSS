"""EyedropperTool — pick a color from the canvas."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QCursor, QMouseEvent

from snapmock.tools.base_tool import BaseTool
from snapmock.ui.cursors import eyedropper_cursor


class EyedropperTool(BaseTool):
    """Click on the canvas to sample a color.

    Since BaseTool doesn't inherit QObject, the picked color is stored
    and can be queried after mouse_press returns True.
    """

    def __init__(self) -> None:
        super().__init__()
        self._picked_color: QColor = QColor()
        self._pick_serial = 0
        self._pick_callback: Callable[[QColor], None] | None = None

    @property
    def tool_id(self) -> str:
        return "eyedropper"

    @property
    def display_name(self) -> str:
        return "Eyedropper"

    @property
    def cursor(self) -> QCursor:
        """The dropper glyph with its tip as the hotspot (General UI PRD 6.6)."""
        return eyedropper_cursor()

    @property
    def picked_color(self) -> QColor:
        return QColor(self._picked_color)

    @property
    def pick_serial(self) -> int:
        """Counts picks, so a caller can tell whether one happened since it last looked."""
        return self._pick_serial

    def set_pick_callback(self, callback: Callable[[QColor], None] | None) -> None:
        """Called with each picked colour; the Tool Options Bar shows it (PRD 5.3)."""
        self._pick_callback = callback

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
        self._pick_serial += 1
        if self._pick_callback is not None:
            self._pick_callback(self.picked_color)
        return True
