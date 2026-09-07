"""Linux X11 backend and X11 hotkey backend through ctypes (PRD 6.3, 6.7).

This module imports on every platform. Nothing touches the X server until
:func:`create_backends` runs, and that raises :class:`OSError` unless the
session is X11 and libX11 loads. The screen grab itself is Qt's (see
:class:`QtScreenGrabBackend`); ctypes supplies what Qt does not expose:
the active window, the XFixes cursor image, and root-window key grabs.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
from ctypes import (
    CFUNCTYPE,
    POINTER,
    Structure,
    byref,
    c_char,
    c_char_p,
    c_int,
    c_long,
    c_short,
    c_ubyte,
    c_uint,
    c_ulong,
    c_ushort,
    c_void_p,
)
from typing import Any

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPoint, QRect, QSocketNotifier, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QKeySequence

from snapmock.capture.backend import (
    CaptureBackend,
    HotkeyBackend,
    QtScreenGrabBackend,
    qt_monitors,
)
from snapmock.capture.models import BackendCapabilities, HotkeyBinding

log = logging.getLogger("snapmock.capture")

# --- X11 constants ---

KEY_PRESS = 2
GRAB_MODE_ASYNC = 1
ANY_PROPERTY_TYPE = 0
XA_CARDINAL = 6
XA_WINDOW = 33
XA_STRING = 31
SHIFT_MASK = 1 << 0
LOCK_MASK = 1 << 1
CONTROL_MASK = 1 << 2
MOD1_MASK = 1 << 3
MOD2_MASK = 1 << 4
MOD3_MASK = 1 << 5
MOD4_MASK = 1 << 6
MOD5_MASK = 1 << 7
XK_NUM_LOCK = 0xFF7F
XEVENT_SIZE = 192  # sizeof(XEvent) on LP64

Window = c_ulong
Atom = c_ulong
KeySym = c_ulong
KeyCode = c_ubyte


class XKeyEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", c_int),
        ("display", c_void_p),
        ("window", Window),
        ("root", Window),
        ("subwindow", Window),
        ("time", c_ulong),
        ("x", c_int),
        ("y", c_int),
        ("x_root", c_int),
        ("y_root", c_int),
        ("state", c_uint),
        ("keycode", c_uint),
        ("same_screen", c_int),
    ]


class XEvent(ctypes.Union):
    _fields_ = [("type", c_int), ("xkey", XKeyEvent), ("pad", c_char * XEVENT_SIZE)]


class XErrorEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("display", c_void_p),
        ("resourceid", c_ulong),
        ("serial", c_ulong),
        ("error_code", c_ubyte),
        ("request_code", c_ubyte),
        ("minor_code", c_ubyte),
    ]


class XModifierKeymap(Structure):
    _fields_ = [("max_keypermod", c_int), ("modifiermap", POINTER(KeyCode))]


class XFixesCursorImage(Structure):
    _fields_ = [
        ("x", c_short),
        ("y", c_short),
        ("width", c_ushort),
        ("height", c_ushort),
        ("xhot", c_ushort),
        ("yhot", c_ushort),
        ("cursor_serial", c_ulong),
        ("pixels", POINTER(c_ulong)),
        ("atom", Atom),
        ("name", c_char_p),
    ]


ERROR_HANDLER_TYPE = CFUNCTYPE(c_int, c_void_p, POINTER(XErrorEvent))


def _load(name: str) -> ctypes.CDLL:
    path = ctypes.util.find_library(name)
    if path is None:
        raise OSError(f"lib{name} not found")
    return ctypes.CDLL(path)


class X11Connection:
    """One Xlib display connection of our own, with the calls this backend needs.

    A separate connection from Qt's keeps grabbed key events on a socket we
    read ourselves, so no native event filter or event parsing is required.
    """

    def __init__(self) -> None:
        self.x = _load("X11")
        self._error_count = 0
        self._bind()
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise OSError("cannot open the X display")
        self.root: int = self.x.XDefaultRootWindow(self.display)
        self._handler = ERROR_HANDLER_TYPE(self._on_error)
        self._previous_handler = self.x.XSetErrorHandler(self._handler)
        self.xfixes: ctypes.CDLL | None = None
        try:
            self.xfixes = _load("Xfixes")
            self._bind_xfixes(self.xfixes)
            event_base, error_base = c_int(), c_int()
            if not self.xfixes.XFixesQueryExtension(
                self.display, byref(event_base), byref(error_base)
            ):
                self.xfixes = None
        except OSError as e:
            log.info("XFixes unavailable: %s", e)
            self.xfixes = None
        self._atoms: dict[str, int] = {}
        self._supported: set[int] | None = None
        self.num_lock_mask = self._find_num_lock_mask()

    def _bind(self) -> None:
        x = self.x
        x.XOpenDisplay.argtypes = [c_char_p]
        x.XOpenDisplay.restype = c_void_p
        x.XCloseDisplay.argtypes = [c_void_p]
        x.XDefaultRootWindow.argtypes = [c_void_p]
        x.XDefaultRootWindow.restype = Window
        x.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]
        x.XInternAtom.restype = Atom
        x.XGetWindowProperty.argtypes = [
            c_void_p,
            Window,
            Atom,
            c_long,
            c_long,
            c_int,
            Atom,
            POINTER(Atom),
            POINTER(c_int),
            POINTER(c_ulong),
            POINTER(c_ulong),
            POINTER(POINTER(c_ubyte)),
        ]
        x.XGetWindowProperty.restype = c_int
        x.XFree.argtypes = [c_void_p]
        x.XGetGeometry.argtypes = [
            c_void_p,
            c_ulong,
            POINTER(Window),
            POINTER(c_int),
            POINTER(c_int),
            POINTER(c_uint),
            POINTER(c_uint),
            POINTER(c_uint),
            POINTER(c_uint),
        ]
        x.XGetGeometry.restype = c_int
        x.XTranslateCoordinates.argtypes = [
            c_void_p,
            Window,
            Window,
            c_int,
            c_int,
            POINTER(c_int),
            POINTER(c_int),
            POINTER(Window),
        ]
        x.XTranslateCoordinates.restype = c_int
        x.XGrabKey.argtypes = [c_void_p, c_int, c_uint, Window, c_int, c_int, c_int]
        x.XUngrabKey.argtypes = [c_void_p, c_int, c_uint, Window]
        x.XKeysymToKeycode.argtypes = [c_void_p, KeySym]
        x.XKeysymToKeycode.restype = KeyCode
        x.XStringToKeysym.argtypes = [c_char_p]
        x.XStringToKeysym.restype = KeySym
        x.XkbKeycodeToKeysym.argtypes = [c_void_p, KeyCode, c_int, c_int]
        x.XkbKeycodeToKeysym.restype = KeySym
        x.XSync.argtypes = [c_void_p, c_int]
        x.XFlush.argtypes = [c_void_p]
        x.XPending.argtypes = [c_void_p]
        x.XPending.restype = c_int
        x.XNextEvent.argtypes = [c_void_p, POINTER(XEvent)]
        x.XConnectionNumber.argtypes = [c_void_p]
        x.XConnectionNumber.restype = c_int
        x.XSetErrorHandler.argtypes = [ERROR_HANDLER_TYPE]
        x.XSetErrorHandler.restype = c_void_p
        x.XGetModifierMapping.argtypes = [c_void_p]
        x.XGetModifierMapping.restype = POINTER(XModifierKeymap)
        x.XFreeModifiermap.argtypes = [POINTER(XModifierKeymap)]

    @staticmethod
    def _bind_xfixes(xfixes: ctypes.CDLL) -> None:
        xfixes.XFixesQueryExtension.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        xfixes.XFixesQueryExtension.restype = c_int
        xfixes.XFixesGetCursorImage.argtypes = [c_void_p]
        xfixes.XFixesGetCursorImage.restype = POINTER(XFixesCursorImage)

    def close(self) -> None:
        if self.display:
            self.x.XCloseDisplay(self.display)
            self.display = None

    # --- errors ---

    def _on_error(self, _display: int, event: Any) -> int:
        self._error_count += 1
        log.debug(
            "X error code=%d request=%d", event.contents.error_code, event.contents.request_code
        )
        return 0

    def sync_and_check(self) -> bool:
        """Flush the request queue; True when no X error arrived since the last check."""
        self._error_count = 0
        self.x.XSync(self.display, 0)
        return self._error_count == 0

    @property
    def fd(self) -> int:
        return int(self.x.XConnectionNumber(self.display))

    # --- atoms and properties ---

    def atom(self, name: str) -> int:
        if name not in self._atoms:
            self._atoms[name] = int(self.x.XInternAtom(self.display, name.encode(), 0))
        return self._atoms[name]

    def get_property(
        self, window: int, name: str, expected_type: int = ANY_PROPERTY_TYPE
    ) -> tuple[int, int, bytes]:
        """Return (actual_type, format, raw bytes) of a window property; empty on absence."""
        actual_type, actual_format = Atom(), c_int()
        nitems, bytes_after = c_ulong(), c_ulong()
        data = POINTER(c_ubyte)()
        status = self.x.XGetWindowProperty(
            self.display,
            window,
            self.atom(name),
            0,
            1024,
            0,
            expected_type,
            byref(actual_type),
            byref(actual_format),
            byref(nitems),
            byref(bytes_after),
            byref(data),
        )
        if status != 0 or not data or nitems.value == 0:
            if data:
                self.x.XFree(data)
            return 0, 0, b""
        unit = {8: 1, 16: 2, 32: 8}.get(actual_format.value, 1)  # 32-bit items are longs
        raw = ctypes.string_at(data, nitems.value * unit)
        self.x.XFree(data)
        return int(actual_type.value), int(actual_format.value), raw

    def get_cardinals(self, window: int, name: str) -> list[int]:
        _t, fmt, raw = self.get_property(window, name)
        if fmt != 32 or not raw:
            return []
        count = len(raw) // 8
        return list((c_ulong * count).from_buffer_copy(raw))

    def get_text(self, window: int, name: str) -> str | None:
        _t, fmt, raw = self.get_property(window, name)
        if fmt != 8 or not raw:
            return None
        return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")

    def supports(self, atom_name: str) -> bool:
        """Whether the window manager lists *atom_name* in _NET_SUPPORTED (EWMH)."""
        if self._supported is None:
            self._supported = set(self.get_cardinals(self.root, "_NET_SUPPORTED"))
        return self.atom(atom_name) in self._supported

    # --- windows ---

    def active_window(self) -> int | None:
        values = self.get_cardinals(self.root, "_NET_ACTIVE_WINDOW")
        if not values or values[0] == 0:
            return None
        return values[0]

    def window_frame_rect(self, window: int) -> QRect | None:
        """The window's frame rectangle in root (physical) pixels, shadow excluded."""
        root_return = Window()
        x, y = c_int(), c_int()
        w, h, border, depth = c_uint(), c_uint(), c_uint(), c_uint()
        if not self.x.XGetGeometry(
            self.display,
            window,
            byref(root_return),
            byref(x),
            byref(y),
            byref(w),
            byref(h),
            byref(border),
            byref(depth),
        ):
            return None
        dst_x, dst_y, child = c_int(), c_int(), Window()
        self.x.XTranslateCoordinates(
            self.display, window, self.root, 0, 0, byref(dst_x), byref(dst_y), byref(child)
        )
        rect = QRect(dst_x.value, dst_y.value, w.value, h.value)
        frame = self.get_cardinals(window, "_NET_FRAME_EXTENTS")
        if len(frame) == 4:  # left, right, top, bottom: decorations outside the client
            rect.adjust(-frame[0], -frame[2], frame[1], frame[3])
        shadow = self.get_cardinals(window, "_GTK_FRAME_EXTENTS")
        if len(shadow) == 4:  # client-side decorations: shadow inside the client area
            rect.adjust(shadow[0], shadow[2], -shadow[1], -shadow[3])
        return rect if rect.isValid() and not rect.isEmpty() else None

    def window_title(self, window: int) -> str | None:
        return self.get_text(window, "_NET_WM_NAME") or self.get_text(window, "WM_NAME")

    # --- cursor ---

    def cursor_image(self) -> tuple[QImage, QPoint] | None:
        if self.xfixes is None:
            return None
        ptr = self.xfixes.XFixesGetCursorImage(self.display)
        if not ptr:
            return None
        try:
            info = ptr.contents
            width, height = int(info.width), int(info.height)
            if width <= 0 or height <= 0:
                return None
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            count = width * height
            pixels = ctypes.cast(info.pixels, POINTER(c_ulong * count)).contents
            for i in range(count):
                image.setPixel(i % width, i // width, int(pixels[i]) & 0xFFFFFFFF)
            return image, QPoint(int(info.xhot), int(info.yhot))
        finally:
            self.x.XFree(ptr)

    # --- keys ---

    def _find_num_lock_mask(self) -> int:
        mapping = self.x.XGetModifierMapping(self.display)
        if not mapping:
            return MOD2_MASK
        try:
            per = mapping.contents.max_keypermod
            for mod_index in range(8):
                for k in range(per):
                    code = mapping.contents.modifiermap[mod_index * per + k]
                    if code and self.x.XkbKeycodeToKeysym(self.display, code, 0, 0) == XK_NUM_LOCK:
                        return 1 << mod_index
        finally:
            self.x.XFreeModifiermap(mapping)
        return MOD2_MASK

    def keycode_for(self, keysym_name: str) -> int:
        keysym = self.x.XStringToKeysym(keysym_name.encode())
        if keysym == 0:
            return 0
        return int(self.x.XKeysymToKeycode(self.display, keysym))

    def grab_key(self, keycode: int, modifiers: int) -> bool:
        """Grab on the root window for every lock-modifier combination (PRD 6.7)."""
        for combo in self._lock_combinations(modifiers):
            self.x.XGrabKey(
                self.display, keycode, combo, self.root, 1, GRAB_MODE_ASYNC, GRAB_MODE_ASYNC
            )
        if self.sync_and_check():
            return True
        self.ungrab_key(keycode, modifiers)
        return False

    def ungrab_key(self, keycode: int, modifiers: int) -> None:
        for combo in self._lock_combinations(modifiers):
            self.x.XUngrabKey(self.display, keycode, combo, self.root)
        self.sync_and_check()

    def _lock_combinations(self, modifiers: int) -> list[int]:
        locks = (0, LOCK_MASK, self.num_lock_mask, LOCK_MASK | self.num_lock_mask)
        return sorted({modifiers | lock for lock in locks})

    def lock_masks(self) -> int:
        return LOCK_MASK | self.num_lock_mask

    def pending_key_presses(self) -> list[tuple[int, int]]:
        """Drain the event queue; return (keycode, state without lock bits) per key press."""
        presses: list[tuple[int, int]] = []
        event = XEvent()
        while self.x.XPending(self.display) > 0:
            self.x.XNextEvent(self.display, byref(event))
            if event.type == KEY_PRESS:
                presses.append(
                    (int(event.xkey.keycode), int(event.xkey.state) & ~self.lock_masks())
                )
        return presses


# --- Qt key sequence to X keysym ---

_KEYSYM_NAMES: dict[int, str] = {
    Qt.Key.Key_Print.value: "Print",
    Qt.Key.Key_SysReq.value: "Sys_Req",
    Qt.Key.Key_Space.value: "space",
    Qt.Key.Key_Escape.value: "Escape",
    Qt.Key.Key_Tab.value: "Tab",
    Qt.Key.Key_Backspace.value: "BackSpace",
    Qt.Key.Key_Return.value: "Return",
    Qt.Key.Key_Enter.value: "KP_Enter",
    Qt.Key.Key_Insert.value: "Insert",
    Qt.Key.Key_Delete.value: "Delete",
    Qt.Key.Key_Pause.value: "Pause",
    Qt.Key.Key_Home.value: "Home",
    Qt.Key.Key_End.value: "End",
    Qt.Key.Key_Left.value: "Left",
    Qt.Key.Key_Up.value: "Up",
    Qt.Key.Key_Right.value: "Right",
    Qt.Key.Key_Down.value: "Down",
    Qt.Key.Key_PageUp.value: "Prior",
    Qt.Key.Key_PageDown.value: "Next",
    Qt.Key.Key_ScrollLock.value: "Scroll_Lock",
    Qt.Key.Key_Menu.value: "Menu",
}


def keysym_name_for(key: Qt.Key) -> str | None:
    """The X keysym name for a Qt key, or None when there is no portable mapping."""
    value = key.value
    if value in _KEYSYM_NAMES:
        return _KEYSYM_NAMES[value]
    if Qt.Key.Key_F1.value <= value <= Qt.Key.Key_F35.value:
        return f"F{value - Qt.Key.Key_F1.value + 1}"
    if Qt.Key.Key_0.value <= value <= Qt.Key.Key_9.value:
        return chr(value)
    if Qt.Key.Key_A.value <= value <= Qt.Key.Key_Z.value:
        return chr(value).lower()
    if 0x20 < value < 0x7F:
        return chr(value)
    return None


def x_modifiers_for(modifiers: Qt.KeyboardModifier) -> int:
    mask = 0
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        mask |= SHIFT_MASK
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        mask |= CONTROL_MASK
    if modifiers & Qt.KeyboardModifier.AltModifier:
        mask |= MOD1_MASK
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        mask |= MOD4_MASK
    return mask


def parse_key_sequence(sequence: QKeySequence) -> tuple[str, int] | None:
    """(keysym name, X modifier mask) for a single-key sequence, or None."""
    if sequence.isEmpty():
        return None
    combination = sequence[0]
    name = keysym_name_for(combination.key())
    if name is None:
        return None
    return name, x_modifiers_for(combination.keyboardModifiers())


# --- backends ---


class X11CaptureBackend(QtScreenGrabBackend):
    """Qt grab plus ctypes for the active window and the XFixes cursor (PRD 6.3)."""

    name = "x11"

    def __init__(self, connection: X11Connection) -> None:
        self._x = connection
        self._has_ewmh = connection.supports("_NET_ACTIVE_WINDOW")
        self._has_cursor = connection.xfixes is not None and connection.cursor_image() is not None

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            full_screen=True,
            active_window=self._has_ewmh,
            region=True,
            cursor=self._has_cursor,
            hotkeys=True,
            tray=True,
            needs_permission=False,
        )

    def active_window_geometry(self) -> QRect | None:
        if not self._has_ewmh:
            return None
        window = self._x.active_window()
        if window is None:
            return None
        physical = self._x.window_frame_rect(window)
        if physical is None:
            return None
        return physical_to_logical(physical)

    def active_window_title(self) -> str | None:
        window = self._x.active_window()
        return self._x.window_title(window) if window is not None else None

    def _cursor_image(self) -> tuple[QImage, QPoint] | None:
        if not self._has_cursor:
            return None
        try:
            return self._x.cursor_image()
        except (OSError, ValueError) as e:
            log.info("XFixes cursor read failed: %s", e)
            return None


def physical_to_logical(physical: QRect) -> QRect:
    """Map a root-window (physical pixel) rectangle to Qt's logical virtual desktop."""
    monitors = qt_monitors()
    best = None
    best_area = -1
    for m in monitors:
        area = m.physical_geometry.intersected(physical)
        size = max(0, area.width()) * max(0, area.height())
        if size > best_area:
            best, best_area = m, size
    if best is None:
        return QRect(physical)
    ratio = best.device_pixel_ratio
    origin = best.physical_geometry.topLeft()
    left = best.logical_geometry.x() + (physical.x() - origin.x()) / ratio
    top = best.logical_geometry.y() + (physical.y() - origin.y()) / ratio
    return QRect(
        round(left), round(top), round(physical.width() / ratio), round(physical.height() / ratio)
    )


class X11HotkeyBackend(HotkeyBackend):
    """XGrabKey on the root window, delivered through a socket notifier (PRD 6.7)."""

    name = "x11"

    def __init__(self, connection: X11Connection, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._x = connection
        self._grabs: dict[str, tuple[int, int]] = {}  # action -> (keycode, modifiers)
        self._notifier = QSocketNotifier(
            sip.voidptr(connection.fd), QSocketNotifier.Type.Read, self
        )
        self._notifier.activated.connect(self._on_readable)

    @property
    def supported(self) -> bool:
        return True

    def register(self, binding: HotkeyBinding) -> bool:
        self.unregister(binding)
        parsed = parse_key_sequence(binding.key_sequence)
        if parsed is None:
            binding.registered = False
            binding.failure_reason = "This key cannot be used as a global hotkey."
            return False
        name, modifiers = parsed
        keycode = self._x.keycode_for(name)
        if keycode == 0:
            binding.registered = False
            binding.failure_reason = "This key is not on the current keyboard layout."
            return False
        for other_action, (code, mods) in self._grabs.items():
            if (code, mods) == (keycode, modifiers) and other_action != binding.action:
                binding.registered = False
                binding.failure_reason = "Already used by another capture hotkey."
                return False
        if not self._x.grab_key(keycode, modifiers):
            binding.registered = False
            binding.failure_reason = "In use by another application"
            return False
        self._grabs[binding.action] = (keycode, modifiers)
        binding.registered = True
        binding.failure_reason = None
        return True

    def unregister(self, binding: HotkeyBinding) -> None:
        grab = self._grabs.pop(binding.action, None)
        if grab is not None:
            self._x.ungrab_key(*grab)
        binding.registered = False

    def unregister_all(self) -> None:
        for keycode, modifiers in self._grabs.values():
            self._x.ungrab_key(keycode, modifiers)
        self._grabs.clear()

    def _on_readable(self) -> None:
        for keycode, state in self._x.pending_key_presses():
            for action, (code, mods) in self._grabs.items():
                if code == keycode and mods == state:
                    self.triggered.emit(action)
                    break


def is_x11_session() -> bool:
    app = QGuiApplication.instance()
    platform = QGuiApplication.platformName().lower() if app is not None else ""
    return platform == "xcb"


def create_backends() -> tuple[CaptureBackend, HotkeyBackend]:
    """Activate on an X11 session only; raises OSError otherwise (PRD 6.2)."""
    if not is_x11_session():
        raise OSError("not an X11 session")
    connection = X11Connection()
    return X11CaptureBackend(connection), X11HotkeyBackend(connection)
