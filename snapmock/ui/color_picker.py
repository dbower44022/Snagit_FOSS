"""ColorPicker — color swatch widget with QColorDialog integration."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QPushButton, QWidget


class ColorPicker(QPushButton):
    """A button that shows the current color and opens a QColorDialog on click.

    Signals
    -------
    color_changed(QColor)
        Emitted when the user selects a new color.
    """

    color_changed = pyqtSignal(QColor)

    def __init__(self, color: QColor | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color if color is not None else QColor("red")
        self._update_swatch()
        self.clicked.connect(self._open_dialog)
        self.setFixedSize(32, 32)

    @property
    def color(self) -> QColor:
        return QColor(self._color)

    @color.setter
    def color(self, value: QColor) -> None:
        self._color = QColor(value)
        self._update_swatch()

    def _update_swatch(self) -> None:
        self.setStyleSheet(f"background-color: {self._color.name()}; border: 1px solid #888;")

    def _open_dialog(self) -> None:
        new_color = QColorDialog.getColor(self._color, self, "Select Color")
        if new_color.isValid():
            self._color = new_color
            self._update_swatch()
            self.color_changed.emit(self._color)
