"""Tests for CaptureManager against the fake backend (PRD 2, 3.1, 3.6, 4, 7.4)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PyQt6.QtCore import QObject, QPoint, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QKeySequence
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget
from pytestqt.qtbot import QtBot

from snapmock.capture.backend import FakeCaptureBackend, FakeHotkeyBackend, NullCaptureBackend
from snapmock.capture.manager import (
    MSG_BUSY,
    MSG_MODAL,
    MSG_NO_WINDOW,
    MSG_OVERLAY_ERROR,
    MSG_WINDOW_DEGRADED,
    CaptureManager,
    CaptureState,
)
from snapmock.capture.models import (
    HOTKEY_ACTION_FULL_SCREEN,
    HOTKEY_ACTION_REGION,
    ORIGIN_HOTKEY,
    BackendCapabilities,
    CaptureMode,
    CaptureRequest,
    CaptureResult,
    MonitorInfo,
    ScreenGrab,
)
from snapmock.capture.window_state import WindowHider
from snapmock.config.settings import AppSettings


class FakeOverlay(QObject):
    """A region selector the tests drive by hand."""

    region_selected = pyqtSignal(QRect, str)
    cancelled = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.shown: list[tuple[ScreenGrab, str, bool]] = []
        self.hidden = 0
        self.destroyed = 0
        self.raise_on_show: Exception | None = None

    def show_selection(self, grab: ScreenGrab, *, hint: str, show_magnifier: bool) -> None:
        if self.raise_on_show is not None:
            raise self.raise_on_show
        self.shown.append((grab, hint, show_magnifier))

    def hide_selection(self) -> None:
        self.hidden += 1

    def destroy(self) -> None:
        self.destroyed += 1


def _monitors() -> list[MonitorInfo]:
    return [
        MonitorInfo("A", QRect(0, 0, 200, 100), QSize(200, 100), 1.0, True),
        MonitorInfo("B", QRect(200, 0, 100, 100), QSize(200, 200), 2.0),
    ]


@pytest.fixture()
def overlays() -> list[FakeOverlay]:
    return []


@pytest.fixture()
def backend() -> FakeCaptureBackend:
    return FakeCaptureBackend(_monitors())


@pytest.fixture()
def manager(
    qapp: QApplication, backend: FakeCaptureBackend, overlays: list[FakeOverlay]
) -> CaptureManager:
    sounds: list[int] = []

    def factory() -> FakeOverlay:
        o = FakeOverlay()
        overlays.append(o)
        return o

    m = CaptureManager(
        backend,
        FakeHotkeyBackend(),
        AppSettings(),
        overlay_factory=factory,
        sound_player=lambda: sounds.append(1),
    )
    m.sounds = sounds  # type: ignore[attr-defined]
    return m


def _request(mode: CaptureMode, **kw: object) -> CaptureRequest:
    defaults: dict[str, object] = {"hide_window": False}
    defaults.update(kw)
    return CaptureRequest(mode, **defaults)  # type: ignore[arg-type]


def _run(qtbot: QtBot, manager: CaptureManager, request: CaptureRequest) -> CaptureResult:
    with qtbot.waitSignal(manager.capture_completed, timeout=3000) as blocker:
        assert manager.start(request)
    result = blocker.args[0]
    assert isinstance(result, CaptureResult)
    return result


# --- full screen ---


def test_full_screen_monitor_under_cursor(
    qtbot: QtBot, manager: CaptureManager, backend: FakeCaptureBackend
) -> None:
    backend.fake_cursor_position = QPoint(250, 50)  # on B
    result = _run(qtbot, manager, _request(CaptureMode.FULL_SCREEN))
    assert result.image.size() == QSize(200, 200)
    meta = result.metadata
    assert meta.mode is CaptureMode.FULL_SCREEN and meta.requested_mode is meta.mode
    assert meta.monitor_name == "B" and meta.device_pixel_ratio == 2.0
    assert meta.screen_rect == QRect(400, 0, 200, 200)
    assert meta.backend == "fake" and meta.platform in ("linux", "darwin", "win32")
    assert meta.cursor_included is False
    assert AppSettings().capture_last_mode() == "full_screen"
    assert manager.state is CaptureState.IDLE


def test_full_screen_all_monitors(qtbot: QtBot, manager: CaptureManager) -> None:
    AppSettings().set_capture_full_screen_scope("all_monitors")
    result = _run(qtbot, manager, _request(CaptureMode.FULL_SCREEN))
    assert result.image.size() == QSize(600, 200)
    assert result.metadata.monitor_name is None
    assert result.metadata.device_pixel_ratio == 2.0


# --- active window ---


def test_active_window_crops_to_geometry(
    qtbot: QtBot, manager: CaptureManager, backend: FakeCaptureBackend
) -> None:
    backend.fake_active_window = QRect(20, 10, 60, 40)
    result = _run(qtbot, manager, _request(CaptureMode.ACTIVE_WINDOW))
    assert result.image.size() == QSize(60, 40)
    assert result.metadata.window_title == "Fake Window"
    assert result.metadata.monitor_name == "A"
    assert result.metadata.screen_rect == QRect(20, 10, 60, 40)


def test_active_window_missing_fails(
    qtbot: QtBot, manager: CaptureManager, backend: FakeCaptureBackend
) -> None:
    backend.fake_active_window = None
    with qtbot.waitSignal(manager.capture_failed) as blocker:
        manager.start(_request(CaptureMode.ACTIVE_WINDOW))
    assert blocker.args == [MSG_NO_WINDOW]


def test_active_window_degrades_to_region(
    qtbot: QtBot, backend: FakeCaptureBackend, overlays: list[FakeOverlay]
) -> None:
    backend.fake_capabilities = BackendCapabilities(full_screen=True, region=True)
    manager = CaptureManager(
        backend, FakeHotkeyBackend(), AppSettings(), overlay_factory=lambda: _new(overlays)
    )
    assert manager.start(_request(CaptureMode.ACTIVE_WINDOW))
    assert manager.state is CaptureState.SELECTING
    grab, hint, magnifier = overlays[0].shown[0]
    assert hint == MSG_WINDOW_DEGRADED and magnifier is True
    with qtbot.waitSignal(manager.capture_completed) as blocker:
        overlays[0].region_selected.emit(QRect(0, 0, 50, 25), "A")
    result = blocker.args[0]
    assert result.metadata.mode is CaptureMode.REGION
    assert result.metadata.requested_mode is CaptureMode.ACTIVE_WINDOW
    assert result.image.size() == QSize(50, 25)


def _new(overlays: list[FakeOverlay]) -> FakeOverlay:
    o = FakeOverlay()
    overlays.append(o)
    return o


# --- region ---


def test_region_selection_on_hidpi_monitor(
    qtbot: QtBot, manager: CaptureManager, overlays: list[FakeOverlay]
) -> None:
    assert manager.start(_request(CaptureMode.REGION))
    assert len(overlays) == 1
    with qtbot.waitSignal(manager.capture_completed) as blocker:
        overlays[0].region_selected.emit(QRect(210, 10, 40, 30), "B")
    result = blocker.args[0]
    assert result.image.size() == QSize(80, 60)
    assert result.metadata.screen_rect == QRect(420, 20, 80, 60)
    assert result.metadata.device_pixel_ratio == 2.0
    # The overlay is reused on the next capture.
    assert manager.start(_request(CaptureMode.REGION))
    assert len(overlays) == 1
    manager.cancel()


def test_region_cancel_is_silent(
    qtbot: QtBot, manager: CaptureManager, overlays: list[FakeOverlay]
) -> None:
    completed: list[object] = []
    manager.capture_completed.connect(completed.append)
    assert manager.start(_request(CaptureMode.REGION))
    with qtbot.waitSignal(manager.capture_cancelled):
        overlays[0].cancelled.emit()
    assert not completed and manager.state is CaptureState.IDLE


def test_overlay_exception_is_reported_and_overlay_recreated(
    qtbot: QtBot, manager: CaptureManager, overlays: list[FakeOverlay]
) -> None:
    manager.start(_request(CaptureMode.FULL_SCREEN, hide_window=False))  # warm up
    first = FakeOverlay()
    first.raise_on_show = RuntimeError("paint failed")
    manager._overlay_factory = lambda: overlays.append(first) or first  # noqa: SLF001
    with qtbot.waitSignal(manager.capture_failed) as blocker:
        manager.start(_request(CaptureMode.REGION))
    assert blocker.args == [MSG_OVERLAY_ERROR]
    assert first.destroyed == 1
    manager._overlay_factory = lambda: _new(overlays)  # noqa: SLF001
    assert manager.start(_request(CaptureMode.REGION))
    assert overlays[-1] is not first and overlays[-1].shown
    manager.cancel()


def test_overlay_failed_signal_mid_selection(
    qtbot: QtBot, manager: CaptureManager, overlays: list[FakeOverlay]
) -> None:
    manager.start(_request(CaptureMode.REGION))
    with qtbot.waitSignal(manager.capture_failed) as blocker:
        overlays[0].failed.emit("The capture overlay encountered an error")
    assert blocker.args == [MSG_OVERLAY_ERROR]
    assert overlays[0].destroyed == 1


# --- refusals and failures ---


def test_busy_request_is_refused(qtbot: QtBot, manager: CaptureManager) -> None:
    assert manager.start(_request(CaptureMode.REGION))
    with qtbot.waitSignal(manager.capture_refused) as blocker:
        assert manager.start(_request(CaptureMode.REGION)) is False
    assert blocker.args == [MSG_BUSY, "menu"]
    manager.cancel()


def test_modal_dialog_refuses_capture(qtbot: QtBot, manager: CaptureManager) -> None:
    dlg = QDialog()
    dlg.setModal(True)
    qtbot.addWidget(dlg)
    dlg.show()
    assert QApplication.activeModalWidget() is dlg
    with qtbot.waitSignal(manager.capture_refused) as blocker:
        assert manager.start(_request(CaptureMode.FULL_SCREEN)) is False
    assert blocker.args == [MSG_MODAL, "menu"]
    dlg.hide()


def test_null_backend_refuses(qapp: QApplication) -> None:
    manager = CaptureManager(NullCaptureBackend(), FakeHotkeyBackend(), AppSettings())
    refused: list[tuple[str, str]] = []
    manager.capture_refused.connect(lambda r, o: refused.append((r, o)))
    assert manager.start(_request(CaptureMode.REGION)) is False
    assert refused == [("Screen capture is not supported on this platform.", "menu")]
    assert "not supported" in manager.capability_summary()


def test_backend_failure_reports_reason(
    qtbot: QtBot, manager: CaptureManager, backend: FakeCaptureBackend
) -> None:
    backend.fail_with = "The portal is missing."
    with qtbot.waitSignal(manager.capture_failed) as blocker:
        manager.start(_request(CaptureMode.FULL_SCREEN))
    assert blocker.args == ["The portal is missing."]
    assert manager.state is CaptureState.IDLE


def test_onboarding_gate_can_cancel(manager: CaptureManager) -> None:
    seen: list[CaptureRequest] = []

    def gate(req: CaptureRequest) -> bool:
        seen.append(req)
        return False

    manager.set_onboarding_gate(gate)
    assert manager.start(_request(CaptureMode.FULL_SCREEN)) is False
    assert len(seen) == 1 and manager.state is CaptureState.IDLE


# --- options ---


def test_cursor_clipboard_and_sound(
    qtbot: QtBot, manager: CaptureManager, backend: FakeCaptureBackend
) -> None:
    AppSettings().set_capture_play_sound(True)
    backend.fake_cursor_position = QPoint(50, 50)
    cursor = QImage(3, 3, QImage.Format.Format_ARGB32)
    cursor.fill(QColor(1, 2, 3))
    backend.fake_cursor_image = cursor
    result = _run(
        qtbot,
        manager,
        _request(CaptureMode.FULL_SCREEN, include_cursor=True, copy_to_clipboard=True),
    )
    assert result.metadata.cursor_included is True
    assert QColor(result.image.pixel(50, 50)) == QColor(1, 2, 3)
    clipboard = QApplication.clipboard()
    assert clipboard is not None and clipboard.image().size() == QSize(200, 100)
    assert manager.sounds == [1]  # type: ignore[attr-defined]
    assert backend.grab_calls[-1] is True


def test_cursor_not_requested_when_backend_lacks_it(
    qtbot: QtBot, manager: CaptureManager, backend: FakeCaptureBackend
) -> None:
    backend.fake_capabilities = BackendCapabilities(
        full_screen=True, region=True, active_window=True
    )
    manager._capabilities = backend.fake_capabilities  # noqa: SLF001
    result = _run(qtbot, manager, _request(CaptureMode.FULL_SCREEN, include_cursor=True))
    assert backend.grab_calls[-1] is False
    assert result.metadata.cursor_included is False


def test_delay_counts_down_then_captures(qtbot: QtBot, manager: CaptureManager) -> None:
    ticks: list[int] = []
    manager.countdown_tick.connect(ticks.append)
    with qtbot.waitSignal(manager.capture_completed, timeout=5000):
        assert manager.start(_request(CaptureMode.FULL_SCREEN, delay_seconds=2))
        assert manager.state is CaptureState.COUNTDOWN
    assert ticks[0] == 2 and ticks[-1] <= 1
    assert manager._badge is not None and not manager._badge.isVisible()  # noqa: SLF001


def test_escape_during_countdown_cancels(qtbot: QtBot, manager: CaptureManager) -> None:
    completed: list[object] = []
    manager.capture_completed.connect(completed.append)
    assert manager.start(_request(CaptureMode.FULL_SCREEN, delay_seconds=5))
    badge = manager._badge  # noqa: SLF001
    assert badge is not None and badge.isVisible() and badge.remaining == 5
    with qtbot.waitSignal(manager.capture_cancelled):
        badge.cancel_requested.emit()
    assert not completed and manager.state is CaptureState.IDLE
    assert not badge.isVisible()


def test_request_from_settings_reads_preferences(manager: CaptureManager) -> None:
    s = AppSettings()
    s.set_capture_default_mode("full_screen")
    s.set_capture_delay_seconds(4)
    s.set_capture_include_cursor(True)
    s.set_capture_hide_window(False)
    req = manager.request_from_settings(origin="tray")
    assert req.mode is CaptureMode.FULL_SCREEN and req.delay_seconds == 4
    assert req.include_cursor and not req.hide_window and req.origin == "tray"
    assert manager.request_from_settings(delay=0).delay_seconds == 0


# --- hide and restore ---


def test_hide_and_restore_around_grab(qtbot: QtBot, manager: CaptureManager) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    window.setGeometry(30, 40, 300, 200)
    window.show()
    seen_hidden: list[bool] = []
    manager.capture_completed.connect(lambda _r: seen_hidden.append(window.isVisible()))
    _run(qtbot, manager, _request(CaptureMode.FULL_SCREEN, hide_window=True))
    assert seen_hidden == [False]  # handoff happens before restore (PRD 7.1)
    assert window.isVisible()
    assert window.geometry() == QRect(30, 40, 300, 200)


def test_windows_restored_on_failure(
    qtbot: QtBot, manager: CaptureManager, backend: FakeCaptureBackend
) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    window.show()
    backend.fail_with = "nope"
    with qtbot.waitSignal(manager.capture_failed, timeout=3000):
        manager.start(_request(CaptureMode.FULL_SCREEN, hide_window=True))
    assert window.isVisible()


def test_window_hider_skips_capture_ui_and_restores_once(qtbot: QtBot) -> None:
    from snapmock.capture.countdown import CountdownBadge

    window = QMainWindow()
    qtbot.addWidget(window)
    window.show()
    badge = CountdownBadge()
    qtbot.addWidget(badge)
    badge.show()
    hider = WindowHider()
    hider.hide_all()
    assert hider.is_hidden and not window.isVisible() and badge.isVisible()
    hider.restore()
    assert window.isVisible() and not hider.is_hidden
    hider.restore()  # idempotent


def test_hide_all_makes_hiding_immediate_for_every_window(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each window is handed to the platform before it is hidden (PRD 3.6).

    Windows fades a window out and keeps compositing it, so a grab taken
    straight after ``hide()`` catches SnapMock semi-transparent over the
    capture. The hider disables that animation first.
    """
    first = QMainWindow()
    qtbot.addWidget(first)
    first.show()
    second = QMainWindow()
    qtbot.addWidget(second)
    second.show()
    asked: list[QWidget] = []
    monkeypatch.setattr(
        WindowHider, "_make_hiding_immediate", staticmethod(lambda w: asked.append(w))
    )
    hider = WindowHider()
    hider.hide_all()
    assert set(asked) == {first, second}
    assert not first.isVisible() and not second.isVisible()
    hider.restore()


# --- hotkeys ---


def test_hotkeys_register_from_settings_and_report_failures(manager: CaptureManager) -> None:
    hk = manager.hotkey_backend
    assert isinstance(hk, FakeHotkeyBackend)
    hk.refused.add("Ctrl+Print")
    failed = manager.register_hotkeys()
    assert [b.action for b in failed] == [HOTKEY_ACTION_FULL_SCREEN]
    region = manager.binding(HOTKEY_ACTION_REGION)
    assert region is not None and region.registered and region.key_text == "Print"


def test_hotkey_trigger_starts_capture(qtbot: QtBot, manager: CaptureManager) -> None:
    manager.register_hotkeys()
    hk = manager.hotkey_backend
    assert isinstance(hk, FakeHotkeyBackend)
    AppSettings().set_capture_hide_window(False)
    with qtbot.waitSignal(manager.capture_completed, timeout=3000) as blocker:
        hk.fire(HOTKEY_ACTION_FULL_SCREEN)
    assert blocker.args[0].metadata.mode is CaptureMode.FULL_SCREEN
    # Origin is recorded from the hotkey path.
    req = manager.request_from_settings(CaptureMode.REGION, ORIGIN_HOTKEY)
    assert req.origin == ORIGIN_HOTKEY


def test_set_hotkey_releases_old_and_keeps_old_on_failure(manager: CaptureManager) -> None:
    manager.register_hotkeys()
    hk = manager.hotkey_backend
    assert isinstance(hk, FakeHotkeyBackend)
    assert manager.set_hotkey(HOTKEY_ACTION_REGION, "F9")
    assert hk.registered[HOTKEY_ACTION_REGION] == "F9"
    assert AppSettings().capture_hotkey(HOTKEY_ACTION_REGION) == "F9"
    hk.refused.add("F10")
    assert manager.set_hotkey(HOTKEY_ACTION_REGION, "F10") is False
    binding = manager.binding(HOTKEY_ACTION_REGION)
    assert binding is not None and binding.key_text == "F9" and binding.registered
    assert AppSettings().capture_hotkey(HOTKEY_ACTION_REGION) == "F9"
    assert manager.set_hotkey(HOTKEY_ACTION_REGION, "")
    assert not binding.is_bound and HOTKEY_ACTION_REGION not in hk.registered
    assert binding.key_sequence == QKeySequence()


def test_shutdown_releases_everything(manager: CaptureManager) -> None:
    manager.register_hotkeys()
    assert manager.listen_for_commands(name=f"snapmock-test-{id(manager)}")
    manager.shutdown()
    assert manager.channel is None
    hk = manager.hotkey_backend
    assert isinstance(hk, FakeHotkeyBackend) and not hk.registered


def test_command_line_over_channel_starts_capture(qtbot: QtBot, manager: CaptureManager) -> None:
    from snapmock.capture.single_instance import try_forward

    name = f"snapmock-test-cli-{id(manager)}"
    assert manager.listen_for_commands(name=name)
    AppSettings().set_capture_hide_window(False)
    with qtbot.waitSignal(manager.capture_completed, timeout=3000) as blocker:
        assert try_forward(["snapmock", "--capture", "full"], name=name)
    assert blocker.args[0].metadata.mode is CaptureMode.FULL_SCREEN
    manager.shutdown()


def _unused(_: Callable[[], None]) -> None:  # keeps the Callable import honest for mypy
    return None
