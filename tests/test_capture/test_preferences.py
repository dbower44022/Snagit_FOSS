"""Tests for the Capture preferences category (PRD 8.1, 6.7, 9.3, 14.7)."""

from __future__ import annotations

from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from pytestqt.qtbot import QtBot

from snapmock.capture.backend import (
    FakeCaptureBackend,
    FakeHotkeyBackend,
    NullHotkeyBackend,
)
from snapmock.capture.manager import CaptureManager
from snapmock.capture.models import HOTKEY_ACTION_REGION, BackendCapabilities
from snapmock.config.settings import AppSettings
from snapmock.main_window import TRAY_UNAVAILABLE_MESSAGE, MainWindow
from snapmock.ui.preferences_dialog import (
    CURSOR_UNAVAILABLE,
    HOTKEY_IN_USE,
    PreferencesDialog,
)


def _dialog(qtbot: QtBot, manager: CaptureManager) -> PreferencesDialog:
    dlg = PreferencesDialog(AppSettings(), capture=manager)
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_without_manager_has_no_capture_group(qtbot: QtBot) -> None:
    dlg = PreferencesDialog(AppSettings())
    qtbot.addWidget(dlg)
    assert dlg._capture_group is None  # noqa: SLF001
    assert dlg.get_changes() == {}


def test_capture_group_reads_and_reports_changes(qtbot: QtBot, qapp: QApplication) -> None:
    manager = CaptureManager(FakeCaptureBackend(), FakeHotkeyBackend(), AppSettings())
    dlg = _dialog(qtbot, manager)
    assert dlg._capture_group is not None  # noqa: SLF001
    assert dlg.get_changes() == {}
    dlg._capture_mode_combo.setCurrentIndex(2)  # noqa: SLF001
    dlg._capture_delay_spin.setValue(7)  # noqa: SLF001
    dlg._capture_cursor_cb.setChecked(True)  # noqa: SLF001
    dlg._capture_scope_combo.setCurrentIndex(1)  # noqa: SLF001
    dlg._capture_tray_cb.setChecked(False)  # noqa: SLF001
    assert dlg._capture_keep_running_cb.isEnabled() is False  # noqa: SLF001
    changes = dlg.get_changes()
    assert changes["capture_default_mode"] == ("region", "full_screen")
    assert changes["capture_delay_seconds"] == (0, 7)
    assert changes["capture_include_cursor"] == (False, True)
    assert changes["capture_full_screen_scope"] == ("monitor_under_cursor", "all_monitors")
    assert changes["capture_tray_enabled"] == (True, False)
    assert "Backend: fake." in dlg._capability_label.text()  # noqa: SLF001


def test_hotkey_editor_registers_immediately_and_reports_conflict(
    qtbot: QtBot, qapp: QApplication
) -> None:
    hk = FakeHotkeyBackend()
    manager = CaptureManager(FakeCaptureBackend(), hk, AppSettings())
    manager.register_hotkeys()
    dlg = _dialog(qtbot, manager)
    edit = dlg._hotkey_edits[HOTKEY_ACTION_REGION]  # noqa: SLF001
    assert edit.keySequence() == QKeySequence("Print")
    dlg._change_hotkey(HOTKEY_ACTION_REGION, QKeySequence("F9"))  # noqa: SLF001
    assert hk.registered[HOTKEY_ACTION_REGION] == "F9"
    assert AppSettings().capture_hotkey(HOTKEY_ACTION_REGION) == "F9"
    assert dlg.hotkey_status_text(HOTKEY_ACTION_REGION) == ""
    hk.refused.add("F10")
    dlg._change_hotkey(HOTKEY_ACTION_REGION, QKeySequence("F10"))  # noqa: SLF001
    assert dlg.hotkey_status_text(HOTKEY_ACTION_REGION) == HOTKEY_IN_USE
    assert edit.keySequence() == QKeySequence("F9")  # the previous key stays
    assert hk.registered[HOTKEY_ACTION_REGION] == "F9"


def test_startup_conflict_shown_beside_editor(qtbot: QtBot, qapp: QApplication) -> None:
    hk = FakeHotkeyBackend()
    hk.refused.add("Print")
    manager = CaptureManager(FakeCaptureBackend(), hk, AppSettings())
    manager.register_hotkeys()
    dlg = _dialog(qtbot, manager)
    assert dlg.hotkey_status_text(HOTKEY_ACTION_REGION) == HOTKEY_IN_USE


def test_command_line_guidance_replaces_editors_without_hotkeys(
    qtbot: QtBot, qapp: QApplication
) -> None:
    backend = FakeCaptureBackend()
    backend.fake_capabilities = BackendCapabilities(full_screen=True, region=True)
    manager = CaptureManager(backend, NullHotkeyBackend(), AppSettings())
    dlg = _dialog(qtbot, manager)
    assert dlg._hotkey_edits == {}  # noqa: SLF001
    labels = [
        w.text()
        for w in dlg._capture_group.findChildren(type(dlg._capability_label))  # noqa: SLF001
    ]
    assert "Bind a desktop shortcut to:" in labels
    assert CURSOR_UNAVAILABLE in labels
    assert any("desktop shortcut" in t for t in labels)
    summary = dlg._capability_label.text()  # noqa: SLF001
    assert "Active window: not available." in summary
    assert "Cursor: not available." in summary
    assert "Global hotkeys: bind a desktop shortcut." in summary
    # The Copy button puts the command on the clipboard.
    dlg._copy_text("snapmock --capture region")  # noqa: SLF001
    clipboard = qapp.clipboard()
    assert clipboard is not None and clipboard.text() == "snapmock --capture region"


def test_apply_capture_preferences_updates_settings_and_menus(main_window: MainWindow) -> None:
    main_window._apply_preference_changes(  # noqa: SLF001
        {
            "capture_default_mode": ("region", "full_screen"),
            "capture_delay_seconds": (0, 10),
            "capture_include_cursor": (False, True),
            "capture_copy_to_clipboard": (False, True),
            "capture_show_magnifier": (True, False),
            "capture_full_screen_scope": ("monitor_under_cursor", "all_monitors"),
        }
    )
    s = AppSettings()
    assert s.capture_default_mode() == "full_screen"
    assert s.capture_delay_seconds() == 10
    assert s.capture_include_cursor() and s.capture_copy_to_clipboard()
    assert s.capture_show_magnifier() is False
    assert s.capture_full_screen_scope() == "all_monitors"
    button = main_window._capture_button  # noqa: SLF001
    assert button is not None and button.toolTip() == "Capture (Ctrl+Print)"
    toggles = dict(main_window._capture_toggle_actions)  # noqa: SLF001
    assert toggles["include_cursor"].isChecked() and toggles["copy_to_clipboard"].isChecked()
    delay_group = main_window._delay_groups[0]  # noqa: SLF001
    assert [a.isChecked() for a in delay_group.actions()] == [False, False, False, True]


def test_enabling_tray_without_a_tray_explains(main_window: MainWindow) -> None:
    assert not QSystemTrayIcon.isSystemTrayAvailable()
    AppSettings().set_capture_tray_enabled(False)
    main_window._apply_preference_changes({"capture_tray_enabled": (False, True)})  # noqa: SLF001
    assert AppSettings().capture_tray_enabled() is True
    assert main_window.tray_icon is None
    assert main_window._toast._label.text() == TRAY_UNAVAILABLE_MESSAGE  # noqa: SLF001


def test_tray_preference_creates_and_removes_icon(qtbot: QtBot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    AppSettings().set_capture_tray_enabled(False)
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.tray_icon is None
    window._apply_preference_changes({"capture_tray_enabled": (False, True)})  # noqa: SLF001
    assert window.tray_icon is not None
    window._apply_preference_changes(  # noqa: SLF001
        {"capture_keep_running_in_tray": (False, True)}
    )
    app = QApplication.instance()
    assert isinstance(app, QApplication) and app.quitOnLastWindowClosed() is False
    window._apply_preference_changes({"capture_tray_enabled": (True, False)})  # noqa: SLF001
    assert window.tray_icon is None
    assert app.quitOnLastWindowClosed() is True
