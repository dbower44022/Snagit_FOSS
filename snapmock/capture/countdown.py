"""The delay countdown badge (PRD 4.1)."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

CAPTURE_UI_PROPERTY = "snapmock_capture_ui"


class CountdownBadge(QWidget):
    """A small frameless badge showing the seconds left before the grab.

    Signals
    -------
    cancel_requested()
        Escape was pressed or the badge was clicked.
    """

    cancel_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setProperty(CAPTURE_UI_PROPERTY, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(72, 72)
        self._remaining = 0

    @property
    def remaining(self) -> int:
        return self._remaining

    def set_remaining(self, seconds: int) -> None:
        self._remaining = max(0, seconds)
        self.update()

    def place_on(self, monitor_rect: QRect) -> None:
        """Top center of *monitor_rect* (logical pixels)."""
        x = monitor_rect.center().x() - self.width() // 2
        self.move(QPoint(x, monitor_rect.top() + 24))

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 30, 30, 220))
        painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
        painter.setPen(QColor(255, 255, 255))
        font = QFont(self.font())
        font.setPointSize(26)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self._remaining))
        painter.end()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None and event.key() == Qt.Key.Key_Escape:
            event.accept()
            self.cancel_requested.emit()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None:
            event.accept()
        self.cancel_requested.emit()
