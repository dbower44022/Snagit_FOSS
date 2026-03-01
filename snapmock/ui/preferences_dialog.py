"""PreferencesDialog — view and edit persistent application settings."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from snapmock.config.settings import AppSettings


class PreferencesDialog(QDialog):
    """Modal dialog for viewing and editing application preferences."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        # --- General group ---
        general_group = QGroupBox("General")
        general_layout = QFormLayout()

        self._autosave_cb = QCheckBox()
        self._autosave_cb.setChecked(settings.autosave_enabled())
        general_layout.addRow("Autosave enabled:", self._autosave_cb)

        self._autosave_interval_spin = QSpinBox()
        self._autosave_interval_spin.setRange(1, 60)
        self._autosave_interval_spin.setSuffix(" min")
        self._autosave_interval_spin.setValue(settings.autosave_interval_minutes())
        self._autosave_interval_spin.setEnabled(settings.autosave_enabled())
        general_layout.addRow("Autosave interval:", self._autosave_interval_spin)

        self._autosave_cb.toggled.connect(self._autosave_interval_spin.setEnabled)

        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # --- View group ---
        view_group = QGroupBox("View")
        view_layout = QFormLayout()

        self._grid_visible_cb = QCheckBox()
        self._grid_visible_cb.setChecked(settings.grid_visible())
        view_layout.addRow("Show grid:", self._grid_visible_cb)

        self._grid_size_spin = QSpinBox()
        self._grid_size_spin.setRange(1, 1000)
        self._grid_size_spin.setSuffix(" px")
        self._grid_size_spin.setValue(settings.grid_size())
        view_layout.addRow("Grid size:", self._grid_size_spin)

        self._rulers_cb = QCheckBox()
        self._rulers_cb.setChecked(settings.rulers_visible())
        view_layout.addRow("Show rulers:", self._rulers_cb)

        self._snap_to_grid_cb = QCheckBox()
        self._snap_to_grid_cb.setChecked(settings.snap_to_grid())
        view_layout.addRow("Snap to grid:", self._snap_to_grid_cb)

        view_group.setLayout(view_layout)
        layout.addWidget(view_group)

        # --- Snapshot original values ---
        self._orig: dict[str, Any] = {
            "autosave_enabled": settings.autosave_enabled(),
            "autosave_interval": settings.autosave_interval_minutes(),
            "grid_visible": settings.grid_visible(),
            "grid_size": settings.grid_size(),
            "rulers_visible": settings.rulers_visible(),
            "snap_to_grid": settings.snap_to_grid(),
        }

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

        new_autosave = self._autosave_cb.isChecked()
        if new_autosave != self._orig["autosave_enabled"]:
            changes["autosave_enabled"] = (self._orig["autosave_enabled"], new_autosave)

        new_interval = self._autosave_interval_spin.value()
        if new_interval != self._orig["autosave_interval"]:
            changes["autosave_interval"] = (self._orig["autosave_interval"], new_interval)

        new_grid_visible = self._grid_visible_cb.isChecked()
        if new_grid_visible != self._orig["grid_visible"]:
            changes["grid_visible"] = (self._orig["grid_visible"], new_grid_visible)

        new_grid_size = self._grid_size_spin.value()
        if new_grid_size != self._orig["grid_size"]:
            changes["grid_size"] = (self._orig["grid_size"], new_grid_size)

        new_rulers = self._rulers_cb.isChecked()
        if new_rulers != self._orig["rulers_visible"]:
            changes["rulers_visible"] = (self._orig["rulers_visible"], new_rulers)

        new_snap = self._snap_to_grid_cb.isChecked()
        if new_snap != self._orig["snap_to_grid"]:
            changes["snap_to_grid"] = (self._orig["snap_to_grid"], new_snap)

        return changes
