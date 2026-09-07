"""Windows backend stub (PRD 6.6, 6.7).

Implements the interfaces and reports what the platform will support, but
every grab raises :class:`CaptureError` until the GDI, DWM, and RegisterHotKey
paths through ctypes are written. Imports on every platform.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRect

from snapmock.capture.backend import (
    CaptureBackend,
    CaptureError,
    HotkeyBackend,
    QtScreenGrabBackend,
)
from snapmock.capture.models import BackendCapabilities, HotkeyBinding, ScreenGrab

NOT_IMPLEMENTED = "not yet implemented on this platform"


class WindowsCaptureBackend(QtScreenGrabBackend):
    """GDI grab through Qt; active window and cursor through ctypes (planned)."""

    name = "windows"

    def capabilities(self) -> BackendCapabilities:
        # What Windows will support in version 1 (PRD 6.8); the stub grabs nothing yet.
        return BackendCapabilities(
            full_screen=True,
            active_window=True,
            region=True,
            cursor=True,
            hotkeys=True,
            tray=True,
            needs_permission=False,
        )

    def grab_screens(self, include_cursor: bool) -> ScreenGrab:
        raise CaptureError(NOT_IMPLEMENTED)

    def active_window_geometry(self) -> QRect | None:
        return None


class WindowsHotkeyBackend(HotkeyBackend):
    """RegisterHotKey with a native event filter on WM_HOTKEY (planned)."""

    name = "windows"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @property
    def supported(self) -> bool:
        return False  # accurate until RegisterHotKey is wired; Preferences shows guidance

    def register(self, binding: HotkeyBinding) -> bool:
        binding.registered = False
        binding.failure_reason = NOT_IMPLEMENTED
        return False


def create_backends() -> tuple[CaptureBackend, HotkeyBackend]:
    return WindowsCaptureBackend(), WindowsHotkeyBackend()
