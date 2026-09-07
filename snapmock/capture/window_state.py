"""Hide-and-restore of the application's windows around a grab (PRD 3.6)."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget

from snapmock.capture.countdown import CAPTURE_UI_PROPERTY


@dataclass
class _Recorded:
    widget: QWidget
    geometry: QRect
    state: Qt.WindowState


class WindowHider:
    """Records and hides every SnapMock top-level window; restores them once."""

    def __init__(self) -> None:
        self._recorded: list[_Recorded] = []
        self._main: QMainWindow | None = None

    @property
    def is_hidden(self) -> bool:
        return bool(self._recorded)

    @staticmethod
    def _is_app_window(widget: QWidget) -> bool:
        if not widget.isWindow() or not widget.isVisible():
            return False
        if isinstance(widget, QMenu) or widget.property(CAPTURE_UI_PROPERTY):
            return False
        if widget.windowType() in (Qt.WindowType.ToolTip, Qt.WindowType.Popup):
            return False
        return True

    def hide_all(self) -> None:
        """Record geometry and state of every visible window, then hide them."""
        if self._recorded:
            return
        for widget in QApplication.topLevelWidgets():
            if not self._is_app_window(widget):
                continue
            self._recorded.append(
                _Recorded(widget, QRect(widget.geometry()), widget.windowState())
            )
            if isinstance(widget, QMainWindow) and self._main is None:
                self._main = widget
            widget.hide()

    def any_exposed(self) -> bool:
        """Whether any hidden window still has an exposed native surface."""
        for rec in self._recorded:
            handle = rec.widget.windowHandle()
            if handle is not None and handle.isExposed():
                return True
        return False

    def restore(self) -> None:
        """Show every hidden window in its recorded state, then activate the main one."""
        recorded, self._recorded = self._recorded, []
        main, self._main = self._main, None
        for rec in recorded:
            widget = rec.widget
            if widget.windowState() & Qt.WindowState.WindowMinimized:
                widget.setWindowState(rec.state)
            if rec.state & (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen):
                widget.setWindowState(rec.state)
            else:
                widget.setGeometry(rec.geometry)
            widget.show()
        if main is not None:
            main.raise_()
            main.activateWindow()

    def recorded_geometry(self, widget: QWidget) -> QRect | None:
        for rec in self._recorded:
            if rec.widget is widget:
                return QRect(rec.geometry)
        return None
