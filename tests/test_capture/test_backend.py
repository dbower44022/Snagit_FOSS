"""Tests for the backend abstraction, null backends, and fakes (PRD 6.1, 6.7)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRect, QSize
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.capture.backend import (
    UNSUPPORTED_PLATFORM_MESSAGE,
    CaptureError,
    FakeCaptureBackend,
    FakeHotkeyBackend,
    NullCaptureBackend,
    NullHotkeyBackend,
    qt_monitors,
    synthetic_image,
)
from snapmock.capture.models import (
    HOTKEY_ACTION_REGION,
    HotkeyBinding,
    MonitorInfo,
    PermissionState,
)


def test_null_capture_backend_reports_nothing_and_fails(qapp: QApplication) -> None:
    backend = NullCaptureBackend()
    assert not backend.capabilities().any_capture
    with pytest.raises(CaptureError, match=UNSUPPORTED_PLATFORM_MESSAGE):
        backend.grab_screens(False)
    assert backend.active_window_geometry() is None
    assert backend.request_permission() is PermissionState.NOT_REQUIRED


def test_null_hotkey_backend_refuses(qapp: QApplication) -> None:
    backend = NullHotkeyBackend()
    binding = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Print"))
    assert backend.supported is False
    assert backend.register(binding) is False
    assert binding.registered is False
    assert binding.failure_reason


def test_qt_monitors_reports_the_offscreen_screen(qapp: QApplication) -> None:
    monitors = qt_monitors()
    assert monitors
    assert monitors[0].physical_size.width() > 0
    assert any(m.is_primary for m in monitors)


def test_fake_backend_images_match_physical_size(qapp: QApplication) -> None:
    hi = MonitorInfo("hi", QRect(0, 0, 100, 50), QSize(200, 100), 2.0, True)
    lo = MonitorInfo("lo", QRect(100, 0, 100, 50), QSize(100, 50), 1.0)
    backend = FakeCaptureBackend([hi, lo])
    grab = backend.grab_screens(include_cursor=True)
    assert grab.images["hi"].size() == QSize(200, 100)
    assert grab.images["lo"].size() == QSize(100, 50)
    assert grab.cursor_image is not None
    assert backend.grab_calls == [True]
    backend.fail_with = "boom"
    with pytest.raises(CaptureError, match="boom"):
        backend.grab_screens(False)


def test_synthetic_image_varies_by_position(qapp: QApplication) -> None:
    img = synthetic_image(QSize(50, 50))
    assert img.pixel(0, 0) != img.pixel(49, 49)


def test_fake_hotkey_backend_registers_and_fires(qtbot: QtBot) -> None:
    backend = FakeHotkeyBackend()
    ok = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Print"))
    assert backend.register(ok) and ok.registered
    with qtbot.waitSignal(backend.triggered) as blocker:
        backend.fire(HOTKEY_ACTION_REGION)
    assert blocker.args == [HOTKEY_ACTION_REGION]
    backend.refused.add("Ctrl+Print")
    bad = HotkeyBinding("capture.full_screen", QKeySequence("Ctrl+Print"))
    assert backend.register(bad) is False
    assert bad.failure_reason == "In use by another application"
    backend.unregister(ok)
    assert not ok.registered and HOTKEY_ACTION_REGION not in backend.registered
