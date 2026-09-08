"""Tests for the Windows backend contract, the macOS stub and onboarding (PRD 6.5, 6.6, 9.1)."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.capture import macos, windows
from snapmock.capture.backend import CaptureError, FakeHotkeyBackend
from snapmock.capture.manager import CaptureManager
from snapmock.capture.models import (
    CaptureMode,
    CaptureRequest,
    PermissionState,
)
from snapmock.capture.onboarding import (
    MACOS_PERMISSION_TEXT,
    MACOS_RESTART_TEXT,
    MacOSPermissionDialog,
)
from snapmock.config.settings import AppSettings
from snapmock.main_window import MainWindow


def test_windows_backend_reports_capabilities(qapp: QApplication) -> None:
    """The Windows backend activates only on Windows, and claims every mode there."""
    if sys.platform != "win32":
        with pytest.raises(OSError):
            windows.create_backends()  # the module still imports everywhere
        return
    capture, hotkeys = windows.create_backends()
    caps = capture.capabilities()
    assert caps.full_screen and caps.active_window and caps.region and caps.cursor
    assert caps.hotkeys and caps.tray
    assert not caps.needs_permission
    assert hotkeys.supported is True  # RegisterHotKey is wired, so no guidance text


def test_windows_key_mapping_is_portable() -> None:
    """The Qt-to-virtual-key mapping is pure, so it runs on every platform."""
    assert windows.parse_key_sequence(QKeySequence("Print")) == (0x2C, 0)
    assert windows.parse_key_sequence(QKeySequence("Alt+Print")) == (0x2C, windows.MOD_ALT)
    assert windows.parse_key_sequence(QKeySequence("Ctrl+Print")) == (0x2C, windows.MOD_CONTROL)
    assert windows.parse_key_sequence(QKeySequence()) is None
    assert windows.virtual_key_for(Qt.Key.Key_Launch0) is None


def test_macos_stub_permission_and_grab(qapp: QApplication) -> None:
    capture, hotkeys = macos.create_backends()
    assert isinstance(capture, macos.MacOSCaptureBackend)
    caps = capture.capabilities()
    assert caps.needs_permission and not caps.hotkeys
    assert capture.request_permission() is PermissionState.DENIED
    with pytest.raises(CaptureError, match="Screen Recording"):
        capture.grab_screens(False)
    capture.permission_state = PermissionState.GRANTED
    with pytest.raises(CaptureError, match="not yet implemented"):
        capture.grab_screens(False)
    assert hotkeys.supported is False


def test_manager_reports_missing_permission(qapp: QApplication) -> None:
    capture, hotkeys = macos.create_backends()
    manager = CaptureManager(capture, hotkeys, AppSettings())
    summary = manager.capability_summary()
    assert "Backend: macOS." in summary
    assert "Screen Recording permission: not granted." in summary
    assert "Global hotkeys: bind a desktop shortcut." in summary


def test_manager_fails_with_permission_message(qtbot: QtBot) -> None:
    capture, _ = macos.create_backends()
    manager = CaptureManager(capture, FakeHotkeyBackend(), AppSettings())
    with qtbot.waitSignal(manager.capture_failed, timeout=2000) as blocker:
        manager.start(CaptureRequest(CaptureMode.FULL_SCREEN, hide_window=False))
    assert blocker.args == [macos.PERMISSION_MESSAGE]


def test_macos_dialog_moves_to_restart_state(qtbot: QtBot) -> None:
    calls: list[int] = []
    dlg = MacOSPermissionDialog(lambda: calls.append(1) is None and False, settings_url="x:")
    qtbot.addWidget(dlg)
    assert dlg.text.text() == MACOS_PERMISSION_TEXT
    assert dlg.quit_button.isHidden()
    dlg.continue_button.click()
    assert calls == [1]
    assert dlg.text.text() == MACOS_RESTART_TEXT
    assert dlg.continue_button.isHidden() and not dlg.quit_button.isHidden()
    assert dlg.granted is False
    dlg.quit_button.click()
    assert dlg.quit_requested


def test_macos_dialog_accepts_when_granted(qtbot: QtBot) -> None:
    dlg = MacOSPermissionDialog(lambda: True, settings_url="x:")
    qtbot.addWidget(dlg)
    dlg.continue_button.click()
    assert dlg.granted and dlg.result() == dlg.DialogCode.Accepted


def test_macos_gate_skips_dialog_once_shown(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    capture, hotkeys = macos.create_backends()
    manager = CaptureManager(capture, hotkeys, AppSettings())
    window = MainWindow(capture_manager=manager)
    qtbot.addWidget(window)
    AppSettings().set_capture_onboarding_shown(True)
    # With onboarding suppressed the request proceeds and fails with the 6.5 message.
    with qtbot.waitSignal(manager.capture_failed, timeout=2000) as blocker:
        window._start_capture(CaptureMode.FULL_SCREEN, "menu")  # noqa: SLF001
    assert blocker.args == [macos.PERMISSION_MESSAGE]
    assert isinstance(capture, macos.MacOSCaptureBackend)
    assert capture.permission_requests >= 2  # gate preflight and the grab's own check
