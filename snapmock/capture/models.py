"""Application-level data models for screen capture (Screen Capture PRD Section 10).

Only :class:`CaptureMetadata` is written to disk, as part of ``manifest.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from PyQt6.QtCore import QPoint, QRect, QSize
from PyQt6.QtGui import QImage, QKeySequence


class CaptureMode(Enum):
    """What part of the display is read (PRD 10.1). Serialized as the lowercase string."""

    FULL_SCREEN = "full_screen"
    ACTIVE_WINDOW = "active_window"
    REGION = "region"
    SCROLLING = "scrolling"  # reserved; not offered in version 1

    @classmethod
    def from_string(cls, value: str, default: CaptureMode | None = None) -> CaptureMode:
        """Parse a stored or command-line value; ``window`` and ``full`` are accepted."""
        aliases = {"window": cls.ACTIVE_WINDOW, "full": cls.FULL_SCREEN, "screen": cls.FULL_SCREEN}
        text = value.strip().lower()
        if text in aliases:
            return aliases[text]
        for mode in cls:
            if mode.value == text:
                return mode
        return default if default is not None else cls.REGION


class FullScreenScope(Enum):
    """Which monitors a full-screen capture keeps (PRD 4.4)."""

    MONITOR_UNDER_CURSOR = "monitor_under_cursor"
    ALL_MONITORS = "all_monitors"

    @classmethod
    def from_string(cls, value: str) -> FullScreenScope:
        return cls.ALL_MONITORS if value == cls.ALL_MONITORS.value else cls.MONITOR_UNDER_CURSOR


class PermissionState(Enum):
    """Result of :meth:`CaptureBackend.request_permission` (PRD 6.1)."""

    GRANTED = "granted"
    DENIED = "denied"
    NOT_REQUIRED = "not_required"


# Hotkey action identifiers (PRD 10.7) and the mode each one starts.
HOTKEY_ACTION_REGION = "capture.region"
HOTKEY_ACTION_WINDOW = "capture.window"
HOTKEY_ACTION_FULL_SCREEN = "capture.full_screen"
HOTKEY_ACTIONS: dict[str, CaptureMode] = {
    HOTKEY_ACTION_REGION: CaptureMode.REGION,
    HOTKEY_ACTION_WINDOW: CaptureMode.ACTIVE_WINDOW,
    HOTKEY_ACTION_FULL_SCREEN: CaptureMode.FULL_SCREEN,
}

# Request origins (PRD 10.2).
ORIGIN_HOTKEY = "hotkey"
ORIGIN_TRAY = "tray"
ORIGIN_TOOLBAR = "toolbar"
ORIGIN_MENU = "menu"
ORIGIN_COMMAND_LINE = "command_line"


@dataclass
class CaptureRequest:
    """What an entry point asks the capture manager to do (PRD 10.2)."""

    mode: CaptureMode
    delay_seconds: int = 0
    include_cursor: bool = False
    copy_to_clipboard: bool = False
    hide_window: bool = True
    origin: str = ORIGIN_MENU


@dataclass
class MonitorInfo:
    """One connected monitor (PRD 10.4)."""

    name: str
    logical_geometry: QRect
    physical_size: QSize
    device_pixel_ratio: float
    is_primary: bool = False

    @property
    def physical_geometry(self) -> QRect:
        """Position and size in virtual-desktop physical pixels."""
        ratio = self.device_pixel_ratio
        return QRect(
            round(self.logical_geometry.x() * ratio),
            round(self.logical_geometry.y() * ratio),
            self.physical_size.width(),
            self.physical_size.height(),
        )


@dataclass
class ScreenGrab:
    """The frozen screen image, one physical-pixel image per monitor (PRD 10.3).

    ``monitors`` is the monitor list at grab time, kept with the images so a
    monitor change after the grab does not affect the capture (PRD 4.4).
    """

    images: dict[str, QImage]
    monitors: list[MonitorInfo]
    cursor_image: QImage | None = None
    cursor_hotspot: QPoint | None = None
    cursor_position: QPoint | None = None
    taken_at: datetime = field(default_factory=datetime.now)

    def monitor_by_name(self, name: str) -> MonitorInfo | None:
        for m in self.monitors:
            if m.name == name:
                return m
        return None

    def monitor_at(self, logical_point: QPoint) -> MonitorInfo | None:
        """The monitor whose logical geometry contains *logical_point*."""
        for m in self.monitors:
            if m.logical_geometry.contains(logical_point):
                return m
        return None

    @property
    def virtual_logical_rect(self) -> QRect:
        rect = QRect()
        for m in self.monitors:
            rect = rect.united(m.logical_geometry)
        return rect


@dataclass
class CaptureMetadata:
    """Facts about how a capture was taken, stored in ``manifest.json`` (PRD 10.5, 12.1)."""

    mode: CaptureMode
    requested_mode: CaptureMode
    monitor_name: str | None
    device_pixel_ratio: float
    screen_rect: QRect
    cursor_included: bool
    platform: str
    backend: str
    window_title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "requested_mode": self.requested_mode.value,
            "monitor_name": self.monitor_name,
            "device_pixel_ratio": float(self.device_pixel_ratio),
            "screen_rect": {
                "x": self.screen_rect.x(),
                "y": self.screen_rect.y(),
                "width": self.screen_rect.width(),
                "height": self.screen_rect.height(),
            },
            "cursor_included": bool(self.cursor_included),
            "platform": self.platform,
            "backend": self.backend,
            "window_title": self.window_title,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaptureMetadata:
        rect = data.get("screen_rect") or {}
        if not isinstance(rect, dict):
            rect = {}
        monitor = data.get("monitor_name")
        title = data.get("window_title")
        return cls(
            mode=CaptureMode.from_string(str(data.get("mode", "region"))),
            requested_mode=CaptureMode.from_string(
                str(data.get("requested_mode", data.get("mode", "region")))
            ),
            monitor_name=str(monitor) if monitor is not None else None,
            device_pixel_ratio=float(data.get("device_pixel_ratio", 1.0)),
            screen_rect=QRect(
                int(rect.get("x", 0)),
                int(rect.get("y", 0)),
                int(rect.get("width", 0)),
                int(rect.get("height", 0)),
            ),
            cursor_included=bool(data.get("cursor_included", False)),
            platform=str(data.get("platform", "")),
            backend=str(data.get("backend", "")),
            window_title=str(title) if title is not None else None,
        )


@dataclass(frozen=True)
class BackendCapabilities:
    """What a backend supports on this session (PRD 10.6)."""

    full_screen: bool = False
    active_window: bool = False
    region: bool = False
    cursor: bool = False
    hotkeys: bool = False
    tray: bool = False
    needs_permission: bool = False

    @property
    def any_capture(self) -> bool:
        return self.full_screen or self.active_window or self.region

    def supports(self, mode: CaptureMode) -> bool:
        if mode is CaptureMode.FULL_SCREEN:
            return self.full_screen
        if mode is CaptureMode.ACTIVE_WINDOW:
            return self.active_window
        if mode is CaptureMode.REGION:
            return self.region
        return False


@dataclass
class HotkeyBinding:
    """One global hotkey as stored and as registered (PRD 10.7)."""

    action: str
    key_sequence: QKeySequence
    registered: bool = False
    failure_reason: str | None = None

    @property
    def is_bound(self) -> bool:
        return not self.key_sequence.isEmpty()

    @property
    def key_text(self) -> str:
        """Portable text form, the form stored in settings (PRD 12.2)."""
        return self.key_sequence.toString(QKeySequence.SequenceFormat.PortableText)

    @property
    def display_text(self) -> str:
        return self.key_sequence.toString(QKeySequence.SequenceFormat.NativeText)


@dataclass
class CaptureResult:
    """The value carried by ``capture_completed`` (PRD 10.8)."""

    image: QImage
    metadata: CaptureMetadata
    taken_at: datetime
