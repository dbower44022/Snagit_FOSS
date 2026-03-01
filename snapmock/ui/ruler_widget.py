"""RulerWidget — pixel ruler for horizontal and vertical axes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from snapmock.config.constants import (
    RULER_BG_COLOR,
    RULER_CURSOR_COLOR,
    RULER_SIZE,
    RULER_TEXT_COLOR,
    RULER_TICK_COLOR,
)

if TYPE_CHECKING:
    from snapmock.core.view import SnapView

# "Nice number" multipliers for tick spacing
_NICE_NUMBERS = [1, 2, 5]


def _nice_tick_interval(rough: float) -> float:
    """Find the nearest 'nice' tick interval (1, 2, 5, 10, 20, 50, ...)."""
    if rough <= 0:
        return 1.0
    magnitude = 1.0
    while magnitude * 10 <= rough:
        magnitude *= 10
    for n in _NICE_NUMBERS:
        if magnitude * n >= rough:
            return magnitude * n
    return magnitude * 10


class RulerWidget(QWidget):
    """Draws a pixel ruler alongside the SnapView viewport."""

    def __init__(
        self,
        orientation: Qt.Orientation,
        view: SnapView,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._orientation = orientation
        self._view = view
        self._cursor_scene_pos: QPointF = QPointF()
        self._font = QFont("Sans Serif", 7)

    def set_cursor_pos(self, x: float, y: float) -> None:
        self._cursor_scene_pos = QPointF(x, y)
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(RULER_BG_COLOR))

        view = self._view
        t = view.transform()
        zoom = t.m11()
        if zoom <= 0:
            painter.end()
            return

        horizontal = self._orientation == Qt.Orientation.Horizontal

        if horizontal:
            length = self.width()
            # Map viewport edges to scene x
            left_scene = view.mapToScene(0, 0).x()
            right_scene = view.mapToScene(length, 0).x()
            scene_span = right_scene - left_scene
        else:
            length = self.height()
            top_scene = view.mapToScene(0, 0).y()
            bottom_scene = view.mapToScene(0, length).y()
            scene_span = bottom_scene - top_scene

        if scene_span <= 0:
            painter.end()
            return

        # Adaptive tick spacing: want major ticks ~80-150px apart on screen
        rough_interval = (scene_span / length) * 100
        interval = _nice_tick_interval(rough_interval)

        minor_interval = interval / 5
        if minor_interval * zoom < 3:
            minor_interval = interval / 2
            if minor_interval * zoom < 3:
                minor_interval = interval

        # Determine range
        if horizontal:
            start = left_scene
            end = right_scene
        else:
            start = top_scene
            end = bottom_scene

        # Snap start to interval
        first_major = int(start / interval) * interval
        if first_major > start:
            first_major -= interval

        painter.setFont(self._font)
        tick_pen = QPen(QColor(RULER_TICK_COLOR), 1)
        text_pen = QPen(QColor(RULER_TEXT_COLOR))

        # Draw minor ticks
        painter.setPen(tick_pen)
        minor_start = int(start / minor_interval) * minor_interval
        pos = minor_start
        while pos <= end:
            px = self._scene_to_widget(pos, horizontal)
            if 0 <= px <= length:
                if horizontal:
                    painter.drawLine(int(px), RULER_SIZE - 4, int(px), RULER_SIZE)
                else:
                    painter.drawLine(RULER_SIZE - 4, int(px), RULER_SIZE, int(px))
            pos += minor_interval

        # Draw major ticks + labels
        pos = first_major
        while pos <= end:
            px = self._scene_to_widget(pos, horizontal)
            if 0 <= px <= length:
                painter.setPen(tick_pen)
                if horizontal:
                    painter.drawLine(int(px), 0, int(px), RULER_SIZE)
                else:
                    painter.drawLine(0, int(px), RULER_SIZE, int(px))

                painter.setPen(text_pen)
                label = str(int(pos))
                if horizontal:
                    painter.drawText(int(px) + 2, RULER_SIZE - 5, label)
                else:
                    painter.save()
                    painter.translate(RULER_SIZE - 3, int(px) + 2)
                    painter.rotate(-90)
                    painter.drawText(0, 0, label)
                    painter.restore()
            pos += interval

        # Cursor marker (red triangle)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(RULER_CURSOR_COLOR))
        if horizontal:
            cx = self._scene_to_widget(self._cursor_scene_pos.x(), True)
            if 0 <= cx <= length:
                tri = QPolygonF(
                    [
                        QPointF(cx - 4, RULER_SIZE),
                        QPointF(cx + 4, RULER_SIZE),
                        QPointF(cx, RULER_SIZE - 6),
                    ]
                )
                painter.drawPolygon(tri)
        else:
            cy = self._scene_to_widget(self._cursor_scene_pos.y(), False)
            if 0 <= cy <= length:
                tri = QPolygonF(
                    [
                        QPointF(RULER_SIZE, cy - 4),
                        QPointF(RULER_SIZE, cy + 4),
                        QPointF(RULER_SIZE - 6, cy),
                    ]
                )
                painter.drawPolygon(tri)

        painter.end()

    def _scene_to_widget(self, scene_val: float, horizontal: bool) -> float:
        """Convert a scene coordinate to widget pixel position."""
        if horizontal:
            vp_pt = self._view.mapFromScene(QPointF(scene_val, 0))
            return float(vp_pt.x())
        else:
            vp_pt = self._view.mapFromScene(QPointF(0, scene_val))
            return float(vp_pt.y())
