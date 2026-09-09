"""Toast — transient notification shown at the bottom of the main window."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class Toast(QWidget):
    """A small pill that fades in at the bottom center of its parent."""

    def __init__(self, parent: QWidget, duration_ms: int = 4000) -> None:
        super().__init__(parent)
        self._duration = duration_ms
        self._on_click: Callable[[], None] | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "Toast { background: rgba(40, 40, 40, 230); border-radius: 8px; }"
            "QLabel { color: white; }"
            "QPushButton { color: #8ec9ff; background: transparent; border: none;"
            " text-decoration: underline; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        self._label = QLabel("")
        self._link = QPushButton("")
        self._link.setAccessibleName("Toast action")
        self._link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._link.clicked.connect(self._activate)
        layout.addWidget(self._label)
        layout.addWidget(self._link)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()
        parent.installEventFilter(self)

    def show_message(
        self,
        text: str,
        link_text: str = "",
        on_click: Callable[[], None] | None = None,
    ) -> None:
        self._label.setText(text)
        self._link.setText(link_text)
        self._link.setAccessibleName(link_text)
        self._link.setVisible(bool(link_text))
        self._on_click = on_click
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(self._duration)

    def _activate(self) -> None:
        if self._on_click is not None:
            self._on_click()
        self.hide()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 40
        self.move(max(0, x), max(0, y))

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # noqa: N802
        if event is not None and event.type() == QEvent.Type.Resize and self.isVisible():
            self._reposition()
        return False
