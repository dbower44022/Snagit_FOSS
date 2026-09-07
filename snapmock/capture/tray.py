"""The system tray icon image (PRD 3.2). Drawn in code; no icon asset exists yet."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def make_tray_icon(size: int = 64) -> QIcon:
    """A camera-like glyph: a rounded body, a lens ring, and a corner bracket."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    unit = size / 16
    body = QRectF(1 * unit, 4 * unit, 14 * unit, 10 * unit)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(40, 40, 40))
    painter.drawRoundedRect(body, 2 * unit, 2 * unit)
    painter.drawRoundedRect(QRectF(5 * unit, 2 * unit, 6 * unit, 3 * unit), unit, unit)
    painter.setPen(QPen(QColor(250, 250, 250), 1.6 * unit))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(5 * unit, 6 * unit, 6 * unit, 6 * unit))
    painter.setPen(QPen(QColor(90, 170, 255), 1.4 * unit))
    painter.drawPoint(QPointF(12.5 * unit, 6.5 * unit))
    painter.end()
    return QIcon(pixmap)
