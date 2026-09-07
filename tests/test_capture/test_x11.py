"""Tests for the X11 backend (PRD 6.3, 6.7).

The pure parts run everywhere. The integration tests need a live X server and
libX11, and are skipped otherwise.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.capture import x11
from snapmock.capture.models import HOTKEY_ACTION_REGION, HotkeyBinding


@pytest.mark.skipif(
    ctypes.sizeof(ctypes.c_ulong) != 8,
    reason="the layouts are LP64; this platform is LLP64 and never selects X11",
)
def test_struct_sizes_match_lp64_layouts() -> None:
    assert ctypes.sizeof(x11.XKeyEvent) == 96
    assert ctypes.sizeof(x11.XEvent) == 192
    assert ctypes.sizeof(x11.XFixesCursorImage) == 48


def test_keysym_names() -> None:
    assert x11.keysym_name_for(Qt.Key.Key_Print) == "Print"
    assert x11.keysym_name_for(Qt.Key.Key_F9) == "F9"
    assert x11.keysym_name_for(Qt.Key.Key_F35) == "F35"
    assert x11.keysym_name_for(Qt.Key.Key_A) == "a"
    assert x11.keysym_name_for(Qt.Key.Key_5) == "5"
    assert x11.keysym_name_for(Qt.Key.Key_PageDown) == "Next"
    assert x11.keysym_name_for(Qt.Key.Key_Launch0) is None


def test_parse_key_sequence_modifiers() -> None:
    assert x11.parse_key_sequence(QKeySequence("Print")) == ("Print", 0)
    assert x11.parse_key_sequence(QKeySequence("Ctrl+Print")) == ("Print", x11.CONTROL_MASK)
    assert x11.parse_key_sequence(QKeySequence("Alt+Print")) == ("Print", x11.MOD1_MASK)
    assert x11.parse_key_sequence(QKeySequence("Ctrl+Shift+Meta+F2")) == (
        "F2",
        x11.CONTROL_MASK | x11.SHIFT_MASK | x11.MOD4_MASK,
    )
    assert x11.parse_key_sequence(QKeySequence()) is None


def test_physical_to_logical_on_offscreen(qapp: QApplication) -> None:
    rect = x11.physical_to_logical(QRect(10, 20, 30, 40))
    assert rect.size().width() > 0 and rect.size().height() > 0


def test_create_backends_refuses_non_x11_session(qapp: QApplication) -> None:
    with pytest.raises(OSError):
        x11.create_backends()  # the test suite runs on the offscreen platform


def _x11_available() -> bool:
    return bool(os.environ.get("DISPLAY")) and ctypes.util.find_library("X11") is not None


live = pytest.mark.skipif(not _x11_available(), reason="needs a live X11 display")


@pytest.fixture()
def connection() -> x11.X11Connection:
    conn = x11.X11Connection()
    yield conn  # type: ignore[misc]
    conn.close()


@live
def test_live_active_window_and_cursor(qapp: QApplication, connection: x11.X11Connection) -> None:
    backend = x11.X11CaptureBackend(connection)
    caps = backend.capabilities()
    assert caps.full_screen and caps.region and caps.hotkeys
    if caps.active_window:
        geometry = backend.active_window_geometry()
        assert geometry is None or not geometry.isEmpty()
    if caps.cursor:
        cursor = connection.cursor_image()
        assert cursor is not None and cursor[0].width() > 0


@live
def test_live_grab_conflict_and_release(qapp: QApplication, connection: x11.X11Connection) -> None:
    hk = x11.X11HotkeyBackend(connection)
    binding = HotkeyBinding("capture.full_screen", QKeySequence("Ctrl+Shift+Alt+F12"))
    assert hk.register(binding) and binding.registered
    other = x11.X11Connection()
    try:
        keycode = other.keycode_for("F12")
        mods = x11.CONTROL_MASK | x11.SHIFT_MASK | x11.MOD1_MASK
        assert other.grab_key(keycode, mods) is False
        hk.unregister(binding)
        assert other.grab_key(keycode, mods) is True
        other.ungrab_key(keycode, mods)
    finally:
        other.close()


@live
def test_live_key_press_is_delivered(qtbot: QtBot, connection: x11.X11Connection) -> None:
    """Synthesize the grabbed key with XTest and expect ``triggered``."""
    xtst_path = ctypes.util.find_library("Xtst")
    if xtst_path is None:
        pytest.skip("libXtst not installed")
    xtst = ctypes.CDLL(xtst_path)
    xtst.XTestFakeKeyEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_ulong,
    ]
    hk = x11.X11HotkeyBackend(connection)
    binding = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Shift+Alt+F11"))
    assert hk.register(binding)
    sender = x11.X11Connection()
    try:
        ctrl = sender.keycode_for("Control_L")
        shift = sender.keycode_for("Shift_L")
        alt = sender.keycode_for("Alt_L")
        f11 = sender.keycode_for("F11")
        with qtbot.waitSignal(hk.triggered, timeout=3000) as blocker:
            for code, down in (
                (ctrl, 1),
                (shift, 1),
                (alt, 1),
                (f11, 1),
                (f11, 0),
                (alt, 0),
                (shift, 0),
                (ctrl, 0),
            ):
                xtst.XTestFakeKeyEvent(sender.display, code, down, 0)
            sender.x.XFlush(sender.display)
        assert blocker.args == [HOTKEY_ACTION_REGION]
    finally:
        hk.unregister(binding)
        sender.close()
