"""ColorPicker — color swatch widget with QColorDialog integration."""

from __future__ import annotations

from PyQt6.QtCore import QRect, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QColorDialog, QHBoxLayout, QPushButton, QWidget


class _SwatchButton(QPushButton):
    """A button that paints its current color, with checkerboard behind alpha."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor("red")

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor) -> None:
        self._color = QColor(value)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        inner = self.rect().adjusted(1, 1, -1, -1)

        # Draw checkerboard behind any color with alpha < 255
        if self._color.alpha() < 255:
            cell = 4
            light = QColor(204, 204, 204)
            dark = QColor(153, 153, 153)
            for y in range(inner.top(), inner.bottom() + 1, cell):
                for x in range(inner.left(), inner.right() + 1, cell):
                    even = ((x - inner.left()) // cell + (y - inner.top()) // cell) % 2 == 0
                    c = light if even else dark
                    w = min(cell, inner.right() + 1 - x)
                    h = min(cell, inner.bottom() + 1 - y)
                    painter.fillRect(QRect(x, y, w, h), c)

        # Draw the actual color on top
        painter.fillRect(inner, self._color)

        # Border
        painter.setPen(QColor("#888888"))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()


class ColorPicker(QWidget):
    """A widget that shows the current color swatch and opens QColorDialog on click.

    When ``allow_transparent`` is True (the default), a small toggle button
    appears next to the swatch for quickly switching to/from transparent.

    Signals
    -------
    color_changed(QColor)
        Emitted when the user selects a new color.
    """

    color_changed = pyqtSignal(QColor)

    def __init__(
        self,
        color: QColor | None = None,
        parent: QWidget | None = None,
        *,
        allow_transparent: bool = True,
    ) -> None:
        super().__init__(parent)
        self._color = color if color is not None else QColor("red")
        self._last_opaque = QColor(self._color) if self._color.alpha() > 0 else QColor("red")
        self._allow_transparent = allow_transparent

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._swatch = _SwatchButton()
        self._swatch.setFixedSize(32, 32)
        self._swatch.color = self._color
        self._swatch.clicked.connect(self._open_dialog)
        layout.addWidget(self._swatch)

        self._transparent_btn: QPushButton | None = None
        if allow_transparent:
            btn = QPushButton("\u2205")  # ∅ empty-set symbol
            btn.setFixedSize(24, 32)
            btn.setCheckable(True)
            btn.setChecked(self._color.alpha() == 0)
            btn.setToolTip("Transparent (no color)")
            btn.setStyleSheet(
                "QPushButton { font-size: 14px; }"
                "QPushButton:checked { background-color: #cde; border: 1px solid #68a; }"
            )
            btn.clicked.connect(self._on_transparent_toggled)
            layout.addWidget(btn)
            self._transparent_btn = btn

    @property
    def color(self) -> QColor:
        return QColor(self._color)

    @color.setter
    def color(self, value: QColor) -> None:
        self._color = QColor(value)
        if value.alpha() > 0:
            self._last_opaque = QColor(value)
        self._swatch.color = self._color
        if self._transparent_btn is not None:
            self._transparent_btn.setChecked(value.alpha() == 0)

    def _open_dialog(self) -> None:
        options = QColorDialog.ColorDialogOption.ShowAlphaChannel
        new_color = QColorDialog.getColor(self._color, self, "Select Color", options=options)
        if new_color.isValid():
            self._color = new_color
            if new_color.alpha() > 0:
                self._last_opaque = QColor(new_color)
            self._swatch.color = self._color
            if self._transparent_btn is not None:
                self._transparent_btn.setChecked(new_color.alpha() == 0)
            self.color_changed.emit(self._color)

    def _on_transparent_toggled(self, checked: bool) -> None:
        if checked:
            # Save current color and go transparent
            if self._color.alpha() > 0:
                self._last_opaque = QColor(self._color)
            self._color = QColor(0, 0, 0, 0)
        else:
            # Restore last opaque color
            self._color = QColor(self._last_opaque)
        self._swatch.color = self._color
        self.color_changed.emit(self._color)
