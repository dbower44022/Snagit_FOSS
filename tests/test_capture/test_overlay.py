"""Tests for the region selection overlay (PRD Section 5), driven by synthetic events."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import QImage, QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from snapmock.capture.backend import FakeCaptureBackend
from snapmock.capture.models import MonitorInfo, ScreenGrab
from snapmock.capture.overlay import (
    HINT_CROSS_SCALING,
    HINT_TEXT,
    MSG_OVERLAY_ERROR_EXPORT,
    OverlayWindow,
    RegionOverlay,
    compute_rect,
)

NoMod = Qt.KeyboardModifier.NoModifier
Shift = Qt.KeyboardModifier.ShiftModifier
Alt = Qt.KeyboardModifier.AltModifier
Left = Qt.MouseButton.LeftButton
Right = Qt.MouseButton.RightButton


def _monitors(ratio_b: float = 1.0) -> list[MonitorInfo]:
    return [
        MonitorInfo("A", QRect(0, 0, 200, 100), QSize(200, 100), 1.0, True),
        MonitorInfo(
            "B",
            QRect(200, 0, 100, 100),
            QSize(round(100 * ratio_b), round(100 * ratio_b)),
            ratio_b,
        ),
    ]


def _move(win: OverlayWindow, pos: QPoint, mods: Qt.KeyboardModifier = NoMod) -> None:
    """A mouse move with modifiers (qtbot.mouseMove takes none)."""
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(pos),
        QPointF(win.mapToGlobal(pos)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        mods,
    )
    QApplication.sendEvent(win, event)


@pytest.fixture()
def grab(qapp: QApplication) -> ScreenGrab:
    return FakeCaptureBackend(_monitors()).grab_screens(False)


@pytest.fixture()
def overlay(qtbot: QtBot, grab: ScreenGrab) -> RegionOverlay:
    o = RegionOverlay()
    o.cancel_on_focus_loss = False  # offscreen has no real focus; tested separately
    o.show_selection(grab, hint="", show_magnifier=True)
    for w in o.windows:
        qtbot.addWidget(w)
    return o


def _win(overlay: RegionOverlay, name: str) -> OverlayWindow:
    return next(w for w in overlay.windows if w.monitor.name == name)


def test_compute_rect_modifiers() -> None:
    p, c = QPoint(10, 10), QPoint(40, 20)
    assert compute_rect(p, c, square=False, from_center=False) == QRect(10, 10, 30, 10)
    assert compute_rect(p, c, square=True, from_center=False) == QRect(10, 10, 30, 30)
    assert compute_rect(p, c, square=False, from_center=True) == QRect(-20, 0, 60, 20)
    assert compute_rect(p, c, square=True, from_center=True) == QRect(-20, -20, 60, 60)
    assert compute_rect(c, p, square=False, from_center=False) == QRect(10, 10, 30, 10)


def test_overlay_creates_one_window_per_monitor(overlay: RegionOverlay) -> None:
    assert overlay.is_visible
    assert [w.monitor.name for w in overlay.windows] == ["A", "B"]
    assert _win(overlay, "A").geometry() == QRect(0, 0, 200, 100)
    assert _win(overlay, "B").geometry() == QRect(200, 0, 100, 100)
    assert overlay.model.hint == HINT_TEXT


def test_drag_and_release_confirms(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win = _win(overlay, "A")
    with qtbot.waitSignal(overlay.region_selected) as blocker:
        qtbot.mousePress(win, Left, NoMod, QPoint(10, 20))
        qtbot.mouseMove(win, QPoint(50, 60))
        assert overlay.model.rect == QRect(10, 20, 40, 40)
        qtbot.mouseRelease(win, Left, NoMod, QPoint(50, 60))
    assert blocker.args == [QRect(10, 20, 40, 40), "A"]
    assert not overlay.is_visible


def test_small_drag_is_discarded(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win = _win(overlay, "A")
    selected: list[object] = []
    overlay.region_selected.connect(lambda r, n: selected.append(r))
    qtbot.mousePress(win, Left, NoMod, QPoint(10, 10))
    qtbot.mouseMove(win, QPoint(12, 12))
    qtbot.mouseRelease(win, Left, NoMod, QPoint(12, 12))
    assert not selected and overlay.is_visible and not overlay.model.dragging


def test_shift_and_alt_modifiers(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win = _win(overlay, "A")
    qtbot.mousePress(win, Left, NoMod, QPoint(50, 50))
    _move(win, QPoint(80, 60), Shift)
    assert overlay.model.rect == QRect(50, 50, 30, 30)
    _move(win, QPoint(80, 60), Alt)
    assert overlay.model.rect == QRect(20, 40, 60, 20)
    _move(win, QPoint(80, 60), Shift | Alt)
    assert overlay.model.rect == QRect(20, 20, 60, 60)
    # Modifiers may change without the mouse moving: the rectangle recomputes.
    qtbot.keyPress(win, Qt.Key.Key_Shift, Shift)
    assert overlay.model.rect == QRect(50, 50, 30, 30)
    qtbot.keyRelease(win, Qt.Key.Key_Shift, NoMod)
    assert overlay.model.rect == QRect(50, 50, 30, 10)
    qtbot.mouseRelease(win, Left, NoMod, QPoint(80, 60))


def test_space_moves_rectangle_then_resumes_resizing(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win = _win(overlay, "A")
    qtbot.mousePress(win, Left, NoMod, QPoint(10, 10))
    qtbot.mouseMove(win, QPoint(40, 30))
    assert overlay.model.rect == QRect(10, 10, 30, 20)
    qtbot.keyPress(win, Qt.Key.Key_Space)
    assert overlay.model.moving
    qtbot.mouseMove(win, QPoint(60, 50))
    assert overlay.model.rect == QRect(30, 30, 30, 20)
    qtbot.keyRelease(win, Qt.Key.Key_Space)
    assert not overlay.model.moving
    qtbot.mouseMove(win, QPoint(70, 60))
    assert overlay.model.rect == QRect(30, 30, 40, 30)
    with qtbot.waitSignal(overlay.region_selected) as blocker:
        qtbot.mouseRelease(win, Left, NoMod, QPoint(70, 60))
    assert blocker.args[0] == QRect(30, 30, 40, 30)


def test_escape_and_right_click_cancel(
    qtbot: QtBot, overlay: RegionOverlay, grab: ScreenGrab
) -> None:
    win = _win(overlay, "A")
    with qtbot.waitSignal(overlay.cancelled):
        qtbot.keyPress(win, Qt.Key.Key_Escape)
    assert not overlay.is_visible
    overlay.show_selection(grab, hint="", show_magnifier=True)
    for w in overlay.windows:
        qtbot.addWidget(w)
    win = _win(overlay, "A")
    with qtbot.waitSignal(overlay.cancelled):
        qtbot.mousePress(win, Right, NoMod, QPoint(5, 5))
    assert not overlay.is_visible


def test_drag_spans_monitors_with_equal_ratio(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win_a = _win(overlay, "A")
    qtbot.mousePress(win_a, Left, NoMod, QPoint(150, 10))
    # The pointer crosses into B; B's window reports the move in its own coordinates.
    win_b = _win(overlay, "B")
    qtbot.mouseMove(win_b, QPoint(50, 60))
    assert overlay.model.rect == QRect(150, 10, 100, 50)
    with qtbot.waitSignal(overlay.region_selected) as blocker:
        qtbot.mouseRelease(win_b, Left, NoMod, QPoint(50, 60))
    assert blocker.args == [QRect(150, 10, 100, 50), "A"]


def test_drag_is_clamped_at_monitor_with_different_ratio(qtbot: QtBot, qapp: QApplication) -> None:
    grab = FakeCaptureBackend(_monitors(2.0)).grab_screens(False)
    overlay = RegionOverlay()
    overlay.cancel_on_focus_loss = False
    overlay.show_selection(grab, hint="", show_magnifier=False)
    for w in overlay.windows:
        qtbot.addWidget(w)
    win_a, win_b = _win(overlay, "A"), _win(overlay, "B")
    qtbot.mousePress(win_a, Left, NoMod, QPoint(150, 10))
    qtbot.mouseMove(win_b, QPoint(50, 60))
    assert overlay.model.rect == QRect(150, 10, 50, 50)
    assert overlay.model.hint == HINT_CROSS_SCALING
    qtbot.mouseMove(win_a, QPoint(180, 40))
    assert overlay.model.hint == HINT_TEXT
    qtbot.mouseRelease(win_a, Left, NoMod, QPoint(180, 40))


def test_degradation_hint_then_standard_hint(qtbot: QtBot, grab: ScreenGrab) -> None:
    overlay = RegionOverlay()
    overlay.cancel_on_focus_loss = False
    overlay.show_selection(grab, hint="degraded", show_magnifier=True)
    for w in overlay.windows:
        qtbot.addWidget(w)
    assert overlay.model.hint == "degraded"
    overlay._restore_hint()  # noqa: SLF001 - the 3 s timer's slot
    assert overlay.model.hint == HINT_TEXT
    overlay.destroy()


def test_arrow_keys_move_crosshair_and_enter_flashes(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win = _win(overlay, "A")
    overlay.model.cursor = QPoint(50, 50)
    qtbot.keyPress(win, Qt.Key.Key_Right)
    qtbot.keyPress(win, Qt.Key.Key_Down, Shift)
    assert overlay.model.cursor == QPoint(51, 60)
    qtbot.keyPress(win, Qt.Key.Key_Return)
    assert overlay.model.hint_flash
    overlay._end_flash()  # noqa: SLF001
    assert not overlay.model.hint_flash


def test_focus_loss_cancels(qtbot: QtBot, overlay: RegionOverlay) -> None:
    overlay.cancel_on_focus_loss = True
    other = QWidget()  # "another application" takes the focus
    qtbot.addWidget(other)
    other.show()
    other.activateWindow()
    with qtbot.waitSignal(overlay.cancelled, timeout=2000):
        overlay.schedule_focus_check()
    assert not overlay.is_visible


def test_focus_moving_between_overlay_windows_does_not_cancel(
    qtbot: QtBot, overlay: RegionOverlay
) -> None:
    overlay.cancel_on_focus_loss = True
    cancelled: list[int] = []
    overlay.cancelled.connect(lambda: cancelled.append(1))
    _win(overlay, "B").activateWindow()
    overlay.schedule_focus_check()
    qtbot.wait(300)
    assert not cancelled and overlay.is_visible


def test_paint_runs_on_every_window(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win = _win(overlay, "A")
    qtbot.mousePress(win, Left, NoMod, QPoint(10, 10))
    qtbot.mouseMove(win, QPoint(60, 40))
    for w in overlay.windows:
        w.repaint()
        image = w.grab().toImage()
        assert not image.isNull()
    qtbot.mouseRelease(win, Left, NoMod, QPoint(60, 40))


def test_handler_exception_is_reported_and_overlay_hidden(
    qtbot: QtBot, overlay: RegionOverlay
) -> None:
    def boom(*_args: object) -> None:
        raise RuntimeError("bad")

    with qtbot.waitSignal(overlay.failed) as blocker:
        overlay.guarded(boom, 1)
    assert blocker.args == [MSG_OVERLAY_ERROR_EXPORT]
    assert not overlay.is_visible
    overlay.destroy()
    assert overlay.windows == []


def test_physical_pixel_lookup_on_hidpi(qapp: QApplication) -> None:
    grab = FakeCaptureBackend(_monitors(2.0)).grab_screens(False)
    overlay = RegionOverlay()
    overlay.cancel_on_focus_loss = False
    overlay.show_selection(grab, hint="", show_magnifier=True)
    win_b = _win(overlay, "B")
    color = win_b.physical_pixel(QPoint(250, 50))
    assert color is not None
    assert color.rgb() == grab.images["B"].pixel(100, 100)
    assert win_b.physical_pixel(QPoint(999, 999)) is None
    overlay.destroy()


def test_show_without_images_raises(qapp: QApplication) -> None:
    overlay = RegionOverlay()
    empty = ScreenGrab(images={}, monitors=_monitors())
    with pytest.raises(RuntimeError):
        overlay.show_selection(empty, hint="", show_magnifier=True)
    overlay.destroy()


def test_dimmed_image_is_darker_than_source(qtbot: QtBot, overlay: RegionOverlay) -> None:
    win = _win(overlay, "A")
    overlay.model.cursor = QPoint(-50, -50)  # keep crosshair and magnifier off this window
    win.repaint()
    painted = win.grab().toImage()
    source: QImage = win._image  # noqa: SLF001
    assert painted.pixelColor(100, 50).lightness() < source.pixelColor(100, 50).lightness()
