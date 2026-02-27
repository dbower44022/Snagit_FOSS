"""Resize Image dialog — scale the entire image/canvas."""

from __future__ import annotations

from PyQt6.QtCore import QSizeF
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ResizeImageDialog(QDialog):
    """Dialog for resizing the entire image (scaling all content)."""

    def __init__(
        self,
        current_size: QSizeF,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resize Image")
        self.setMinimumWidth(350)

        self._original_w = int(current_size.width())
        self._original_h = int(current_size.height())
        self._aspect_ratio = self._original_w / max(self._original_h, 1)
        self._lock_aspect = True
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
        self._lock_cb.setChecked(True)
        self._lock_cb.toggled.connect(self._on_lock_toggled)
        size_layout.addWidget(self._lock_cb, 2, 0, 1, 2)

        # Percentage mode
        size_layout.addWidget(QLabel("Scale:"), 3, 0)
        self._pct_spin = QSpinBox()
        self._pct_spin.setRange(1, 10000)
        self._pct_spin.setValue(100)
        self._pct_spin.setSuffix(" %")
        self._pct_spin.valueChanged.connect(self._on_percent_changed)
        size_layout.addWidget(self._pct_spin, 3, 1)

        size_group.setLayout(size_layout)
        layout.addWidget(size_group)

        self._w_spin.valueChanged.connect(self._on_width_changed)
        self._h_spin.valueChanged.connect(self._on_height_changed)

        # --- Interpolation ---
        interp_group = QGroupBox("Interpolation")
        interp_layout = QGridLayout()
        interp_layout.addWidget(QLabel("Method:"), 0, 0)
        self._interp_combo = QComboBox()
        self._interp_combo.addItems(["Nearest", "Bilinear", "Bicubic", "Lanczos"])
        self._interp_combo.setCurrentText("Bilinear")
        interp_layout.addWidget(self._interp_combo, 0, 1)
        interp_group.setLayout(interp_layout)
        layout.addWidget(interp_group)

        # --- Options ---
        self._all_layers_cb = QCheckBox("Resize all layers")
        self._all_layers_cb.setChecked(True)
        layout.addWidget(self._all_layers_cb)

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
        self._update_percent()

    def _on_height_changed(self, value: int) -> None:
        if self._updating:
            return
        if self._lock_aspect:
            self._updating = True
            self._w_spin.setValue(max(1, int(value * self._aspect_ratio)))
            self._updating = False
        self._update_percent()

    def _on_percent_changed(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        self._w_spin.setValue(max(1, int(self._original_w * value / 100)))
        self._h_spin.setValue(max(1, int(self._original_h * value / 100)))
        self._updating = False

    def _update_percent(self) -> None:
        if self._updating:
            return
        self._updating = True
        pct = int(self._w_spin.value() / max(self._original_w, 1) * 100)
        self._pct_spin.setValue(max(1, pct))
        self._updating = False

    # --- results ---

    def new_size(self) -> QSizeF:
        return QSizeF(self._w_spin.value(), self._h_spin.value())

    def interpolation(self) -> str:
        return self._interp_combo.currentText()

    def resize_all_layers(self) -> bool:
        return self._all_layers_cb.isChecked()
