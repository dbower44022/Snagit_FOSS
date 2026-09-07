"""PreferencesDialog — view and edit persistent application settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from snapmock.config.constants import LIBRARY_THUMBNAIL_MAX, LIBRARY_THUMBNAIL_MIN
from snapmock.config.settings import AppSettings
from snapmock.library.model import SORT_OPTIONS


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

        # --- Library group (Library PRD 8.1) ---
        self._library_group = QGroupBox("Library")
        lib_layout = QFormLayout()

        dir_row = QHBoxLayout()
        self._library_dir_edit = QLineEdit(str(settings.library_directory()))
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_library_dir)
        dir_row.addWidget(self._library_dir_edit, 1)
        dir_row.addWidget(browse_btn)
        lib_layout.addRow("Library directory:", dir_row)

        self._library_auto_open_cb = QCheckBox()
        self._library_auto_open_cb.setChecked(settings.library_auto_open())
        lib_layout.addRow("Auto-open captures:", self._library_auto_open_cb)

        self._library_view_combo = QComboBox()
        self._library_view_combo.addItem("Grid", "grid")
        self._library_view_combo.addItem("Preview (List)", "list")
        self._library_view_combo.setCurrentIndex(
            max(0, self._library_view_combo.findData(settings.library_default_view_mode()))
        )
        lib_layout.addRow("Default view mode:", self._library_view_combo)

        thumb_row = QHBoxLayout()
        self._library_thumb_slider = QSlider(Qt.Orientation.Horizontal)
        self._library_thumb_slider.setRange(LIBRARY_THUMBNAIL_MIN, LIBRARY_THUMBNAIL_MAX)
        self._library_thumb_slider.setValue(settings.library_default_thumbnail_size())
        self._library_thumb_value = QSpinBox()
        self._library_thumb_value.setRange(LIBRARY_THUMBNAIL_MIN, LIBRARY_THUMBNAIL_MAX)
        self._library_thumb_value.setSuffix(" px")
        self._library_thumb_value.setValue(settings.library_default_thumbnail_size())
        self._library_thumb_slider.valueChanged.connect(self._library_thumb_value.setValue)
        self._library_thumb_value.valueChanged.connect(self._library_thumb_slider.setValue)
        thumb_row.addWidget(self._library_thumb_slider, 1)
        thumb_row.addWidget(self._library_thumb_value)
        lib_layout.addRow("Default thumbnail size:", thumb_row)

        self._library_sort_combo = QComboBox()
        for sort_id, label in SORT_OPTIONS:
            self._library_sort_combo.addItem(label, sort_id)
        self._library_sort_combo.setCurrentIndex(
            max(0, self._library_sort_combo.findData(settings.library_default_sort()))
        )
        lib_layout.addRow("Default sort order:", self._library_sort_combo)

        self._library_toast_cb = QCheckBox()
        self._library_toast_cb.setChecked(settings.library_toast_enabled())
        lib_layout.addRow("Toast notifications:", self._library_toast_cb)

        self._library_group.setLayout(lib_layout)
        layout.addWidget(self._library_group)

        # --- Snapshot original values ---
        self._orig: dict[str, Any] = {
            "autosave_enabled": settings.autosave_enabled(),
            "autosave_interval": settings.autosave_interval_minutes(),
            "grid_visible": settings.grid_visible(),
            "grid_size": settings.grid_size(),
            "rulers_visible": settings.rulers_visible(),
            "snap_to_grid": settings.snap_to_grid(),
            "library_directory": str(settings.library_directory()),
            "library_auto_open": settings.library_auto_open(),
            "library_default_view_mode": settings.library_default_view_mode(),
            "library_default_thumbnail_size": settings.library_default_thumbnail_size(),
            "library_default_sort": settings.library_default_sort(),
            "library_toast_enabled": settings.library_toast_enabled(),
        }

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def focus_library_section(self) -> None:
        """Bring the Library settings into view (Library > Library Preferences…)."""
        self._library_dir_edit.setFocus()

    def _browse_library_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Library Directory", self._library_dir_edit.text()
        )
        if chosen:
            self._library_dir_edit.setText(str(Path(chosen)))

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

        library_values: dict[str, object] = {
            "library_directory": self._library_dir_edit.text().strip(),
            "library_auto_open": self._library_auto_open_cb.isChecked(),
            "library_default_view_mode": self._library_view_combo.currentData(),
            "library_default_thumbnail_size": self._library_thumb_slider.value(),
            "library_default_sort": self._library_sort_combo.currentData(),
            "library_toast_enabled": self._library_toast_cb.isChecked(),
        }
        for key, new_value in library_values.items():
            if new_value != self._orig[key]:
                changes[key] = (self._orig[key], new_value)

        return changes
