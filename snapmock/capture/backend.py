"""The capture backend abstraction (Screen Capture PRD Sections 6.1, 6.7).

The application sees :class:`CaptureBackend` and :class:`HotkeyBackend` and
nothing platform-specific. This module also holds the null backends used
when nothing is supported, a Qt-based grab shared by the X11, macOS and
Windows backends, and fake backends for the test suite.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime

from PyQt6.QtCore import QObject, QPoint, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QImage, QLinearGradient, QPainter

from snapmock.capture.models import (
    BackendCapabilities,
    HotkeyBinding,
    MonitorInfo,
    PermissionState,
    ScreenGrab,
)

log = logging.getLogger("snapmock.capture")

UNSUPPORTED_PLATFORM_MESSAGE = "Screen capture is not supported on this platform."


class CaptureError(Exception):
    """A capture failed; ``str(error)`` is the user-readable reason (PRD 7.4)."""


class CaptureBackend(ABC):
    """Platform-specific pixel reading (PRD 6.1). One instance per process."""

    #: ``x11``, ``wayland_portal``, ``macos``, ``windows``, ``null`` or ``fake``.
    name: str = "null"

    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Which modes and options this backend supports on this session."""

    @abstractmethod
    def monitors(self) -> list[MonitorInfo]:
        """Every connected monitor."""

    @abstractmethod
    def grab_screens(self, include_cursor: bool) -> ScreenGrab:
        """One physical-pixel image per monitor. Raises :class:`CaptureError`."""

    def active_window_geometry(self) -> QRect | None:
        """Logical geometry of the focused window, excluding shadow, or None."""
        return None

    def active_window_title(self) -> str | None:
        return None

    def request_permission(self) -> PermissionState:
        return PermissionState.NOT_REQUIRED


class HotkeyBackend(QObject):
    """Global hotkey registration (PRD 6.7).

    Signals
    -------
    triggered(str)
        A registered hotkey was pressed; carries the binding's action.
    """

    triggered = pyqtSignal(str)

    name: str = "null"

    @property
    def supported(self) -> bool:
        """Whether this backend can register hotkeys at all."""
        return False

    def register(self, binding: HotkeyBinding) -> bool:
        """Register *binding*, updating its ``registered`` and ``failure_reason``."""
        binding.registered = False
        binding.failure_reason = "Global hotkeys are not available on this desktop."
        return False

    def unregister(self, binding: HotkeyBinding) -> None:
        binding.registered = False

    def unregister_all(self) -> None:
        return None


# --- null backends (PRD 6.2: unrecognized platform) ---


class NullCaptureBackend(CaptureBackend):
    """Reports nothing supported; every grab fails with the platform message."""

    name = "null"

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities()

    def monitors(self) -> list[MonitorInfo]:
        return qt_monitors()

    def grab_screens(self, include_cursor: bool) -> ScreenGrab:
        raise CaptureError(UNSUPPORTED_PLATFORM_MESSAGE)


class NullHotkeyBackend(HotkeyBackend):
    """Reports every registration as unsupported (Wayland, macOS in version 1)."""

    name = "null"


# --- Qt-based grab shared by the X11, macOS and Windows backends ---


def qt_monitors() -> list[MonitorInfo]:
    """Build the monitor list from Qt's screens."""
    result: list[MonitorInfo] = []
    primary = QGuiApplication.primaryScreen()
    for screen in QGuiApplication.screens():
        ratio = float(screen.devicePixelRatio())
        geo = screen.geometry()
        result.append(
            MonitorInfo(
                name=screen.name() or f"screen{len(result)}",
                logical_geometry=QRect(geo),
                physical_size=QSize(round(geo.width() * ratio), round(geo.height() * ratio)),
                device_pixel_ratio=ratio,
                is_primary=screen is primary,
            )
        )
    return result


class QtScreenGrabBackend(CaptureBackend):
    """Grabs every screen through Qt's root-window grab (PRD 6.3, 6.5, 6.6).

    Subclasses add the cursor image and the active window through platform
    calls; when ``_cursor_image`` returns None the cursor is left out.
    """

    def monitors(self) -> list[MonitorInfo]:
        return qt_monitors()

    def grab_screens(self, include_cursor: bool) -> ScreenGrab:
        monitors = self.monitors()
        images: dict[str, QImage] = {}
        for screen, info in zip(QGuiApplication.screens(), monitors, strict=False):
            pixmap = screen.grabWindow()
            if pixmap.isNull():
                raise CaptureError("The screen could not be read.")
            image = pixmap.toImage()
            if image.size() != info.physical_size and not info.physical_size.isEmpty():
                image = image.scaled(info.physical_size)
            image.setDevicePixelRatio(1.0)
            images[info.name] = image
        if not images:
            raise CaptureError("No monitor was found to capture.")
        grab = ScreenGrab(images=images, monitors=monitors, taken_at=datetime.now())
        grab.cursor_position = QCursor.pos()
        if include_cursor:
            cursor = self._cursor_image()
            if cursor is not None:
                grab.cursor_image, grab.cursor_hotspot = cursor
        return grab

    def _cursor_image(self) -> tuple[QImage, QPoint] | None:
        """Cursor bitmap with alpha and its hotspot, or None when unavailable."""
        return None


# --- fakes for tests (PRD 14.5: every backend-independent path runs against a fake) ---


def synthetic_image(size: QSize, seed: int = 0) -> QImage:
    """A gradient image whose pixels differ by position, so crops are verifiable."""
    image = QImage(size, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0))
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, size.width(), size.height())
    gradient.setColorAt(0.0, QColor((40 * seed) % 256, 80, 200))
    gradient.setColorAt(1.0, QColor(255, (60 * seed + 120) % 256, 30))
    painter.fillRect(image.rect(), gradient)
    painter.end()
    return image


class FakeCaptureBackend(CaptureBackend):
    """Returns synthetic monitors and images; every knob is a plain attribute."""

    name = "fake"

    def __init__(self, monitors: list[MonitorInfo] | None = None) -> None:
        self.fake_monitors: list[MonitorInfo] = monitors or [
            MonitorInfo("fake-0", QRect(0, 0, 200, 100), QSize(200, 100), 1.0, True)
        ]
        self.fake_capabilities = BackendCapabilities(
            full_screen=True, active_window=True, region=True, cursor=True, hotkeys=True, tray=True
        )
        self.fake_cursor_image: QImage | None = None
        self.fake_cursor_hotspot = QPoint(0, 0)
        self.fake_cursor_position = QPoint(10, 10)
        self.fake_active_window: QRect | None = QRect(20, 10, 60, 40)
        self.fake_window_title: str | None = "Fake Window"
        self.fake_permission = PermissionState.NOT_REQUIRED
        self.fail_with: str | None = None
        self.grab_calls: list[bool] = []
        self.permission_requests = 0

    def capabilities(self) -> BackendCapabilities:
        return self.fake_capabilities

    def monitors(self) -> list[MonitorInfo]:
        return list(self.fake_monitors)

    def grab_screens(self, include_cursor: bool) -> ScreenGrab:
        self.grab_calls.append(include_cursor)
        if self.fail_with is not None:
            raise CaptureError(self.fail_with)
        images = {
            m.name: synthetic_image(m.physical_size, seed=i)
            for i, m in enumerate(self.fake_monitors)
        }
        grab = ScreenGrab(
            images=images,
            monitors=self.monitors(),
            cursor_position=QPoint(self.fake_cursor_position),
            taken_at=datetime.now(),
        )
        if include_cursor and self.fake_capabilities.cursor:
            cursor = self.fake_cursor_image
            if cursor is None:
                cursor = QImage(8, 8, QImage.Format.Format_ARGB32)
                cursor.fill(QColor(255, 255, 255, 255))
            grab.cursor_image = cursor
            grab.cursor_hotspot = QPoint(self.fake_cursor_hotspot)
        return grab

    def active_window_geometry(self) -> QRect | None:
        return QRect(self.fake_active_window) if self.fake_active_window else None

    def active_window_title(self) -> str | None:
        return self.fake_window_title

    def request_permission(self) -> PermissionState:
        self.permission_requests += 1
        return self.fake_permission


class FakeHotkeyBackend(HotkeyBackend):
    """Accepts every registration except keys listed in ``refused``."""

    name = "fake"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.refused: set[str] = set()
        self.registered: dict[str, str] = {}

    @property
    def supported(self) -> bool:
        return True

    def register(self, binding: HotkeyBinding) -> bool:
        if binding.key_text in self.refused:
            binding.registered = False
            binding.failure_reason = "In use by another application"
            return False
        self.registered[binding.action] = binding.key_text
        binding.registered = True
        binding.failure_reason = None
        return True

    def unregister(self, binding: HotkeyBinding) -> None:
        self.registered.pop(binding.action, None)
        binding.registered = False

    def unregister_all(self) -> None:
        self.registered.clear()

    def fire(self, action: str) -> None:
        """Simulate the operating system delivering the hotkey for *action*."""
        if action in self.registered:
            self.triggered.emit(action)
