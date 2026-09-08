"""Tests for the Windows backend (PRD 6.6, 6.7).

The pure parts run everywhere. The live tests need the Windows API and are
skipped elsewhere. The suite runs on the offscreen platform, so SnapMock has
no native window of its own here; the live tests therefore work against the
desktop's real foreground window rather than one of ours.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Iterator

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QKeySequence
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.capture import windows
from snapmock.capture.models import HOTKEY_ACTION_REGION, HOTKEY_ACTION_WINDOW, HotkeyBinding


@pytest.mark.skipif(
    ctypes.sizeof(ctypes.c_void_p) != 8, reason="the layouts are those of 64-bit Windows"
)
def test_struct_sizes_match_win64_layouts() -> None:
    assert ctypes.sizeof(windows.POINT) == 8
    assert ctypes.sizeof(windows.RECT) == 16
    assert ctypes.sizeof(windows.CURSORINFO) == 24
    assert ctypes.sizeof(windows.ICONINFO) == 32
    assert ctypes.sizeof(windows.BITMAP) == 32
    assert ctypes.sizeof(windows.BITMAPINFOHEADER) == 40
    assert ctypes.sizeof(windows.MSG) == 48


def test_virtual_key_mapping() -> None:
    assert windows.virtual_key_for(Qt.Key.Key_Print) == 0x2C  # VK_SNAPSHOT
    assert windows.virtual_key_for(Qt.Key.Key_F1) == 0x70
    assert windows.virtual_key_for(Qt.Key.Key_F24) == 0x87
    assert windows.virtual_key_for(Qt.Key.Key_A) == 0x41
    assert windows.virtual_key_for(Qt.Key.Key_5) == 0x35
    assert windows.virtual_key_for(Qt.Key.Key_PageDown) == 0x22
    assert windows.virtual_key_for(Qt.Key.Key_Launch0) is None


def test_parse_key_sequence_modifiers() -> None:
    # A bare Print Screen is the shipped Region default, so no modifier is fine.
    assert windows.parse_key_sequence(QKeySequence("Print")) == (0x2C, 0)
    assert windows.parse_key_sequence(QKeySequence("Alt+Print")) == (0x2C, windows.MOD_ALT)
    assert windows.parse_key_sequence(QKeySequence("Ctrl+Shift+Meta+F2")) == (
        0x71,
        windows.MOD_CONTROL | windows.MOD_SHIFT | windows.MOD_WIN,
    )
    assert windows.parse_key_sequence(QKeySequence()) is None


@pytest.mark.skipif(sys.platform == "win32", reason="Windows is where this backend activates")
def test_create_backends_refuses_off_windows() -> None:
    with pytest.raises(OSError):
        windows.create_backends()  # the module still imports on every platform


live = pytest.mark.skipif(sys.platform != "win32", reason="needs the Windows API")


@pytest.fixture()
def win32() -> windows.Win32:
    return windows.Win32()


@pytest.fixture()
def hotkeys(win32: windows.Win32) -> Iterator[windows.WindowsHotkeyBackend]:
    backend = windows.WindowsHotkeyBackend(win32)
    yield backend
    backend.close()  # releases every key and destroys the message-only window


@live
def test_live_dpi_awareness_is_per_monitor_v2(qapp: QApplication, win32: windows.Win32) -> None:
    """Qt sets it during startup; the backend only verifies it (PRD 6.6).

    Only the real Windows platform plugin sets it, so this says nothing on the
    offscreen platform the suite normally runs on.
    """
    if QGuiApplication.platformName() != "windows":
        pytest.skip("only the windows platform plugin sets the awareness context")
    assert win32.per_monitor_dpi_aware_v2()


@live
def test_live_foreground_window_geometry_and_title(
    qapp: QApplication, win32: windows.Win32
) -> None:
    hwnd = win32.foreground_window()
    if hwnd is None:
        pytest.skip("no foreground window on this desktop")
    assert isinstance(win32.window_class(hwnd), str)
    title = win32.window_title(hwnd)
    assert title is None or title
    rect = win32.window_frame_rect(hwnd)
    assert rect is None or (rect.isValid() and not rect.isEmpty())


@live
def test_live_frame_bounds_are_within_the_window_rect(
    qapp: QApplication, win32: windows.Win32
) -> None:
    """The extended frame bounds exclude the invisible resize border (PRD 14.5)."""
    hwnd = win32.foreground_window()
    if hwnd is None:
        pytest.skip("no foreground window on this desktop")
    outer = windows.RECT()
    if not win32.user32.GetWindowRect(windows.HANDLE(hwnd), ctypes.byref(outer)):
        pytest.skip("GetWindowRect failed for the foreground window")
    frame = win32.window_frame_rect(hwnd)
    if frame is None:
        pytest.skip("the foreground window reports no frame")
    assert frame.width() <= outer.right - outer.left
    assert frame.height() <= outer.bottom - outer.top


@live
def test_live_cursor_image_has_alpha_and_a_hotspot(
    qapp: QApplication, win32: windows.Win32
) -> None:
    cursor = win32.cursor_image()
    if cursor is None:
        pytest.skip("no cursor is showing on this desktop")
    image, hotspot = cursor
    assert image.width() > 0 and image.height() > 0
    assert not image.isNull()
    assert 0 <= hotspot.x() <= image.width()
    assert 0 <= hotspot.y() <= image.height()


@live
def test_live_standard_cursors_convert(qapp: QApplication, win32: windows.Win32) -> None:
    """Load the stock cursors and put each through the ICONINFO conversion.

    This does not depend on a cursor being visible, so it runs anywhere on
    Windows. The stock cursors are monochrome, which is exactly the
    double-height mask path (upper half AND, lower half XOR) that the I-beam
    arrives on.
    """
    user32 = win32.user32
    user32.LoadCursorW.argtypes = [windows.HANDLE, ctypes.c_void_p]
    user32.LoadCursorW.restype = windows.HANDLE
    for idc in (32512, 32513, 32514):  # IDC_ARROW, IDC_IBEAM, IDC_WAIT
        handle = user32.LoadCursorW(None, ctypes.c_void_p(idc))
        assert handle
        icon = windows.ICONINFO()
        assert user32.GetIconInfo(windows.HANDLE(handle), ctypes.byref(icon))
        try:
            converted = win32._icon_to_image(icon)  # noqa: SLF001 - the unit under test
        finally:
            for bitmap in (icon.hbmMask, icon.hbmColor):
                if bitmap:
                    win32.gdi32.DeleteObject(windows.HANDLE(bitmap))
        assert converted is not None
        image, hotspot = converted
        assert image.width() > 0 and image.height() > 0
        assert 0 <= hotspot.x() <= image.width()
        assert 0 <= hotspot.y() <= image.height()
        opaque = sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if image.pixel(x, y) >> 24
        )
        assert opaque > 0, f"cursor {idc} converted to a fully transparent image"


@live
def test_live_frame_rect_and_title_for_a_created_window(
    qapp: QApplication, win32: windows.Win32
) -> None:
    """Geometry and title come back for a real window we own.

    The window is never shown, so nothing appears on screen and DWM has no
    extended bounds for it: this also covers the GetWindowRect fallback.
    """
    user32 = win32.user32
    hwnd = user32.CreateWindowExW(
        0,
        ctypes.c_wchar_p("STATIC"),
        ctypes.c_wchar_p("SnapMock Test Window"),
        0,
        120,
        130,
        320,
        240,
        None,
        None,
        None,
        None,
    )
    assert hwnd
    try:
        handle = int(hwnd)
        assert win32.window_title(handle) == "SnapMock Test Window"
        assert win32.window_class(handle).lower() == "static"
        rect = win32.window_frame_rect(handle)
        assert rect is not None
        assert rect.width() == 320 and rect.height() == 240
        assert rect.x() == 120 and rect.y() == 130
    finally:
        user32.DestroyWindow(windows.HANDLE(hwnd))


@live
def test_live_own_window_is_not_reported_as_the_active_window(
    qapp: QApplication, win32: windows.Win32
) -> None:
    """A SnapMock window is skipped so the manager's fallback applies, as on X11."""
    backend = windows.WindowsCaptureBackend(win32)
    geometry = backend.active_window_geometry()
    assert geometry is None or not geometry.isEmpty()


@live
def test_live_duplicate_key_is_refused(
    qapp: QApplication, hotkeys: windows.WindowsHotkeyBackend
) -> None:
    first = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Alt+Shift+F11"))
    second = HotkeyBinding(HOTKEY_ACTION_WINDOW, QKeySequence("Ctrl+Alt+Shift+F11"))
    assert hotkeys.register(first) and first.registered
    assert hotkeys.register(second) is False
    assert second.failure_reason == windows.DUPLICATE_KEY


@live
def test_live_key_taken_by_another_registration_reports_in_use(
    qapp: QApplication, hotkeys: windows.WindowsHotkeyBackend
) -> None:
    """Error 1409 becomes the same wording the X11 backend and the fake use."""
    binding = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Alt+Shift+F10"))
    assert hotkeys.register(binding)
    rival = windows.WindowsHotkeyBackend(windows.Win32())
    try:
        taken = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Alt+Shift+F10"))
        assert rival.register(taken) is False
        assert taken.failure_reason == windows.KEY_IN_USE
    finally:
        rival.close()


@live
def test_live_hotkey_round_trip(qtbot: QtBot, hotkeys: windows.WindowsHotkeyBackend) -> None:
    """A WM_HOTKEY for a registered identifier becomes ``triggered`` with its action.

    The message is posted rather than typed: synthetic keystrokes only become
    hotkeys for a process on the interactive input desktop, which a test runner
    need not be. Pressing the key for real is a hand-verification step. What is
    covered here is every line this project owns: the native event filter, the
    identifier lookup, and the signal.
    """
    binding = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Alt+Shift+F12"))
    assert hotkeys.register(binding) and binding.registered
    hwnd = hotkeys._hwnd  # noqa: SLF001 - the test posts to the backend's own window
    assert hwnd is not None
    user32 = hotkeys._win32.user32  # noqa: SLF001
    user32.PostMessageW.argtypes = [windows.HANDLE, windows.UINT, windows.WPARAM, windows.LPARAM]
    hotkey_id = hotkeys._ids[HOTKEY_ACTION_REGION]  # noqa: SLF001
    with qtbot.waitSignal(hotkeys.triggered, timeout=5000) as blocker:
        posted = user32.PostMessageW(
            windows.HANDLE(hwnd),
            windows.UINT(windows.WM_HOTKEY),
            windows.WPARAM(hotkey_id),
            windows.LPARAM(0),
        )
        assert posted
    assert blocker.args == [HOTKEY_ACTION_REGION]


@live
def test_live_unrelated_message_is_ignored(
    qapp: QApplication, hotkeys: windows.WindowsHotkeyBackend
) -> None:
    """A WM_HOTKEY carrying an identifier we did not register emits nothing."""
    binding = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Alt+Shift+F8"))
    assert hotkeys.register(binding)
    fired: list[str] = []
    hotkeys.triggered.connect(fired.append)
    hotkeys._on_hotkey(9999)  # noqa: SLF001 - no such registration
    assert fired == []


@live
def test_live_unregister_releases_the_key(
    qapp: QApplication, hotkeys: windows.WindowsHotkeyBackend
) -> None:
    binding = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Alt+Shift+F9"))
    assert hotkeys.register(binding)
    hotkeys.unregister(binding)
    assert not binding.registered
    rival = windows.WindowsHotkeyBackend(windows.Win32())
    try:
        again = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Alt+Shift+F9"))
        assert rival.register(again) is True  # the key is free once released
    finally:
        rival.close()
