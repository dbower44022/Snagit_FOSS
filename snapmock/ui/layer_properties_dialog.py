"""LayerPropertiesDialog — inspect and edit properties of a Layer."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from snapmock.core.layer import Layer


class LayerPropertiesDialog(QDialog):
    """Modal dialog for viewing and editing layer properties."""

    def __init__(
        self,
        layer: Layer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._layer = layer
        self.setWindowTitle("Layer Properties")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # --- Properties group ---
        props_group = QGroupBox("Properties")
        props_layout = QFormLayout()

        self._name_edit = QLineEdit(layer.name)
        props_layout.addRow("Name:", self._name_edit)

        self._opacity_spin = QSpinBox()
        self._opacity_spin.setRange(0, 100)
        self._opacity_spin.setSuffix("%")
        self._opacity_spin.setValue(int(layer.opacity * 100))
        props_layout.addRow("Opacity:", self._opacity_spin)

        self._visible_cb = QCheckBox()
        self._visible_cb.setChecked(layer.visible)
        props_layout.addRow("Visible:", self._visible_cb)

        self._locked_cb = QCheckBox()
        self._locked_cb.setChecked(layer.locked)
        props_layout.addRow("Locked:", self._locked_cb)

        self._item_count_label = QLabel(str(len(layer.item_ids)))
        props_layout.addRow("Item count:", self._item_count_label)

        props_group.setLayout(props_layout)
        layout.addWidget(props_group)

        # --- Snapshot originals ---
        self._orig_name = layer.name
        self._orig_opacity = layer.opacity
        self._orig_visible = layer.visible
        self._orig_locked = layer.locked

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_changes(self) -> dict[str, tuple[object, object]]:
        """Return only properties that actually changed.

        Returns a dict keyed by property name, with ``(old_value, new_value)`` tuples.
        """
        changes: dict[str, tuple[object, object]] = {}

        new_name = self._name_edit.text()
        if new_name != self._orig_name:
            changes["name"] = (self._orig_name, new_name)

        new_opacity = self._opacity_spin.value() / 100.0
        if new_opacity != self._orig_opacity:
            changes["opacity"] = (self._orig_opacity, new_opacity)

        new_visible = self._visible_cb.isChecked()
        if new_visible != self._orig_visible:
            changes["visible"] = (self._orig_visible, new_visible)

        new_locked = self._locked_cb.isChecked()
        if new_locked != self._orig_locked:
            changes["locked"] = (self._orig_locked, new_locked)

        return changes
