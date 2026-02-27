"""SnapStatusBar — displays cursor position, zoom level, selection info."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QStatusBar

if TYPE_CHECKING:
    from snapmock.core.view import SnapView


class SnapStatusBar(QStatusBar):
    """Status bar showing cursor position and zoom level."""

    def __init__(self, view: SnapView) -> None:
        super().__init__()
        self._view = view

        self._zoom_label = QLabel(f"Zoom: {view.zoom_percent}%")
        self._cursor_label = QLabel("Cursor: 0, 0")
        self.addPermanentWidget(self._cursor_label)
        self.addPermanentWidget(self._zoom_label)

        view.zoom_changed.connect(self._on_zoom_changed)

    def _on_zoom_changed(self, percent: int) -> None:
        self._zoom_label.setText(f"Zoom: {percent}%")

    def update_cursor_pos(self, x: float, y: float) -> None:
        self._cursor_label.setText(f"Cursor: {x:.0f}, {y:.0f}")
