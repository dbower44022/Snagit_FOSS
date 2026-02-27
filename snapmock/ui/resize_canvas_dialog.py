"""Resize Canvas dialog — change canvas dimensions with anchor point selection."""

from __future__ import annotations

from PyQt6.QtCore import QSizeF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ResizeCanvasDialog(QDialog):
    """Dialog for resizing the canvas with anchor point and fill color."""

    def __init__(
        self,
        current_size: QSizeF,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resize Canvas")
        self.setMinimumWidth(350)

        self._original_w = int(current_size.width())
        self._original_h = int(current_size.height())
        self._aspect_ratio = self._original_w / max(self._original_h, 1)
        self._lock_aspect = False
        self._anchor = 4  # center
        self._fill_color = QColor("white")
        self._updating = False

        layout = QVBoxLayout(self)

        # --- Size group ---
        size_group = QGroupBox("New Size")
        size_layout = QGridLayout()

        size_layout.addWidget(QLabel("Width:"), 0, 0)
        self._w_spin = QSpinBox()
        self._w_spin.setRange(1, 32000)
        self._w_spin.setValue(self._original_w)
        self._w_spin.setSuffix(" px")
        size_layout.addWidget(self._w_spin, 0, 1)

        size_layout.addWidget(QLabel("Height:"), 1, 0)
        self._h_spin = QSpinBox()
        self._h_spin.setRange(1, 32000)
        self._h_spin.setValue(self._original_h)
        self._h_spin.setSuffix(" px")
        size_layout.addWidget(self._h_spin, 1, 1)

        self._lock_cb = QCheckBox("Lock aspect ratio")
        self._lock_cb.toggled.connect(self._on_lock_toggled)
        size_layout.addWidget(self._lock_cb, 2, 0, 1, 2)

        size_group.setLayout(size_layout)
        layout.addWidget(size_group)

        self._w_spin.valueChanged.connect(self._on_width_changed)
        self._h_spin.valueChanged.connect(self._on_height_changed)

        # --- Anchor group ---
        anchor_group = QGroupBox("Anchor")
        anchor_layout = QGridLayout()
        self._anchor_buttons: list[QRadioButton] = []
        for i in range(9):
            btn = QRadioButton()
            btn.setChecked(i == 4)
            row, col = divmod(i, 3)
            anchor_layout.addWidget(btn, row, col)
            self._anchor_buttons.append(btn)
            btn.clicked.connect(self._make_anchor_setter(i))
        anchor_group.setLayout(anchor_layout)
        layout.addWidget(anchor_group)

        # --- Fill color ---
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Fill color:"))
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(60, 24)
        self._update_color_button()
        self._color_btn.clicked.connect(self._pick_color)
        color_layout.addWidget(self._color_btn)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        # --- Info ---
        self._info_label = QLabel(f"Current: {self._original_w} × {self._original_h} px")
        layout.addWidget(self._info_label)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_anchor_setter(self, index: int):  # type: ignore[no-untyped-def]
        def _set() -> None:
            self._anchor = index

        return _set

    def _on_lock_toggled(self, checked: bool) -> None:
        self._lock_aspect = checked
        if checked:
            self._aspect_ratio = self._w_spin.value() / max(self._h_spin.value(), 1)

    def _on_width_changed(self, value: int) -> None:
        if self._updating:
            return
        if self._lock_aspect:
            self._updating = True
            self._h_spin.setValue(max(1, int(value / self._aspect_ratio)))
            self._updating = False

    def _on_height_changed(self, value: int) -> None:
        if self._updating:
            return
        if self._lock_aspect:
            self._updating = True
            self._w_spin.setValue(max(1, int(value * self._aspect_ratio)))
            self._updating = False

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._fill_color, self)
        if color.isValid():
            self._fill_color = color
            self._update_color_button()

    def _update_color_button(self) -> None:
        self._color_btn.setStyleSheet(
            f"background-color: {self._fill_color.name()}; border: 1px solid gray;"
        )

    # --- results ---

    def new_size(self) -> QSizeF:
        return QSizeF(self._w_spin.value(), self._h_spin.value())

    def anchor(self) -> int:
        return self._anchor

    def fill_color(self) -> QColor:
        return QColor(self._fill_color)
