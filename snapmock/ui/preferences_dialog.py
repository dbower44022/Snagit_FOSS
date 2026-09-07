"""PreferencesDialog — view and edit persistent application settings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from snapmock.capture.models import (
    HOTKEY_ACTION_FULL_SCREEN,
    HOTKEY_ACTION_REGION,
    HOTKEY_ACTION_WINDOW,
    CaptureMode,
    FullScreenScope,
)
from snapmock.config.constants import LIBRARY_THUMBNAIL_MAX, LIBRARY_THUMBNAIL_MIN
from snapmock.config.settings import AppSettings
from snapmock.library.model import SORT_OPTIONS

if TYPE_CHECKING:
    from snapmock.capture.manager import CaptureManager

HOTKEY_IN_USE = "In use by another application"
CURSOR_UNAVAILABLE = "Not available on this desktop"
COMMAND_LINE_FOR_ACTION = {
    HOTKEY_ACTION_REGION: "snapmock --capture region",
    HOTKEY_ACTION_WINDOW: "snapmock --capture window",
    HOTKEY_ACTION_FULL_SCREEN: "snapmock --capture full",
}
HOTKEY_LABELS = {
    HOTKEY_ACTION_REGION: "Region hotkey:",
    HOTKEY_ACTION_WINDOW: "Active window hotkey:",
    HOTKEY_ACTION_FULL_SCREEN: "Full screen hotkey:",
}
DESKTOP_SHORTCUT_HELP = (
    "Wayland and macOS desktops do not let applications register their own keyboard "
    "shortcuts. Bind a shortcut in your desktop's keyboard settings to one of these "
    "commands:\n\n"
    "    snapmock --capture region\n"
    "    snapmock --capture window\n"
    "    snapmock --capture full\n\n"
    "GNOME: Settings > Keyboard > View and Customize Shortcuts > Custom Shortcuts.\n"
    "KDE Plasma: System Settings > Shortcuts > Add Command.\n"
    "macOS: the Shortcuts application, with a keyboard shortcut on a Run Shell Script "
    "action.\n\n"
    "The desktop's own PrintScreen binding must be removed or changed first."
)


class PreferencesDialog(QDialog):
    """Modal dialog for viewing and editing application preferences."""

    def __init__(
        self,
        settings: AppSettings,
        parent: QWidget | None = None,
        *,
        capture: CaptureManager | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(350)
        self._capture = capture
        self._hotkey_edits: dict[str, QKeySequenceEdit] = {}
        self._hotkey_status: dict[str, QLabel] = {}

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

        # --- Capture group (Screen Capture PRD 8.1) ---
        self._capture_group: QGroupBox | None = None
        if capture is not None:
            self._capture_group = self._build_capture_group(settings, capture)
            layout.addWidget(self._capture_group)

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
        if capture is not None:
            self._orig.update(
                {
                    "capture_default_mode": settings.capture_default_mode(),
                    "capture_delay_seconds": settings.capture_delay_seconds(),
                    "capture_include_cursor": settings.capture_include_cursor(),
                    "capture_play_sound": settings.capture_play_sound(),
                    "capture_hide_window": settings.capture_hide_window(),
                    "capture_copy_to_clipboard": settings.capture_copy_to_clipboard(),
                    "capture_full_screen_scope": settings.capture_full_screen_scope(),
                    "capture_show_magnifier": settings.capture_show_magnifier(),
                    "capture_tray_enabled": settings.capture_tray_enabled(),
                    "capture_keep_running_in_tray": settings.capture_keep_running_in_tray(),
                }
            )

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

    def focus_capture_section(self) -> None:
        """Bring the Capture settings into view (Capture > Capture Preferences…)."""
        if self._capture_group is not None:
            self._capture_mode_combo.setFocus()

    # --- Capture group (Screen Capture PRD 8.1, 6.7, 9.2, 9.3) ---

    def _build_capture_group(self, settings: AppSettings, capture: CaptureManager) -> QGroupBox:
        group = QGroupBox("Capture")
        form = QFormLayout()
        caps = capture.capabilities

        self._capture_mode_combo = QComboBox()
        self._capture_mode_combo.addItem("Region", CaptureMode.REGION.value)
        self._capture_mode_combo.addItem("Active window", CaptureMode.ACTIVE_WINDOW.value)
        self._capture_mode_combo.addItem("Full screen", CaptureMode.FULL_SCREEN.value)
        self._capture_mode_combo.setCurrentIndex(
            max(0, self._capture_mode_combo.findData(settings.capture_default_mode()))
        )
        form.addRow("Default capture mode:", self._capture_mode_combo)

        hotkeys_supported = capture.hotkey_backend.supported
        for action in (HOTKEY_ACTION_REGION, HOTKEY_ACTION_WINDOW, HOTKEY_ACTION_FULL_SCREEN):
            if hotkeys_supported:
                form.addRow(HOTKEY_LABELS[action], self._build_hotkey_row(capture, action))
            else:
                form.addRow(HOTKEY_LABELS[action], self._build_command_row(action))
        if not hotkeys_supported:
            help_link = QLabel('<a href="#">How to set up a desktop shortcut...</a>')
            help_link.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
            help_link.linkActivated.connect(lambda _href: self.show_desktop_shortcut_help())
            form.addRow("", help_link)
        else:
            conflicts = QLabel(
                "GNOME on X11 and Windows 11 with the Snipping Tool shortcut both claim "
                "PrintScreen by default."
            )
            conflicts.setWordWrap(True)
            conflicts.setStyleSheet("color: gray")
            form.addRow("", conflicts)

        self._capture_delay_spin = QSpinBox()
        self._capture_delay_spin.setRange(0, 60)
        self._capture_delay_spin.setSuffix(" s")
        self._capture_delay_spin.setValue(settings.capture_delay_seconds())
        form.addRow("Delay:", self._capture_delay_spin)

        cursor_row = QHBoxLayout()
        self._capture_cursor_cb = QCheckBox()
        self._capture_cursor_cb.setChecked(settings.capture_include_cursor())
        cursor_row.addWidget(self._capture_cursor_cb)
        if not caps.cursor:
            note = QLabel(CURSOR_UNAVAILABLE)
            note.setStyleSheet("color: gray")
            cursor_row.addWidget(note)
        cursor_row.addStretch(1)
        form.addRow("Include mouse cursor:", cursor_row)

        self._capture_sound_cb = QCheckBox()
        self._capture_sound_cb.setChecked(settings.capture_play_sound())
        form.addRow("Play capture sound:", self._capture_sound_cb)

        self._capture_hide_cb = QCheckBox()
        self._capture_hide_cb.setChecked(settings.capture_hide_window())
        form.addRow("Hide SnapMock window during capture:", self._capture_hide_cb)

        self._capture_clipboard_cb = QCheckBox()
        self._capture_clipboard_cb.setChecked(settings.capture_copy_to_clipboard())
        form.addRow("Copy to clipboard:", self._capture_clipboard_cb)

        self._capture_scope_combo = QComboBox()
        self._capture_scope_combo.addItem(
            "Monitor under cursor", FullScreenScope.MONITOR_UNDER_CURSOR.value
        )
        self._capture_scope_combo.addItem("All monitors", FullScreenScope.ALL_MONITORS.value)
        self._capture_scope_combo.setCurrentIndex(
            max(0, self._capture_scope_combo.findData(settings.capture_full_screen_scope()))
        )
        form.addRow("Full screen scope:", self._capture_scope_combo)

        self._capture_magnifier_cb = QCheckBox()
        self._capture_magnifier_cb.setChecked(settings.capture_show_magnifier())
        form.addRow("Show magnifier:", self._capture_magnifier_cb)

        self._capture_tray_cb = QCheckBox()
        self._capture_tray_cb.setChecked(settings.capture_tray_enabled())
        form.addRow("Show tray icon:", self._capture_tray_cb)

        self._capture_keep_running_cb = QCheckBox()
        self._capture_keep_running_cb.setChecked(settings.capture_keep_running_in_tray())
        self._capture_keep_running_cb.setEnabled(settings.capture_tray_enabled())
        self._capture_tray_cb.toggled.connect(self._capture_keep_running_cb.setEnabled)
        form.addRow("Keep running in tray when window is closed:", self._capture_keep_running_cb)

        self._capability_label = QLabel(capture.capability_summary())
        self._capability_label.setWordWrap(True)
        self._capability_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._capability_label.setStyleSheet("color: gray")
        form.addRow(self._capability_label)

        group.setLayout(form)
        return group

    def _build_hotkey_row(self, capture: CaptureManager, action: str) -> QWidget:
        """A key sequence editor that registers on change (PRD 3.1, 9.3)."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QKeySequenceEdit()
        edit.setMaximumSequenceLength(1)
        binding = capture.binding(action)
        if binding is not None:
            edit.setKeySequence(binding.key_sequence)
        status = QLabel("")
        status.setStyleSheet("color: #c0392b")
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self._change_hotkey(action, QKeySequence()))
        edit.editingFinished.connect(lambda: self._change_hotkey(action, edit.keySequence()))
        layout.addWidget(edit, 1)
        layout.addWidget(clear)
        layout.addWidget(status)
        self._hotkey_edits[action] = edit
        self._hotkey_status[action] = status
        self._refresh_hotkey_status(action)
        return row

    def _build_command_row(self, action: str) -> QWidget:
        """Command-line guidance with a Copy button (PRD 6.7, Wayland and macOS)."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        command = COMMAND_LINE_FOR_ACTION[action]
        field = QLineEdit(command)
        field.setReadOnly(True)
        field.setToolTip("Bind a desktop shortcut to this command")
        copy = QPushButton("Copy")
        copy.clicked.connect(lambda: self._copy_text(command))
        layout.addWidget(QLabel("Bind a desktop shortcut to:"))
        layout.addWidget(field, 1)
        layout.addWidget(copy)
        return row

    @staticmethod
    def _copy_text(text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _change_hotkey(self, action: str, sequence: QKeySequence) -> None:
        if self._capture is None:
            return
        text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        ok = self._capture.set_hotkey(action, text)
        binding = self._capture.binding(action)
        edit = self._hotkey_edits.get(action)
        if edit is not None and binding is not None:
            edit.blockSignals(True)
            edit.setKeySequence(binding.key_sequence)
            edit.blockSignals(False)
        self._refresh_hotkey_status(action, failed_now=not ok)

    def _refresh_hotkey_status(self, action: str, *, failed_now: bool = False) -> None:
        if self._capture is None:
            return
        binding = self._capture.binding(action)
        label = self._hotkey_status.get(action)
        if label is None or binding is None:
            return
        if failed_now or (binding.is_bound and not binding.registered):
            label.setText(HOTKEY_IN_USE)
        else:
            label.setText("")

    def hotkey_status_text(self, action: str) -> str:
        label = self._hotkey_status.get(action)
        return label.text() if label is not None else ""

    def show_desktop_shortcut_help(self) -> None:
        """The desktop-shortcut guidance (PRD 9.2), reachable at any time."""
        QMessageBox.information(self, "Set Up a Desktop Shortcut", DESKTOP_SHORTCUT_HELP)

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

        if self._capture_group is not None:
            capture_values: dict[str, object] = {
                "capture_default_mode": self._capture_mode_combo.currentData(),
                "capture_delay_seconds": self._capture_delay_spin.value(),
                "capture_include_cursor": self._capture_cursor_cb.isChecked(),
                "capture_play_sound": self._capture_sound_cb.isChecked(),
                "capture_hide_window": self._capture_hide_cb.isChecked(),
                "capture_copy_to_clipboard": self._capture_clipboard_cb.isChecked(),
                "capture_full_screen_scope": self._capture_scope_combo.currentData(),
                "capture_show_magnifier": self._capture_magnifier_cb.isChecked(),
                "capture_tray_enabled": self._capture_tray_cb.isChecked(),
                "capture_keep_running_in_tray": self._capture_keep_running_cb.isChecked(),
            }
            for key, new_value in capture_values.items():
                if new_value != self._orig[key]:
                    changes[key] = (self._orig[key], new_value)

        return changes
