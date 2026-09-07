"""Tests for the capture data models and capture settings (PRD Sections 8.1, 10, 12.2)."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize
from PyQt6.QtGui import QImage, QKeySequence

from snapmock.capture.models import (
    HOTKEY_ACTION_FULL_SCREEN,
    HOTKEY_ACTION_REGION,
    HOTKEY_ACTION_WINDOW,
    BackendCapabilities,
    CaptureMetadata,
    CaptureMode,
    FullScreenScope,
    HotkeyBinding,
    MonitorInfo,
    ScreenGrab,
)
from snapmock.config.settings import AppSettings


def test_capture_mode_parsing_accepts_command_line_aliases() -> None:
    assert CaptureMode.from_string("region") is CaptureMode.REGION
    assert CaptureMode.from_string("window") is CaptureMode.ACTIVE_WINDOW
    assert CaptureMode.from_string("full") is CaptureMode.FULL_SCREEN
    assert CaptureMode.from_string("ACTIVE_WINDOW") is CaptureMode.ACTIVE_WINDOW
    assert CaptureMode.from_string("bogus") is CaptureMode.REGION
    assert CaptureMode.from_string("bogus", CaptureMode.FULL_SCREEN) is CaptureMode.FULL_SCREEN


def test_capture_metadata_round_trips_through_dict() -> None:
    meta = CaptureMetadata(
        mode=CaptureMode.REGION,
        requested_mode=CaptureMode.ACTIVE_WINDOW,
        monitor_name="DP-1",
        device_pixel_ratio=2.0,
        screen_rect=QRect(120, 80, 1600, 900),
        cursor_included=False,
        platform="linux",
        backend="wayland_portal",
        window_title=None,
    )
    data = meta.to_dict()
    assert data["mode"] == "region"
    assert data["requested_mode"] == "active_window"
    assert data["screen_rect"] == {"x": 120, "y": 80, "width": 1600, "height": 900}
    assert CaptureMetadata.from_dict(data) == meta


def test_capture_metadata_from_partial_dict_uses_defaults() -> None:
    meta = CaptureMetadata.from_dict({"mode": "full_screen"})
    assert meta.mode is CaptureMode.FULL_SCREEN
    assert meta.requested_mode is CaptureMode.FULL_SCREEN
    assert meta.screen_rect == QRect(0, 0, 0, 0)
    assert meta.monitor_name is None


def test_monitor_physical_geometry_scales_position() -> None:
    m = MonitorInfo("A", QRect(1000, 0, 800, 600), QSize(1600, 1200), 2.0, True)
    assert m.physical_geometry == QRect(2000, 0, 1600, 1200)


def test_screen_grab_lookups() -> None:
    a = MonitorInfo("A", QRect(0, 0, 100, 100), QSize(100, 100), 1.0, True)
    b = MonitorInfo("B", QRect(100, 0, 100, 100), QSize(200, 200), 2.0)
    grab = ScreenGrab(images={"A": QImage(), "B": QImage()}, monitors=[a, b])
    assert grab.monitor_at(QPoint(150, 50)) is b
    assert grab.monitor_at(QPoint(500, 500)) is None
    assert grab.monitor_by_name("A") is a
    assert grab.virtual_logical_rect == QRect(0, 0, 200, 100)


def test_backend_capabilities_supports_mode() -> None:
    caps = BackendCapabilities(full_screen=True, region=True)
    assert caps.supports(CaptureMode.FULL_SCREEN)
    assert not caps.supports(CaptureMode.ACTIVE_WINDOW)
    assert not caps.supports(CaptureMode.SCROLLING)
    assert caps.any_capture
    assert not BackendCapabilities().any_capture


def test_hotkey_binding_text_forms() -> None:
    binding = HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence("Ctrl+Print"))
    assert binding.is_bound
    assert binding.key_text == "Ctrl+Print"
    assert not HotkeyBinding(HOTKEY_ACTION_REGION, QKeySequence()).is_bound


def test_capture_settings_defaults() -> None:
    s = AppSettings()
    assert s.capture_default_mode() == "region"
    assert s.capture_hotkey(HOTKEY_ACTION_REGION) == "Print"
    assert s.capture_hotkey(HOTKEY_ACTION_WINDOW) == "Alt+Print"
    assert s.capture_hotkey(HOTKEY_ACTION_FULL_SCREEN) == "Ctrl+Print"
    assert s.capture_delay_seconds() == 0
    assert s.capture_include_cursor() is False
    assert s.capture_play_sound() is False
    assert s.capture_hide_window() is True
    assert s.capture_copy_to_clipboard() is False
    assert s.capture_full_screen_scope() == FullScreenScope.MONITOR_UNDER_CURSOR.value
    assert s.capture_show_magnifier() is True
    assert s.capture_tray_enabled() is True
    assert s.capture_keep_running_in_tray() is False
    assert s.capture_onboarding_shown() is False
    assert s.capture_last_mode() == "region"


def test_capture_settings_round_trip_and_clamp() -> None:
    s = AppSettings()
    s.set_capture_hotkey(HOTKEY_ACTION_REGION, "")
    assert s.capture_hotkey(HOTKEY_ACTION_REGION) == ""
    s.set_capture_delay_seconds(99)
    assert s.capture_delay_seconds() == 60
    s.set_capture_full_screen_scope("all_monitors")
    assert s.capture_full_screen_scope() == "all_monitors"
    s.set_capture_full_screen_scope("nonsense")
    assert s.capture_full_screen_scope() == "monitor_under_cursor"
    s.set_capture_last_mode("full_screen")
    assert AppSettings().capture_last_mode() == "full_screen"
