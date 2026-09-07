"""CaptureManager: the coordinator between entry points, backends, and the editor.

Implements PRD Sections 2 (modes), 3.1 (hotkeys), 3.5 (single instance),
3.6 (hide and restore), 4 (options), and 7.4 (failure). The editor connects
``capture_completed`` and ``capture_failed``; that is the whole contract.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Protocol

from PyQt6.QtCore import QObject, QRect, QTimer, pyqtBoundSignal, pyqtSignal
from PyQt6.QtGui import QCursor, QImage, QKeySequence
from PyQt6.QtWidgets import QApplication

from snapmock.capture.backend import (
    UNSUPPORTED_PLATFORM_MESSAGE,
    CaptureBackend,
    CaptureCancelledError,
    CaptureError,
    HotkeyBackend,
)
from snapmock.capture.cli import CaptureCommand
from snapmock.capture.compositing import (
    composite_cursor,
    max_ratio,
    monitor_region,
    physical_rect_for,
    render_region,
)
from snapmock.capture.countdown import CountdownBadge
from snapmock.capture.models import (
    HOTKEY_ACTIONS,
    ORIGIN_COMMAND_LINE,
    ORIGIN_HOTKEY,
    BackendCapabilities,
    CaptureMetadata,
    CaptureMode,
    CaptureRequest,
    CaptureResult,
    FullScreenScope,
    HotkeyBinding,
    PermissionState,
    ScreenGrab,
)
from snapmock.capture.overlay import make_overlay
from snapmock.capture.single_instance import SingleInstanceChannel
from snapmock.capture.sound import play_shutter
from snapmock.capture.window_state import WindowHider
from snapmock.config.settings import AppSettings

log = logging.getLogger("snapmock.capture")

MSG_BUSY = "A capture is already in progress."
MSG_MODAL = "Close the open dialog before capturing."
MSG_NO_WINDOW = "No active window found"
MSG_WINDOW_DEGRADED = (
    "Active window capture is not available on this desktop. Draw the region instead."
)
MSG_OVERLAY_ERROR = "The capture overlay encountered an error"
MSG_PERMISSION = "Screen capture permission has not been granted."

HIDE_WAIT_MS = 250
HIDE_POLL_MS = 16
HIDE_SETTLE_MS = 35
BADGE_LEAD_MS = 100


class RegionSelector(Protocol):
    """What the manager needs from the region overlay (PRD 5)."""

    region_selected: pyqtBoundSignal
    cancelled: pyqtBoundSignal
    failed: pyqtBoundSignal

    def show_selection(self, grab: ScreenGrab, *, hint: str, show_magnifier: bool) -> None: ...

    def hide_selection(self) -> None: ...

    def destroy(self) -> None: ...


class CaptureState(Enum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    HIDING = "hiding"
    GRABBING = "grabbing"
    SELECTING = "selecting"


def current_platform() -> str:
    """``linux``, ``darwin`` or ``win32`` (PRD 10.5)."""
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("win"):
        return "win32"
    return sys.platform


class CaptureManager(QObject):
    """Owns one capture backend, one hotkey backend, the overlay, the delay
    timer, and the single-instance channel (PRD 6.1).

    Signals
    -------
    capture_completed(object)
        A :class:`CaptureResult`; the editor hands its image to the Library.
    capture_failed(str)
        A user-readable reason. No file was created.
    capture_cancelled()
        The user cancelled (Escape, right-click, focus loss, countdown cancel).
    capture_refused(str, str)
        A request was not started: busy, modal dialog open, or unsupported.
        Carries the reason and the request origin (PRD 3.6).
    countdown_tick(int)
        Seconds remaining in a delay; 0 when the countdown ends.
    state_changed(str)
    hotkeys_changed()
        Registration results changed; Preferences and menus refresh.
    """

    capture_completed = pyqtSignal(object)
    capture_failed = pyqtSignal(str)
    capture_cancelled = pyqtSignal()
    capture_refused = pyqtSignal(str, str)
    countdown_tick = pyqtSignal(int)
    state_changed = pyqtSignal(str)
    hotkeys_changed = pyqtSignal()

    def __init__(
        self,
        backend: CaptureBackend,
        hotkey_backend: HotkeyBackend,
        settings: AppSettings | None = None,
        *,
        overlay_factory: Callable[[], RegionSelector] | None = None,
        sound_player: Callable[[], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend
        self._hotkeys = hotkey_backend
        self._hotkeys.setParent(self)
        self._settings = settings or AppSettings()
        self._overlay_factory: Callable[[], RegionSelector] = overlay_factory or make_overlay
        self._overlay: RegionSelector | None = None
        self._sound_player = sound_player or play_shutter
        self._capabilities = backend.capabilities()
        self._state = CaptureState.IDLE
        self._request: CaptureRequest | None = None
        self._grab: ScreenGrab | None = None
        self._hider = WindowHider()
        self._badge: CountdownBadge | None = None
        self._remaining = 0
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)
        self._hide_timer = QTimer(self)
        self._hide_timer.setInterval(HIDE_POLL_MS)
        self._hide_timer.timeout.connect(self._poll_hidden)
        self._hide_elapsed = 0
        self._bindings: dict[str, HotkeyBinding] = {}
        self._channel: SingleInstanceChannel | None = None
        self._onboarding_gate: Callable[[CaptureRequest], bool] | None = None
        self._hotkeys.triggered.connect(self._on_hotkey)
        self._load_bindings()
        log.info("Capture backend: %s; hotkey backend: %s", backend.name, hotkey_backend.name)

    # --- facts ---

    @property
    def backend(self) -> CaptureBackend:
        return self._backend

    @property
    def hotkey_backend(self) -> HotkeyBackend:
        return self._hotkeys

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def state(self) -> CaptureState:
        return self._state

    @property
    def is_busy(self) -> bool:
        return self._state is not CaptureState.IDLE

    @property
    def platform(self) -> str:
        return current_platform()

    def capability_summary(self) -> str:
        """The read-only diagnostic line for Preferences (PRD 8.1)."""
        caps = self._capabilities
        names = {
            "x11": "X11",
            "wayland_portal": "Wayland portal",
            "macos": "macOS",
            "windows": "Windows",
            "null": "none",
            "fake": "fake",
        }
        parts = [f"Backend: {names.get(self._backend.name, self._backend.name)}."]
        if not caps.any_capture:
            parts.append("Screen capture: not supported on this platform.")
        if caps.needs_permission and self._backend.request_permission() is not (
            PermissionState.GRANTED
        ):
            parts.append("Screen Recording permission: not granted.")
        if not caps.active_window:
            parts.append("Active window: not available.")
        if not caps.cursor:
            parts.append("Cursor: not available.")
        if not self._hotkeys.supported:
            parts.append("Global hotkeys: bind a desktop shortcut.")
        return " ".join(parts)

    def set_onboarding_gate(self, gate: Callable[[CaptureRequest], bool] | None) -> None:
        """A callable run before the first grab; returning False cancels the request."""
        self._onboarding_gate = gate

    # --- requests ---

    def request_from_settings(
        self, mode: CaptureMode | None = None, origin: str = "menu", delay: int | None = None
    ) -> CaptureRequest:
        """Build a request from the preferences at request time (PRD 10.2)."""
        s = self._settings
        return CaptureRequest(
            mode=mode or CaptureMode.from_string(s.capture_default_mode()),
            delay_seconds=s.capture_delay_seconds() if delay is None else max(0, min(60, delay)),
            include_cursor=s.capture_include_cursor(),
            copy_to_clipboard=s.capture_copy_to_clipboard(),
            hide_window=s.capture_hide_window(),
            origin=origin,
        )

    def start(self, request: CaptureRequest) -> bool:
        """Start a capture. Returns False (and emits ``capture_refused``) when not started."""
        if self.is_busy:
            self.capture_refused.emit(MSG_BUSY, request.origin)
            return False
        if QApplication.activeModalWidget() is not None:
            self.capture_refused.emit(MSG_MODAL, request.origin)
            return False
        if not self._capabilities.any_capture:
            self.capture_refused.emit(UNSUPPORTED_PLATFORM_MESSAGE, request.origin)
            return False
        if self._onboarding_gate is not None and not self._onboarding_gate(request):
            return False
        self._request = request
        log.info("Capture requested: mode=%s origin=%s", request.mode.value, request.origin)
        if request.delay_seconds > 0:
            self._begin_countdown(request.delay_seconds)
        else:
            self._begin_hide()
        return True

    def start_from_command(self, command: CaptureCommand) -> bool:
        mode = CaptureMode.from_string(command.mode) if command.mode else None
        return self.start(
            self.request_from_settings(mode, ORIGIN_COMMAND_LINE, delay=command.delay_seconds)
        )

    def cancel(self) -> None:
        """Cancel whatever is in progress; restores windows if they were hidden."""
        if not self.is_busy:
            return
        if self._overlay is not None and self._state is CaptureState.SELECTING:
            self._overlay.hide_selection()
        self._finish_cancelled()

    # --- countdown (PRD 4.1) ---

    def _begin_countdown(self, seconds: int) -> None:
        self._set_state(CaptureState.COUNTDOWN)
        self._remaining = seconds
        badge = self._ensure_badge()
        monitor_rect = self._monitor_rect_under_cursor()
        if monitor_rect is not None:
            badge.place_on(monitor_rect)
        badge.set_remaining(seconds)
        badge.show()
        badge.raise_()
        badge.setFocus()
        self.countdown_tick.emit(seconds)
        self._tick_timer.start()

    def _ensure_badge(self) -> CountdownBadge:
        if self._badge is None:
            self._badge = CountdownBadge()
            self._badge.cancel_requested.connect(self._on_countdown_cancel)
        return self._badge

    def _monitor_rect_under_cursor(self) -> QRect | None:
        pos = QCursor.pos()
        for m in self._backend.monitors():
            if m.logical_geometry.contains(pos):
                return m.logical_geometry
        return None

    def _on_tick(self) -> None:
        self._remaining -= 1
        self.countdown_tick.emit(max(0, self._remaining))
        if self._badge is not None:
            self._badge.set_remaining(self._remaining)
        if self._remaining <= 1:
            self._tick_timer.stop()
            # Hide the badge 100 ms before the grab so it is not captured.
            lead = max(0, 1000 - BADGE_LEAD_MS) if self._remaining == 1 else 0
            QTimer.singleShot(lead, self._hide_badge_then_grab)

    def _hide_badge_then_grab(self) -> None:
        if self._state is not CaptureState.COUNTDOWN:
            return
        if self._badge is not None:
            self._badge.hide()
        QTimer.singleShot(BADGE_LEAD_MS, self._begin_hide)

    def _on_countdown_cancel(self) -> None:
        if self._state is CaptureState.COUNTDOWN:
            self._tick_timer.stop()
            self._finish_cancelled()

    # --- hide and grab (PRD 3.6) ---

    def _begin_hide(self) -> None:
        if self._request is None or self._state not in (
            CaptureState.IDLE,
            CaptureState.COUNTDOWN,
        ):
            return
        self._set_state(CaptureState.HIDING)
        if self._request.hide_window:
            self._hider.hide_all()
            self._hide_elapsed = 0
            self._hide_timer.start()
        else:
            self._grab_now()

    def _poll_hidden(self) -> None:
        self._hide_elapsed += HIDE_POLL_MS
        if not self._hider.any_exposed() or self._hide_elapsed >= HIDE_WAIT_MS:
            self._hide_timer.stop()
            QTimer.singleShot(HIDE_SETTLE_MS, self._grab_now)

    def _grab_now(self) -> None:
        request = self._request
        if request is None or self._state is not CaptureState.HIDING:
            return
        self._set_state(CaptureState.GRABBING)
        try:
            if self._capabilities.needs_permission:
                if self._backend.request_permission() is PermissionState.DENIED:
                    raise CaptureError(
                        getattr(self._backend, "permission_message", MSG_PERMISSION)
                    )
            want_cursor = request.include_cursor and self._capabilities.cursor
            grab = self._backend.grab_screens(want_cursor)
        except CaptureCancelledError:
            self._finish_cancelled()
            return
        except CaptureError as e:
            self._finish_failed(str(e), e)
            return
        except Exception as e:  # noqa: BLE001 - a backend bug must not leave windows hidden
            self._finish_failed("The screen could not be captured.", e)
            return
        if want_cursor:
            composite_cursor(grab)
        self._grab = grab
        if request.mode is CaptureMode.FULL_SCREEN:
            self._complete_full_screen(grab)
        elif request.mode is CaptureMode.ACTIVE_WINDOW:
            self._complete_active_window(grab)
        else:
            self._begin_region(grab, hint="")

    # --- full screen (PRD 2.2, 4.4) ---

    def _complete_full_screen(self, grab: ScreenGrab) -> None:
        scope = FullScreenScope.from_string(self._settings.capture_full_screen_scope())
        cursor_pos = grab.cursor_position or QCursor.pos()
        monitor = (
            grab.monitor_at(cursor_pos) if scope is FullScreenScope.MONITOR_UNDER_CURSOR else None
        )
        if scope is FullScreenScope.MONITOR_UNDER_CURSOR and monitor is None:
            monitor = next((m for m in grab.monitors if m.is_primary), None) or (
                grab.monitors[0] if grab.monitors else None
            )
        if monitor is not None:
            image = monitor_region(grab, monitor)
            self._finish_completed(
                image,
                monitor_name=monitor.name,
                ratio=monitor.device_pixel_ratio,
                screen_rect=monitor.physical_geometry,
            )
            return
        ratio = max_ratio(grab.monitors)
        logical = grab.virtual_logical_rect
        image = render_region(grab, logical, ratio)
        self._finish_completed(
            image, monitor_name=None, ratio=ratio, screen_rect=physical_rect_for(logical, ratio)
        )

    # --- active window (PRD 2.3) ---

    def _complete_active_window(self, grab: ScreenGrab) -> None:
        if not self._capabilities.active_window:
            self._begin_region(grab, hint=MSG_WINDOW_DEGRADED)
            return
        geometry = self._backend.active_window_geometry()
        if geometry is None or geometry.isEmpty():
            self._finish_failed(MSG_NO_WINDOW)
            return
        geometry = geometry.intersected(grab.virtual_logical_rect)
        if geometry.isEmpty():
            self._finish_failed(MSG_NO_WINDOW)
            return
        # Captured from the monitor holding most of the window; spans use that ratio.
        best = max(
            grab.monitors,
            key=lambda m: _area(m.logical_geometry.intersected(geometry)),
            default=None,
        )
        ratio = best.device_pixel_ratio if best is not None else 1.0
        image = render_region(grab, geometry, ratio)
        self._finish_completed(
            image,
            monitor_name=best.name if best is not None else None,
            ratio=ratio,
            screen_rect=physical_rect_for(geometry, ratio),
            window_title=self._backend.active_window_title(),
        )

    # --- region (PRD 2.4, 5) ---

    def _begin_region(self, grab: ScreenGrab, *, hint: str) -> None:
        overlay = self._ensure_overlay()
        if overlay is None:
            self._finish_failed("Region capture is not available.")
            return
        self._set_state(CaptureState.SELECTING)
        try:
            overlay.show_selection(
                grab, hint=hint, show_magnifier=self._settings.capture_show_magnifier()
            )
        except Exception as e:  # noqa: BLE001 - overlay fault isolation (PRD 7.4)
            self._on_overlay_failed(MSG_OVERLAY_ERROR, e)

    def _ensure_overlay(self) -> RegionSelector | None:
        if self._overlay is None:
            overlay = self._overlay_factory()
            overlay.region_selected.connect(self._on_region_selected)
            overlay.cancelled.connect(self._on_region_cancelled)
            overlay.failed.connect(self._on_overlay_failed)
            self._overlay = overlay
        return self._overlay

    def _on_region_selected(self, logical_rect: QRect, monitor_name: str) -> None:
        grab = self._grab
        if grab is None or self._state is not CaptureState.SELECTING:
            return
        monitor = grab.monitor_by_name(monitor_name) or grab.monitor_at(logical_rect.center())
        ratio = monitor.device_pixel_ratio if monitor is not None else max_ratio(grab.monitors)
        image = render_region(grab, logical_rect, ratio)
        self._finish_completed(
            image,
            monitor_name=monitor.name if monitor is not None else None,
            ratio=ratio,
            screen_rect=physical_rect_for(logical_rect, ratio),
        )

    def _on_region_cancelled(self) -> None:
        if self._state is CaptureState.SELECTING:
            self._finish_cancelled()

    def _on_overlay_failed(self, reason: str, error: BaseException | None = None) -> None:
        overlay, self._overlay = self._overlay, None
        if overlay is not None:
            try:
                overlay.destroy()
            except Exception:  # noqa: BLE001
                pass
        if self.is_busy:
            self._finish_failed(reason or MSG_OVERLAY_ERROR, error)

    # --- finishing: one restore path (PRD 3.6) ---

    def _finish_completed(
        self,
        image: QImage,
        *,
        monitor_name: str | None,
        ratio: float,
        screen_rect: QRect,
        window_title: str | None = None,
    ) -> None:
        request, grab = self._request, self._grab
        if request is None or grab is None:
            self._finish_cancelled()
            return
        used_mode = request.mode
        if (
            request.mode is CaptureMode.ACTIVE_WINDOW
            and window_title is None
            and (not self._capabilities.active_window)
        ):
            used_mode = CaptureMode.REGION
        metadata = CaptureMetadata(
            mode=used_mode,
            requested_mode=request.mode,
            monitor_name=monitor_name,
            device_pixel_ratio=ratio,
            screen_rect=screen_rect,
            cursor_included=grab.cursor_image is not None,
            platform=self.platform,
            backend=self._backend.name,
            window_title=window_title,
        )
        result = CaptureResult(image=image, metadata=metadata, taken_at=grab.taken_at)
        if request.copy_to_clipboard:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setImage(image)
        if self._settings.capture_play_sound():
            self._sound_player()
        self._settings.set_capture_last_mode(used_mode.value)
        log.info(
            "Capture completed: mode=%s size=%dx%d monitor=%s",
            used_mode.value,
            image.width(),
            image.height(),
            monitor_name,
        )
        self._reset()
        # Handoff before restore, so the new tab exists when the window reappears (PRD 7.1).
        self.capture_completed.emit(result)
        self._hider.restore()

    def _finish_cancelled(self) -> None:
        if self._badge is not None:
            self._badge.hide()
        self._reset()
        self.capture_cancelled.emit()
        self._hider.restore()

    def _finish_failed(self, reason: str, error: BaseException | None = None) -> None:
        request = self._request
        log.error(
            "Capture failed: platform=%s backend=%s mode=%s reason=%s error=%r",
            self.platform,
            self._backend.name,
            request.mode.value if request else None,
            reason,
            error,
        )
        if self._badge is not None:
            self._badge.hide()
        self._reset()
        self.capture_failed.emit(reason)
        self._hider.restore()

    def _reset(self) -> None:
        self._tick_timer.stop()
        self._hide_timer.stop()
        self._request = None
        self._grab = None
        self._set_state(CaptureState.IDLE)

    def _set_state(self, state: CaptureState) -> None:
        if state is not self._state:
            self._state = state
            self.state_changed.emit(state.value)

    # --- hotkeys (PRD 3.1, 6.7, 9.3) ---

    @property
    def bindings(self) -> list[HotkeyBinding]:
        return list(self._bindings.values())

    def binding(self, action: str) -> HotkeyBinding | None:
        return self._bindings.get(action)

    def _load_bindings(self) -> None:
        for action in HOTKEY_ACTIONS:
            self._bindings[action] = HotkeyBinding(
                action, QKeySequence(self._settings.capture_hotkey(action))
            )

    def register_hotkeys(self) -> list[HotkeyBinding]:
        """Register every bound hotkey; returns the bindings that failed."""
        failed: list[HotkeyBinding] = []
        for binding in self._bindings.values():
            if not binding.is_bound:
                continue
            if not self._hotkeys.register(binding):
                failed.append(binding)
        self.hotkeys_changed.emit()
        return failed

    def unregister_hotkeys(self) -> None:
        for binding in self._bindings.values():
            if binding.registered:
                self._hotkeys.unregister(binding)
        self._hotkeys.unregister_all()
        self.hotkeys_changed.emit()

    def set_hotkey(self, action: str, key_text: str) -> bool:
        """Change one hotkey: release the old key, register the new one.

        On failure the previous key stays registered and False is returned.
        """
        binding = self._bindings.get(action)
        if binding is None:
            return False
        new_seq = QKeySequence(key_text, QKeySequence.SequenceFormat.PortableText)
        if new_seq.toString(QKeySequence.SequenceFormat.PortableText) == binding.key_text:
            return True
        old_seq, was_registered = binding.key_sequence, binding.registered
        if was_registered:
            self._hotkeys.unregister(binding)
        binding.key_sequence = new_seq
        ok = True
        if new_seq.isEmpty():
            binding.registered = False
            binding.failure_reason = None
        elif self._hotkeys.supported:
            ok = self._hotkeys.register(binding)
            if not ok:
                binding.key_sequence = old_seq
                if was_registered:
                    self._hotkeys.register(binding)
                self.hotkeys_changed.emit()
                return False
        self._settings.set_capture_hotkey(action, binding.key_text)
        self.hotkeys_changed.emit()
        return ok

    def _on_hotkey(self, action: str) -> None:
        mode = HOTKEY_ACTIONS.get(action)
        if mode is None:
            return
        if self.is_busy:
            return  # one capture at a time; hotkeys are ignored while busy (PRD 3.1)
        self.start(self.request_from_settings(mode, ORIGIN_HOTKEY))

    # --- single instance (PRD 3.5) ---

    @property
    def channel(self) -> SingleInstanceChannel | None:
        return self._channel

    def listen_for_commands(self, name: str | None = None) -> bool:
        """Become the running instance on the single-instance channel."""
        channel = SingleInstanceChannel(name, parent=self)
        if not channel.listen():
            return False
        channel.command_received.connect(self._on_command_line)
        self._channel = channel
        return True

    def _on_command_line(self, argv: list[str]) -> None:
        from snapmock.capture.cli import parse_capture_args

        command = parse_capture_args(argv)
        if command is not None:
            self.start_from_command(command)

    def shutdown(self) -> None:
        """Release hotkeys and the channel; called when the application quits."""
        self.cancel()
        self.unregister_hotkeys()
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        if self._overlay is not None:
            self._overlay.destroy()
            self._overlay = None
        if self._badge is not None:
            self._badge.deleteLater()
            self._badge = None

    @property
    def taken_at(self) -> datetime | None:
        return self._grab.taken_at if self._grab else None


def _area(rect: QRect) -> int:
    return max(0, rect.width()) * max(0, rect.height())
