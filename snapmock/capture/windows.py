"""Windows backend and Windows hotkey backend through ctypes (PRD 6.6, 6.7).

This module imports on every platform. Nothing touches ``user32``, ``gdi32``
or ``dwmapi`` until :func:`create_backends` runs, and that raises
:class:`OSError` off Windows. The screen grab itself is Qt's (see
:class:`QtScreenGrabBackend`, which uses a GDI bit-block transfer underneath);
ctypes supplies what Qt does not expose: the frame bounds that exclude the
invisible resize border, the cursor bitmap, and ``RegisterHotKey``.

The Win32 types are spelled out with plain :mod:`ctypes` rather than taken
from ``ctypes.wintypes``, so that importing this module costs nothing and
cannot fail on Linux or macOS, where the test suite still imports it.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Callable
from ctypes import POINTER, Structure, byref, c_int, c_size_t, c_ssize_t, c_ubyte, c_void_p

from PyQt6 import sip
from PyQt6.QtCore import QAbstractNativeEventFilter, QByteArray, QObject, QPoint, QRect, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QKeySequence

from snapmock.capture.backend import (
    CaptureBackend,
    HotkeyBackend,
    QtScreenGrabBackend,
    physical_to_logical,
)
from snapmock.capture.models import BackendCapabilities, HotkeyBinding

log = logging.getLogger("snapmock.capture")

# --- Win32 scalar types (see the module docstring) ---

BOOL = c_int
DWORD = ctypes.c_uint32
LONG = ctypes.c_int32
WORD = ctypes.c_uint16
UINT = ctypes.c_uint32
HANDLE = c_void_p
WPARAM = c_size_t
LPARAM = c_ssize_t

# --- Win32 constants ---

CURSOR_SHOWING = 0x0001
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_TRANSITIONS_FORCEDISABLED = 3
DIB_RGB_COLORS = 0
BI_RGB = 0
WM_HOTKEY = 0x0312
HWND_MESSAGE = -3
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
#: The event types whose native message really is an MSG. Qt passes other
#: kinds of pointer for other event types, and casting those would fault.
WINDOWS_MSG_EVENT_TYPES = frozenset({b"windows_generic_MSG", b"windows_dispatcher_MSG"})
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

#: Window classes that are the shell rather than a capturable window (PRD 6.6).
SHELL_WINDOW_CLASSES = frozenset(
    {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "TaskListThumbnailWnd"}
)

# Failure reasons. The wording matches the X11 backend and the fake so the
# Preferences editor shows one phrasing everywhere (PRD 8.1, 9.3).
UNMAPPABLE_KEY = "This key cannot be used as a global hotkey."
DUPLICATE_KEY = "Already used by another capture hotkey."
KEY_IN_USE = "In use by another application"


class POINT(Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class RECT(Structure):
    _fields_ = [("left", LONG), ("top", LONG), ("right", LONG), ("bottom", LONG)]


class CURSORINFO(Structure):
    _fields_ = [("cbSize", DWORD), ("flags", DWORD), ("hCursor", HANDLE), ("ptScreenPos", POINT)]


class ICONINFO(Structure):
    _fields_ = [
        ("fIcon", BOOL),
        ("xHotspot", DWORD),
        ("yHotspot", DWORD),
        ("hbmMask", HANDLE),
        ("hbmColor", HANDLE),
    ]


class BITMAP(Structure):
    _fields_ = [
        ("bmType", LONG),
        ("bmWidth", LONG),
        ("bmHeight", LONG),
        ("bmWidthBytes", LONG),
        ("bmPlanes", WORD),
        ("bmBitsPixel", WORD),
        ("bmBits", c_void_p),
    ]


class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", LONG),
        ("biHeight", LONG),
        ("biPlanes", WORD),
        ("biBitCount", WORD),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]


class BITMAPINFO(Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", DWORD * 3)]


class MSG(Structure):
    _fields_ = [
        ("hwnd", HANDLE),
        ("message", UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", DWORD),
        ("pt", POINT),
    ]


class Win32:
    """The user32, gdi32 and dwmapi entry points this backend needs.

    Constructing this is the first thing that touches Windows, so every call
    below is reachable only from :func:`create_backends` and what it returns.
    """

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("not a Windows session")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        self.dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        self._bind()

    def _bind(self) -> None:
        u, g, d = self.user32, self.gdi32, self.dwmapi
        u.GetForegroundWindow.restype = HANDLE
        u.GetWindowRect.argtypes = [HANDLE, POINTER(RECT)]
        u.GetWindowRect.restype = BOOL
        u.GetWindowTextLengthW.argtypes = [HANDLE]
        u.GetWindowTextLengthW.restype = c_int
        u.GetWindowTextW.argtypes = [HANDLE, c_void_p, c_int]
        u.GetWindowTextW.restype = c_int
        u.GetClassNameW.argtypes = [HANDLE, c_void_p, c_int]
        u.GetClassNameW.restype = c_int
        u.GetCursorInfo.argtypes = [POINTER(CURSORINFO)]
        u.GetCursorInfo.restype = BOOL
        u.GetIconInfo.argtypes = [HANDLE, POINTER(ICONINFO)]
        u.GetIconInfo.restype = BOOL
        u.GetDC.argtypes = [HANDLE]
        u.GetDC.restype = HANDLE
        u.ReleaseDC.argtypes = [HANDLE, HANDLE]
        u.ReleaseDC.restype = c_int
        u.CreateWindowExW.argtypes = [
            DWORD,
            c_void_p,
            c_void_p,
            DWORD,
            c_int,
            c_int,
            c_int,
            c_int,
            HANDLE,
            HANDLE,
            HANDLE,
            c_void_p,
        ]
        u.CreateWindowExW.restype = HANDLE
        u.DestroyWindow.argtypes = [HANDLE]
        u.DestroyWindow.restype = BOOL
        u.RegisterHotKey.argtypes = [HANDLE, c_int, UINT, UINT]
        u.RegisterHotKey.restype = BOOL
        u.UnregisterHotKey.argtypes = [HANDLE, c_int]
        u.UnregisterHotKey.restype = BOOL
        u.GetThreadDpiAwarenessContext.restype = c_void_p
        u.AreDpiAwarenessContextsEqual.argtypes = [c_void_p, c_void_p]
        u.AreDpiAwarenessContextsEqual.restype = BOOL
        g.GetObjectW.argtypes = [HANDLE, c_int, c_void_p]
        g.GetObjectW.restype = c_int
        g.GetDIBits.argtypes = [HANDLE, HANDLE, UINT, UINT, c_void_p, POINTER(BITMAPINFO), UINT]
        g.GetDIBits.restype = c_int
        g.DeleteObject.argtypes = [HANDLE]
        g.DeleteObject.restype = BOOL
        d.DwmGetWindowAttribute.argtypes = [HANDLE, DWORD, c_void_p, DWORD]
        d.DwmGetWindowAttribute.restype = ctypes.c_long
        d.DwmSetWindowAttribute.argtypes = [HANDLE, DWORD, c_void_p, DWORD]
        d.DwmSetWindowAttribute.restype = ctypes.c_long

    # --- DPI (PRD 6.6) ---

    def per_monitor_dpi_aware_v2(self) -> bool:
        """Whether this thread already has per-monitor DPI awareness version 2."""
        try:
            context = self.user32.GetThreadDpiAwarenessContext()
            return bool(
                self.user32.AreDpiAwarenessContextsEqual(
                    c_void_p(context), c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
                )
            )
        except (AttributeError, OSError):  # pragma: no cover - Windows before 1607
            return False

    # --- windows ---

    def foreground_window(self) -> int | None:
        hwnd = self.user32.GetForegroundWindow()
        return int(hwnd) if hwnd else None

    def window_class(self, hwnd: int) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        length = self.user32.GetClassNameW(HANDLE(hwnd), buffer, 256)
        return buffer.value if length > 0 else ""

    def window_title(self, hwnd: int) -> str | None:
        length = self.user32.GetWindowTextLengthW(HANDLE(hwnd))
        if length <= 0:
            return None
        buffer = ctypes.create_unicode_buffer(length + 1)
        if self.user32.GetWindowTextW(HANDLE(hwnd), buffer, length + 1) <= 0:
            return None
        return buffer.value or None

    def window_frame_rect(self, hwnd: int) -> QRect | None:
        """The visible frame in virtual-desktop physical pixels (PRD 6.6, 14.5).

        ``DWMWA_EXTENDED_FRAME_BOUNDS`` excludes the invisible resize border
        Windows draws around a window; ``GetWindowRect`` includes it and is
        only the fallback for when DWM reports an error.
        """
        rect = RECT()
        status = self.dwmapi.DwmGetWindowAttribute(
            HANDLE(hwnd),
            DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
            byref(rect),
            DWORD(ctypes.sizeof(rect)),
        )
        if status != 0:
            log.debug("DwmGetWindowAttribute failed (%d); using GetWindowRect", status)
            if not self.user32.GetWindowRect(HANDLE(hwnd), byref(rect)):
                return None
        result = QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        return result if result.isValid() and not result.isEmpty() else None

    # --- cursor (PRD 6.6) ---

    def cursor_image(self) -> tuple[QImage, QPoint] | None:
        """The visible cursor bitmap with alpha, and its hotspot in its own pixels."""
        info = CURSORINFO()
        info.cbSize = ctypes.sizeof(CURSORINFO)
        if not self.user32.GetCursorInfo(byref(info)):
            return None
        if not (info.flags & CURSOR_SHOWING) or not info.hCursor:
            return None
        icon = ICONINFO()
        if not self.user32.GetIconInfo(HANDLE(info.hCursor), byref(icon)):
            return None
        try:
            return self._icon_to_image(icon)
        finally:  # every handle GetIconInfo hands out is ours to release
            for handle in (icon.hbmMask, icon.hbmColor):
                if handle:
                    self.gdi32.DeleteObject(HANDLE(handle))

    def _icon_to_image(self, icon: ICONINFO) -> tuple[QImage, QPoint] | None:
        bitmap = BITMAP()
        if not self.gdi32.GetObjectW(HANDLE(icon.hbmMask), ctypes.sizeof(BITMAP), byref(bitmap)):
            return None
        width, mask_height = int(bitmap.bmWidth), int(bitmap.bmHeight)
        if width <= 0 or mask_height <= 0:
            return None
        hotspot = QPoint(int(icon.xHotspot), int(icon.yHotspot))
        if icon.hbmColor:
            image = self._colour_cursor(icon, width, mask_height)
        else:
            # A monochrome cursor has no colour bitmap: its mask is double
            # height, the upper half the AND mask and the lower half the XOR
            # mask. This is how the I-beam arrives.
            image = self._monochrome_cursor(icon, width, mask_height // 2)
        return (image, hotspot) if image is not None else None

    def _colour_cursor(self, icon: ICONINFO, width: int, height: int) -> QImage | None:
        colour = self._bitmap_pixels(icon.hbmColor, width, height)
        if colour is None:
            return None
        image = _image_from_bgra(colour, width, height)
        if _has_alpha(image):
            return image
        # A colour bitmap that carries no alpha is masked instead: where the
        # AND mask is white the pixel is transparent.
        mask = self._bitmap_pixels(icon.hbmMask, width, height)
        if mask is not None:
            _apply_and_mask(image, mask)
        return image

    def _monochrome_cursor(self, icon: ICONINFO, width: int, height: int) -> QImage | None:
        if height <= 0:
            return None
        both = self._bitmap_pixels(icon.hbmMask, width, height * 2)
        if both is None:
            return None
        stride = width * 4
        and_mask = both[: stride * height]
        xor_mask = both[stride * height :]
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(0)
        for y in range(height):
            row = y * stride
            for x in range(width):
                i = row + x * 4
                if and_mask[i] != 0:  # white in the AND mask means transparent
                    continue
                image.setPixel(x, y, 0xFFFFFFFF if xor_mask[i] else 0xFF000000)
        return image

    def _bitmap_pixels(self, hbitmap: int, width: int, height: int) -> bytes | None:
        """*height* rows of top-down 32-bit BGRA for a GDI bitmap."""
        hdc = self.user32.GetDC(None)
        if not hdc:
            return None
        try:
            info = BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.bmiHeader.biWidth = width
            info.bmiHeader.biHeight = -height  # negative: top-down rows
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = BI_RGB
            buffer = (c_ubyte * (width * height * 4))()
            copied = self.gdi32.GetDIBits(
                HANDLE(hdc), HANDLE(hbitmap), 0, height, buffer, byref(info), DIB_RGB_COLORS
            )
            return bytes(buffer) if copied else None
        finally:
            self.user32.ReleaseDC(None, HANDLE(hdc))


def _image_from_bgra(pixels: bytes, width: int, height: int) -> QImage:
    """A privately owned ARGB32 image from top-down BGRA bytes."""
    # Format_ARGB32 is 0xAARRGGBB, which on a little-endian machine is exactly
    # the BGRA byte order GetDIBits produces.
    image = QImage(pixels, width, height, width * 4, QImage.Format.Format_ARGB32)
    return image.copy()  # own the pixels: *pixels* is about to go out of scope


def _has_alpha(image: QImage) -> bool:
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixel(x, y) >> 24:
                return True
    return False


def _apply_and_mask(image: QImage, mask: bytes) -> None:
    stride = image.width() * 4
    for y in range(image.height()):
        row = y * stride
        for x in range(image.width()):
            opaque = mask[row + x * 4] == 0  # black in the AND mask means draw
            image.setPixel(x, y, (image.pixel(x, y) & 0x00FFFFFF) | (0xFF000000 if opaque else 0))


#: Windows whose close animation has already been turned off.
_TRANSITIONS_DISABLED: set[int] = set()


def disable_window_transitions(hwnd: int) -> bool:
    """Turn off the DWM open and close animation for *hwnd* (PRD 3.6).

    Windows fades a window out over roughly 150 ms after ``hide()``, and DWM
    keeps compositing it for the whole fade. ``QWindow.isExposed()`` goes false
    about 80 ms in, while the window is still almost fully on screen, so a grab
    taken once it reports unexposed catches the window half faded and the
    capture shows a ghost of SnapMock. With transitions disabled the window is
    gone in the frame after ``hide()``.
    """
    if sys.platform != "win32":
        return False
    if hwnd in _TRANSITIONS_DISABLED:
        return True
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        enabled = BOOL(1)
        status = dwmapi.DwmSetWindowAttribute(
            HANDLE(hwnd),
            DWORD(DWMWA_TRANSITIONS_FORCEDISABLED),
            byref(enabled),
            DWORD(ctypes.sizeof(enabled)),
        )
    except OSError as e:  # pragma: no cover - dwmapi is present on every supported Windows
        log.info("Could not disable window transitions: %s", e)
        return False
    if status != 0:
        log.info("DwmSetWindowAttribute refused for %d (0x%08X)", hwnd, status & 0xFFFFFFFF)
        return False
    _TRANSITIONS_DISABLED.add(hwnd)
    return True


# --- Qt key sequences to Windows virtual keys ---

_VIRTUAL_KEYS: dict[int, int] = {
    Qt.Key.Key_Print.value: 0x2C,  # VK_SNAPSHOT
    Qt.Key.Key_Space.value: 0x20,
    Qt.Key.Key_Escape.value: 0x1B,
    Qt.Key.Key_Tab.value: 0x09,
    Qt.Key.Key_Backspace.value: 0x08,
    Qt.Key.Key_Return.value: 0x0D,
    Qt.Key.Key_Enter.value: 0x0D,
    Qt.Key.Key_Insert.value: 0x2D,
    Qt.Key.Key_Delete.value: 0x2E,
    Qt.Key.Key_Pause.value: 0x13,
    Qt.Key.Key_Home.value: 0x24,
    Qt.Key.Key_End.value: 0x23,
    Qt.Key.Key_Left.value: 0x25,
    Qt.Key.Key_Up.value: 0x26,
    Qt.Key.Key_Right.value: 0x27,
    Qt.Key.Key_Down.value: 0x28,
    Qt.Key.Key_PageUp.value: 0x21,
    Qt.Key.Key_PageDown.value: 0x22,
    Qt.Key.Key_ScrollLock.value: 0x91,
    Qt.Key.Key_NumLock.value: 0x90,
    Qt.Key.Key_CapsLock.value: 0x14,
    Qt.Key.Key_Menu.value: 0x5D,  # VK_APPS
}


def virtual_key_for(key: Qt.Key) -> int | None:
    """The Windows virtual-key code for a Qt key, or None when there is none."""
    value = key.value
    if value in _VIRTUAL_KEYS:
        return _VIRTUAL_KEYS[value]
    if Qt.Key.Key_F1.value <= value <= Qt.Key.Key_F24.value:
        return 0x70 + (value - Qt.Key.Key_F1.value)  # VK_F1 to VK_F24
    if Qt.Key.Key_0.value <= value <= Qt.Key.Key_9.value:
        return value  # '0' to '9' share their ASCII codes with the virtual keys
    if Qt.Key.Key_A.value <= value <= Qt.Key.Key_Z.value:
        return value  # 'A' to 'Z' likewise
    return None


def windows_modifiers_for(modifiers: Qt.KeyboardModifier) -> int:
    mask = 0
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        mask |= MOD_SHIFT
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        mask |= MOD_CONTROL
    if modifiers & Qt.KeyboardModifier.AltModifier:
        mask |= MOD_ALT
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        mask |= MOD_WIN
    return mask


def parse_key_sequence(sequence: QKeySequence) -> tuple[int, int] | None:
    """(virtual key, modifier mask) for a single-key sequence, or None.

    A sequence with no modifier is accepted: the default Region hotkey is a
    bare Print Screen, and ``RegisterHotKey`` takes a zero modifier mask.
    """
    if sequence.isEmpty():
        return None
    combination = sequence[0]
    key = virtual_key_for(combination.key())
    if key is None:
        return None
    return key, windows_modifiers_for(combination.keyboardModifiers())


# --- backends ---


class WindowsCaptureBackend(QtScreenGrabBackend):
    """Qt's GDI grab, plus ctypes for the frame bounds and the cursor (PRD 6.6)."""

    name = "windows"

    def __init__(self, win32: Win32) -> None:
        self._win32 = win32

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            full_screen=True,
            active_window=True,
            region=True,
            cursor=True,
            hotkeys=True,
            tray=True,
            needs_permission=False,
        )

    def active_window_geometry(self) -> QRect | None:
        hwnd = self._capturable_foreground_window()
        if hwnd is None:
            return None
        physical = self._win32.window_frame_rect(hwnd)
        if physical is None:
            return None
        return physical_to_logical(physical)

    def active_window_title(self) -> str | None:
        hwnd = self._capturable_foreground_window()
        return self._win32.window_title(hwnd) if hwnd is not None else None

    def _capturable_foreground_window(self) -> int | None:
        """The foreground window unless it is ours or the shell (PRD 6.6).

        Returning None leaves the manager's own fallback to apply, as it does
        on X11.
        """
        hwnd = self._win32.foreground_window()
        if hwnd is None or self._is_our_own(hwnd):
            return None
        if self._win32.window_class(hwnd) in SHELL_WINDOW_CLASSES:
            return None
        return hwnd

    @staticmethod
    def _is_our_own(hwnd: int) -> bool:
        if QGuiApplication.instance() is None:
            return False
        return any(int(w.winId()) == hwnd for w in QGuiApplication.topLevelWindows())

    def _cursor_image(self) -> tuple[QImage, QPoint] | None:
        try:
            return self._win32.cursor_image()
        except (OSError, ValueError) as e:
            log.info("Cursor read failed: %s", e)
            return None


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    """Turns ``WM_HOTKEY`` into a call on the backend.

    This is a separate object rather than the backend itself because PyQt does
    not dispatch ``nativeEventFilter`` to a class that also inherits
    :class:`QObject`: the filter is simply never called. The backend needs a
    Qt signal, so it must be a QObject, and the two cannot be the same object.
    """

    def __init__(self, deliver: Callable[[int], None]) -> None:
        super().__init__()
        self._deliver = deliver

    def nativeEventFilter(
        self,
        eventType: QByteArray | bytes | bytearray | memoryview,  # noqa: N803 - Qt override
        message: sip.voidptr | None,
    ) -> tuple[bool, sip.voidptr | None]:
        """Report the hotkey identifier; the message is never consumed."""
        if message is None:
            return False, message
        kind = eventType.data() if isinstance(eventType, QByteArray) else bytes(eventType)
        if kind not in WINDOWS_MSG_EVENT_TYPES:
            return False, message
        msg = ctypes.cast(int(message), POINTER(MSG)).contents
        if msg.message == WM_HOTKEY:
            self._deliver(int(msg.wParam))
        return False, message


class WindowsHotkeyBackend(HotkeyBackend):
    """``RegisterHotKey`` on a message-only window, delivered on ``WM_HOTKEY`` (PRD 6.7)."""

    name = "windows"

    def __init__(self, win32: Win32, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._win32 = win32
        self._hwnd: int | None = None
        self._ids: dict[str, int] = {}  # action -> hotkey identifier
        self._keys: dict[str, tuple[int, int]] = {}  # action -> (virtual key, modifiers)
        self._next_id = 1
        self._filter = _HotkeyEventFilter(self._on_hotkey)
        self._filter_installed = False

    @property
    def supported(self) -> bool:
        return True

    def _on_hotkey(self, hotkey_id: int) -> None:
        for action, registered_id in self._ids.items():
            if registered_id == hotkey_id:
                self.triggered.emit(action)
                return

    def _ensure_window(self) -> int | None:
        """The message-only window that owns every registration.

        ``STATIC`` is borrowed as the window class so none of our own has to be
        registered; the window never draws and only holds the hotkeys.
        """
        if self._hwnd is not None:
            return self._hwnd
        hwnd = self._win32.user32.CreateWindowExW(
            0,
            ctypes.c_wchar_p("STATIC"),
            ctypes.c_wchar_p("SnapMockHotkeys"),
            0,
            0,
            0,
            0,
            0,
            HANDLE(HWND_MESSAGE),
            None,
            None,
            None,
        )
        if not hwnd:
            log.warning("Could not create the hotkey window: error %d", ctypes.get_last_error())
            return None
        self._hwnd = int(hwnd)
        app = QGuiApplication.instance()
        if app is not None and not self._filter_installed:
            app.installNativeEventFilter(self._filter)
            self._filter_installed = True
        return self._hwnd

    def register(self, binding: HotkeyBinding) -> bool:
        self.unregister(binding)
        parsed = parse_key_sequence(binding.key_sequence)
        if parsed is None:
            binding.registered = False
            binding.failure_reason = UNMAPPABLE_KEY
            return False
        key, modifiers = parsed
        for other, existing in self._keys.items():
            if existing == (key, modifiers) and other != binding.action:
                binding.registered = False
                binding.failure_reason = DUPLICATE_KEY
                return False
        hwnd = self._ensure_window()
        if hwnd is None:
            binding.registered = False
            binding.failure_reason = KEY_IN_USE
            return False
        hotkey_id = self._next_id
        ctypes.set_last_error(0)
        # MOD_NOREPEAT: holding the key fires once, not once per repeat.
        registered = self._win32.user32.RegisterHotKey(
            HANDLE(hwnd), hotkey_id, UINT(modifiers | MOD_NOREPEAT), UINT(key)
        )
        if not registered:
            error = ctypes.get_last_error()
            binding.registered = False
            binding.failure_reason = (
                KEY_IN_USE if error == ERROR_HOTKEY_ALREADY_REGISTERED else UNMAPPABLE_KEY
            )
            log.info("RegisterHotKey failed for %s: error %d", binding.key_text, error)
            return False
        self._next_id += 1
        self._ids[binding.action] = hotkey_id
        self._keys[binding.action] = (key, modifiers)
        binding.registered = True
        binding.failure_reason = None
        return True

    def unregister(self, binding: HotkeyBinding) -> None:
        hotkey_id = self._ids.pop(binding.action, None)
        self._keys.pop(binding.action, None)
        if hotkey_id is not None and self._hwnd is not None:
            self._win32.user32.UnregisterHotKey(HANDLE(self._hwnd), hotkey_id)
        binding.registered = False

    def unregister_all(self) -> None:
        if self._hwnd is not None:
            for hotkey_id in self._ids.values():
                self._win32.user32.UnregisterHotKey(HANDLE(self._hwnd), hotkey_id)
        self._ids.clear()
        self._keys.clear()

    def close(self) -> None:
        """Release every hotkey, drop the event filter, and destroy the window.

        Removing the filter matters: Qt keeps a bare pointer to it, and calling
        into a collected filter faults the process at shutdown.
        """
        self.unregister_all()
        app = QGuiApplication.instance()
        if app is not None and self._filter_installed:
            app.removeNativeEventFilter(self._filter)
        self._filter_installed = False
        if self._hwnd is not None:
            self._win32.user32.DestroyWindow(HANDLE(self._hwnd))
            self._hwnd = None


def create_backends() -> tuple[CaptureBackend, HotkeyBackend]:
    """Activate on Windows only; raises OSError elsewhere (PRD 6.2)."""
    win32 = Win32()
    # Qt sets per-monitor awareness version 2 while QGuiApplication starts, and
    # a second call would be refused, so this verifies rather than sets it.
    if win32.per_monitor_dpi_aware_v2():
        log.debug("Per-monitor DPI awareness v2 confirmed")
    else:  # pragma: no cover - Qt sets it on every supported Windows
        log.warning("Per-monitor DPI awareness v2 is not set; monitor scales may be wrong")
    return WindowsCaptureBackend(win32), WindowsHotkeyBackend(win32)
