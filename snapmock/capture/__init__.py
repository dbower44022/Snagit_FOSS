"""Screen capture: modes, entry points, the region overlay, and platform backends.

Nothing outside this package imports a platform module. The editor talks
to :class:`snapmock.capture.manager.CaptureManager` and nothing else.

Backend selection (PRD 6.2) happens here, once, from the platform name and
the session type. It is not user-configurable.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys

from PyQt6.QtGui import QGuiApplication

from snapmock.capture.backend import (
    CaptureBackend,
    HotkeyBackend,
    NullCaptureBackend,
    NullHotkeyBackend,
)

log = logging.getLogger("snapmock.capture")


def is_wayland_session() -> bool:
    """Whether Qt runs on Wayland or the session environment reports Wayland."""
    platform = QGuiApplication.platformName().lower() if QGuiApplication.instance() else ""
    if platform.startswith("wayland"):
        return True
    if platform in ("xcb", "offscreen", "minimal"):
        return False
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def select_backends() -> tuple[CaptureBackend, HotkeyBackend]:
    """Pick the capture and hotkey backends for this platform and session.

    Linux on Wayland selects the portal backend; Linux otherwise selects X11;
    macOS and Windows select their backends. Anything else, and any platform
    whose module cannot activate, gets the null backends.
    """
    capture: CaptureBackend = NullCaptureBackend()
    hotkeys: HotkeyBackend = NullHotkeyBackend()
    module_name: str | None = None
    if sys.platform.startswith("linux"):
        module_name = "wayland_portal" if is_wayland_session() else "x11"
    elif sys.platform == "darwin":
        module_name = "macos"
    elif sys.platform.startswith("win"):
        module_name = "windows"
    if module_name is not None:
        try:
            module = importlib.import_module(f"snapmock.capture.{module_name}")
            created = module.create_backends()
            capture, hotkeys = created
        except (ImportError, OSError, AttributeError) as e:
            log.warning(
                "Capture backend %s unavailable (%s); using the null backend", module_name, e
            )
    log.info("Selected capture backend %s, hotkey backend %s", capture.name, hotkeys.name)
    return capture, hotkeys
