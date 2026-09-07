"""Linux Wayland backend: the desktop portal's Screenshot interface over QtDBus (PRD 6.4).

Under Wayland an application cannot read other applications' pixels. The
portal is the D-Bus service the compositor exposes for that; SnapMock uses
its Screenshot interface and nothing else. Portal absence is reported, never
worked around: no X11 grab is attempted under Wayland.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QEventLoop, QObject, QRect, QTimer, QUrl, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PyQt6.QtGui import QCursor, QImage

from snapmock.capture.backend import (
    CaptureBackend,
    CaptureCancelledError,
    CaptureError,
    HotkeyBackend,
    NullHotkeyBackend,
    qt_monitors,
)
from snapmock.capture.models import BackendCapabilities, MonitorInfo, ScreenGrab

log = logging.getLogger("snapmock.capture")

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
RESPONSE_SUCCESS = 0
RESPONSE_CANCELLED = 1
CONSENT_TIMEOUT_MS = 120_000

MSG_PORTAL_MISSING = (
    "Screen capture needs the desktop portal (xdg-desktop-portal and a backend for your "
    "desktop). Install it and try again."
)
MSG_PORTAL_FAILED = "The desktop portal did not return a screenshot."
MSG_PORTAL_TIMEOUT = "The desktop did not answer the screenshot request."
MSG_PORTAL_CANCELLED = "Screenshot cancelled in the desktop's dialog."


def request_handle_path(connection: QDBusConnection, token: str) -> str:
    """The Request object path the portal will use for *token* (portal convention)."""
    sender = connection.baseService().lstrip(":").replace(".", "_")
    return f"{PORTAL_PATH}/request/{sender}/{token}"


class PortalScreenshotClient(QObject):
    """One blocking Screenshot call: subscribe to Response, call, wait, read the file."""

    def __init__(
        self,
        connection: QDBusConnection | None = None,
        *,
        service: str = PORTAL_SERVICE,
        path: str = PORTAL_PATH,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bus = connection or QDBusConnection.sessionBus()
        self._service = service
        self._path = path
        self._expected_path = ""
        self._response: tuple[int, dict[str, Any]] | None = None
        self._loop: QEventLoop | None = None

    def is_available(self) -> bool:
        if not self._bus.isConnected():
            return False
        iface = QDBusInterface(self._service, self._path, SCREENSHOT_INTERFACE, self._bus)
        return iface.isValid()

    def screenshot(self, *, timeout_ms: int = CONSENT_TIMEOUT_MS) -> QImage:
        """Take a non-interactive screenshot of the whole desktop. Raises CaptureError."""
        if not self.is_available():
            raise CaptureError(MSG_PORTAL_MISSING)
        token = "snapmock" + uuid.uuid4().hex[:12]
        self._expected_path = request_handle_path(self._bus, token)
        self._response = None
        if not self._bus.connect(
            self._service, "", REQUEST_INTERFACE, "Response", self._on_response
        ):
            raise CaptureError(MSG_PORTAL_FAILED)
        try:
            iface = QDBusInterface(self._service, self._path, SCREENSHOT_INTERFACE, self._bus)
            reply = iface.call("Screenshot", "", {"interactive": False, "handle_token": token})
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                log.error("Portal Screenshot call failed: %s", reply.errorMessage())
                raise CaptureError(MSG_PORTAL_MISSING)
            handle = reply.arguments()[0] if reply.arguments() else None
            handle_path = getattr(handle, "path", lambda: str(handle))()
            if handle_path and handle_path != self._expected_path:
                self._expected_path = str(handle_path)
            if self._response is None:
                self._loop = QEventLoop()
                QTimer.singleShot(timeout_ms, self._loop.quit)
                self._loop.exec()
                self._loop = None
        finally:
            self._bus.disconnect(
                self._service, "", REQUEST_INTERFACE, "Response", self._on_response
            )
        if self._response is None:
            raise CaptureError(MSG_PORTAL_TIMEOUT)
        code, results = self._response
        if code == RESPONSE_CANCELLED:
            raise CaptureCancelledError(MSG_PORTAL_CANCELLED)
        if code != RESPONSE_SUCCESS:
            raise CaptureError(MSG_PORTAL_FAILED)
        uri = str(results.get("uri", ""))
        return read_and_delete(uri)

    @pyqtSlot(QDBusMessage)
    def _on_response(self, message: QDBusMessage) -> None:
        if message.path() != self._expected_path:
            return
        args = message.arguments()
        code = int(args[0]) if args else RESPONSE_SUCCESS + 2
        results = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        self._response = (code, dict(results))
        if self._loop is not None:
            self._loop.quit()


def read_and_delete(uri: str) -> QImage:
    """Load the portal's file and remove it (the file is ours to delete, PRD 6.4)."""
    path = QUrl(uri).toLocalFile() if uri else ""
    if not path:
        raise CaptureError(MSG_PORTAL_FAILED)
    image = QImage(path)
    try:
        os.remove(path)
    except OSError:
        pass
    if image.isNull():
        raise CaptureError(MSG_PORTAL_FAILED)
    image.setDevicePixelRatio(1.0)
    return image


def split_per_monitor(image: QImage, monitors: list[MonitorInfo]) -> dict[str, QImage]:
    """Cut the whole-desktop image into one physical-pixel image per monitor.

    The portal returns the virtual desktop. When its size differs from the
    physical union of the monitors (a compositor scaling choice), the image
    is scaled to that union first so every monitor lands on its own pixels.
    """
    union = QRect()
    for m in monitors:
        union = union.united(m.physical_geometry)
    if union.isEmpty():
        return {}
    if image.size() != union.size():
        image = image.scaled(union.size())
    result: dict[str, QImage] = {}
    for m in monitors:
        rect = m.physical_geometry.translated(-union.topLeft())
        result[m.name] = image.copy(rect)
    return result


class WaylandPortalBackend(CaptureBackend):
    """Screenshot through the portal; no active window, cursor, or hotkeys (PRD 6.4, 6.8)."""

    name = "wayland_portal"

    def __init__(self, screenshot: Callable[[], QImage] | None = None) -> None:
        self._client = PortalScreenshotClient()
        self._screenshot = screenshot or self._client.screenshot

    @property
    def portal_available(self) -> bool:
        return self._client.is_available()

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            full_screen=True,
            active_window=False,
            region=True,
            cursor=False,
            hotkeys=False,
            tray=True,
            needs_permission=False,
        )

    def monitors(self) -> list[MonitorInfo]:
        return qt_monitors()

    def grab_screens(self, include_cursor: bool) -> ScreenGrab:
        monitors = self.monitors()
        if not monitors:
            raise CaptureError("No monitor was found to capture.")
        image = self._screenshot()
        images = split_per_monitor(image, monitors)
        return ScreenGrab(
            images=images,
            monitors=monitors,
            cursor_position=QCursor.pos(),
            taken_at=datetime.now(),
        )


def create_backends() -> tuple[CaptureBackend, HotkeyBackend]:
    """Always activates on a Wayland session; portal absence is reported per capture."""
    backend = WaylandPortalBackend()
    if not backend.portal_available:
        log.warning("Desktop portal not reachable; captures will report the portal message")
    return backend, NullHotkeyBackend()
