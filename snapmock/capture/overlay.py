"""The region selection overlay (Screen Capture PRD Section 5).

One frameless, always-on-top window per monitor, each painting that monitor's
frozen image with the shared selection drawn over it. Everything shown comes
from the :class:`ScreenGrab`; the overlay never reads the live screen and
never touches the main window (PRD 5.1).

Coordinates: the selection model works in virtual-desktop logical pixels. Each
window converts between its local widget coordinates and virtual coordinates
by its monitor's logical origin.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFocusEvent,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget

from snapmock.capture.compositing import physical_rect_for
from snapmock.capture.countdown import CAPTURE_UI_PROPERTY
from snapmock.capture.models import MonitorInfo, ScreenGrab

log = logging.getLogger("snapmock.capture")

MIN_SELECTION = 4  # logical pixels (PRD 5.3)
DIM_ALPHA = 102  # 40 percent black (PRD 5.2)
HINT_TEXT = (
    "Drag to select a region. Shift: square. Alt: from center. "
    "Space: move. Enter: capture. Esc: cancel."
)
HINT_CROSS_SCALING = "Selection cannot cross monitors with different scaling."
DEGRADATION_HINT_MS = 3000
MAGNIFIER_SIZE = 132
MAGNIFIER_PIXELS = 11
MAGNIFIER_ZOOM = 12
MAGNIFIER_OFFSET = 20
FOCUS_CHECK_MS = 100
OVERLAY_ERROR = "The capture overlay encountered an error"
MSG_OVERLAY_ERROR_EXPORT = OVERLAY_ERROR


def accent_color() -> QColor:
    """The theme accent (General UI PRD 13), read from the ThemeManager."""
    from snapmock.core.theme_manager import current_theme

    return QColor(current_theme().accent)


class SelectionModel:
    """The shared selection state, in virtual logical pixels."""

    def __init__(self) -> None:
        self.press: QPoint | None = None
        self.current = QPoint()
        self.rect = QRect()
        self.moving = False
        self.move_anchor = QPoint()
        self.move_rect = QRect()
        self.origin_monitor: MonitorInfo | None = None
        self.allowed: QRect = QRect()
        self.cursor = QPoint()
        self.hint = HINT_TEXT
        self.hint_flash = False

    @property
    def dragging(self) -> bool:
        return self.press is not None

    def reset(self) -> None:
        self.press = None
        self.rect = QRect()
        self.moving = False
        self.origin_monitor = None
        self.allowed = QRect()
        self.hint_flash = False


def compute_rect(press: QPoint, current: QPoint, *, square: bool, from_center: bool) -> QRect:
    """The rectangle for a drag from *press* to *current* under the modifiers (PRD 5.4)."""
    dx = current.x() - press.x()
    dy = current.y() - press.y()
    if square:
        side = max(abs(dx), abs(dy))
        dx = side if dx >= 0 else -side
        dy = side if dy >= 0 else -side
    if from_center:
        w, h = abs(dx), abs(dy)
        return QRect(press.x() - w, press.y() - h, 2 * w, 2 * h)
    x = min(press.x(), press.x() + dx)
    y = min(press.y(), press.y() + dy)
    return QRect(x, y, abs(dx), abs(dy))


class OverlayWindow(QWidget):
    """The overlay for one monitor. Delegates every interaction to the overlay."""

    def __init__(self, overlay: RegionOverlay, monitor: MonitorInfo, image: QImage) -> None:
        super().__init__(
            None,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.BypassWindowManagerHint,
        )
        self.setProperty(CAPTURE_UI_PROPERTY, True)
        self._overlay = overlay
        self.monitor = monitor
        self._pixmap = QPixmap.fromImage(image)
        self._pixmap.setDevicePixelRatio(monitor.device_pixel_ratio)
        self._image = image
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    # --- coordinates ---

    def to_virtual(self, local: QPoint) -> QPoint:
        return local + self.monitor.logical_geometry.topLeft()

    def to_local(self, virtual: QPoint) -> QPoint:
        return virtual - self.monitor.logical_geometry.topLeft()

    def local_rect(self, virtual: QRect) -> QRect:
        return virtual.translated(-self.monitor.logical_geometry.topLeft())

    def physical_pixel(self, virtual: QPoint) -> QColor | None:
        local = self.to_local(virtual)
        ratio = self.monitor.device_pixel_ratio
        px = QPoint(round(local.x() * ratio), round(local.y() * ratio))
        if not self._image.rect().contains(px):
            return None
        return QColor(self._image.pixel(px))

    def show_on_monitor(self) -> None:
        geometry = self.monitor.logical_geometry
        screen = next(
            (s for s in QGuiApplication.screens() if s.name() == self.monitor.name), None
        )
        if screen is not None and screen.geometry() == geometry:
            self.setScreen(screen)
            self.setGeometry(geometry)
            self.showFullScreen()
        else:
            self.setGeometry(geometry)
            self.show()
        self.raise_()

    # --- events (all guarded by the overlay) ---

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        event.accept()
        self._overlay.guarded(
            self._overlay.on_press,
            self.to_virtual(event.pos()),
            event.button(),
            event.modifiers(),
        )

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        event.accept()
        self._overlay.guarded(
            self._overlay.on_move, self.to_virtual(event.pos()), event.modifiers()
        )

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        event.accept()
        self._overlay.guarded(
            self._overlay.on_release,
            self.to_virtual(event.pos()),
            event.button(),
            event.modifiers(),
        )

    def wheelEvent(self, event: Any) -> None:  # noqa: ANN401 - QWheelEvent | None
        if event is not None:
            event.accept()  # ignored by design (PRD 5.3)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        event.accept()
        self._overlay.guarded(self._overlay.on_key_press, event)

    def keyReleaseEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        event.accept()
        self._overlay.guarded(self._overlay.on_key_release, event)

    def focusOutEvent(self, event: QFocusEvent | None) -> None:
        super().focusOutEvent(event)
        self._overlay.schedule_focus_check()

    def event(self, event: QEvent | None) -> bool:
        if event is not None and event.type() == QEvent.Type.WindowDeactivate:
            self._overlay.schedule_focus_check()
        return super().event(event)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        try:
            self._paint(painter)
        except Exception as e:  # noqa: BLE001 - overlay fault isolation (PRD 7.4)
            painter.end()
            self._overlay.report_failure(e)
            return
        painter.end()

    # --- painting (PRD 5.2, 5.5) ---

    def _paint(self, painter: QPainter) -> None:
        model = self._overlay.model
        accent = accent_color()
        painter.drawPixmap(0, 0, self._pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, DIM_ALPHA))

        selection = self.local_rect(model.rect) if model.dragging else QRect()
        if not selection.isEmpty():
            ratio = self.monitor.device_pixel_ratio
            source = QRect(
                round(selection.x() * ratio),
                round(selection.y() * ratio),
                round(selection.width() * ratio),
                round(selection.height() * ratio),
            )
            painter.drawPixmap(selection, self._pixmap, source)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawRect(selection.adjusted(1, 1, -2, -2))
            painter.setPen(QPen(accent, 1))
            painter.drawRect(selection.adjusted(0, 0, -1, -1))
            self._paint_dimensions(painter, selection, model)

        cursor_local = self.to_local(model.cursor)
        on_this_monitor = self.rect().contains(cursor_local)
        if on_this_monitor and not model.dragging:
            painter.setPen(QPen(accent, 1))
            painter.drawLine(cursor_local.x(), 0, cursor_local.x(), self.height())
            painter.drawLine(0, cursor_local.y(), self.width(), cursor_local.y())
        if on_this_monitor:
            self._paint_hint(painter, model)
            if self._overlay.show_magnifier and not model.moving:
                self._paint_magnifier(painter, cursor_local, model)

    def _paint_dimensions(
        self, painter: QPainter, selection: QRect, model: SelectionModel
    ) -> None:
        ratio = self.monitor.device_pixel_ratio
        phys = physical_rect_for(model.rect, ratio)
        text = f"{phys.width()} × {phys.height()}"
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(text) + 12
        h = metrics.height() + 6
        x = selection.right() + 6
        y = selection.bottom() + 6
        if x + w > self.width() or y + h > self.height():
            x = selection.right() - w - 4
            y = selection.bottom() - h - 4
        pill = QRect(x, y, w, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 20, 220))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_hint(self, painter: QPainter, model: SelectionModel) -> None:
        metrics = painter.fontMetrics()
        text = model.hint
        w = metrics.horizontalAdvance(text) + 24
        h = metrics.height() + 12
        bar = QRect((self.width() - w) // 2, 16, w, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent_color() if model.hint_flash else QColor(20, 20, 20, 220))
        painter.drawRoundedRect(bar, 6, 6)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(bar, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_magnifier(
        self, painter: QPainter, cursor_local: QPoint, model: SelectionModel
    ) -> None:
        ratio = self.monitor.device_pixel_ratio
        center = QPoint(round(cursor_local.x() * ratio), round(cursor_local.y() * ratio))
        half = MAGNIFIER_PIXELS // 2
        source = QRect(center.x() - half, center.y() - half, MAGNIFIER_PIXELS, MAGNIFIER_PIXELS)
        text_h = painter.fontMetrics().height() * 2 + 10
        box = QRect(0, 0, MAGNIFIER_SIZE, MAGNIFIER_SIZE + text_h)
        x = cursor_local.x() + MAGNIFIER_OFFSET
        y = cursor_local.y() + MAGNIFIER_OFFSET
        if x + box.width() > self.width():
            x = cursor_local.x() - MAGNIFIER_OFFSET - box.width()
        if y + box.height() > self.height():
            y = cursor_local.y() - MAGNIFIER_OFFSET - box.height()
        box.moveTo(max(0, x), max(0, y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 20, 235))
        painter.drawRect(box)
        image_rect = QRect(box.x(), box.y(), MAGNIFIER_SIZE, MAGNIFIER_SIZE)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(image_rect, self._image, source)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        for i in range(1, MAGNIFIER_PIXELS):
            offset = i * MAGNIFIER_ZOOM
            painter.drawLine(box.x() + offset, box.y(), box.x() + offset, box.y() + MAGNIFIER_SIZE)
            painter.drawLine(box.x(), box.y() + offset, box.x() + MAGNIFIER_SIZE, box.y() + offset)
        painter.setPen(QPen(accent_color(), 1))
        painter.drawRect(
            box.x() + half * MAGNIFIER_ZOOM,
            box.y() + half * MAGNIFIER_ZOOM,
            MAGNIFIER_ZOOM,
            MAGNIFIER_ZOOM,
        )
        color = self.physical_pixel(model.cursor)
        hex_text = color.name().upper() if color is not None else "-"
        phys_x = round(model.cursor.x() * ratio)
        phys_y = round(model.cursor.y() * ratio)
        painter.setPen(QColor(255, 255, 255))
        text_rect = QRect(box.x(), box.y() + MAGNIFIER_SIZE, MAGNIFIER_SIZE, text_h)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"X: {phys_x}  Y: {phys_y}\n{hex_text}",
        )


class RegionOverlay(QObject):
    """Owns the per-monitor windows and the shared selection (PRD 5).

    Signals
    -------
    region_selected(QRect, str)
        The confirmed rectangle in virtual logical pixels, and the monitor where
        the drag began.
    cancelled()
        Escape, right-click, or focus loss to another application.
    failed(str)
        An exception inside the overlay; the manager destroys and recreates it.
    """

    region_selected = pyqtSignal(QRect, str)
    cancelled = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.model = SelectionModel()
        self.show_magnifier = True
        self.cancel_on_focus_loss = True
        self._windows: list[OverlayWindow] = []
        self._grab: ScreenGrab | None = None
        self._visible = False
        self._degradation_timer = QTimer(self)
        self._degradation_timer.setSingleShot(True)
        self._degradation_timer.timeout.connect(self._restore_hint)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.setInterval(250)
        self._flash_timer.timeout.connect(self._end_flash)
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.setInterval(FOCUS_CHECK_MS)
        self._focus_timer.timeout.connect(self._check_focus)

    # --- RegionSelector contract ---

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def windows(self) -> list[OverlayWindow]:
        return list(self._windows)

    def show_selection(self, grab: ScreenGrab, *, hint: str, show_magnifier: bool) -> None:
        self._grab = grab
        self.show_magnifier = show_magnifier
        self.model.reset()
        self.model.cursor = QPoint(grab.cursor_position or QCursor.pos())
        self._close_windows()
        for monitor in grab.monitors:
            image = grab.images.get(monitor.name)
            if image is None or image.isNull():
                continue
            window = OverlayWindow(self, monitor, image)
            window.destroyed.connect(lambda _obj=None, w=window: self._forget(w))
            self._windows.append(window)
        if not self._windows:
            raise RuntimeError("no monitor image to show")
        if hint:
            self.model.hint = hint
            self._degradation_timer.start(DEGRADATION_HINT_MS)
        else:
            self.model.hint = HINT_TEXT
        self._visible = True
        for window in self._windows:
            window.show_on_monitor()
        target = self._window_at(self.model.cursor) or self._windows[0]
        target.activateWindow()
        target.setFocus()
        self._repaint()

    def hide_selection(self) -> None:
        self._visible = False
        self._focus_timer.stop()
        self._degradation_timer.stop()
        for window in self._windows:
            window.hide()
        self.model.reset()

    def destroy(self) -> None:
        self.hide_selection()
        self._close_windows()
        self._grab = None

    def _close_windows(self) -> None:
        for window in self._windows:
            window.hide()
            window.deleteLater()
        self._windows = []

    # --- fault isolation ---

    def guarded(self, handler: Callable[..., None], *args: Any) -> None:
        try:
            handler(*args)
        except Exception as e:  # noqa: BLE001 - PRD 7.4: report, never crash the editor
            self.report_failure(e)

    def report_failure(self, error: BaseException) -> None:
        if not self._visible:
            return
        log.exception("Overlay failure", exc_info=error)
        self._visible = False
        for window in self._windows:
            window.hide()
        self.failed.emit(OVERLAY_ERROR)

    # --- interaction (PRD 5.3, 5.4) ---

    def on_press(self, pos: QPoint, button: Qt.MouseButton, mods: Qt.KeyboardModifier) -> None:
        if button == Qt.MouseButton.RightButton:
            self._cancel()
            return
        if button != Qt.MouseButton.LeftButton or self.model.dragging:
            return
        monitor = self._monitor_at(pos)
        if monitor is None:
            return
        self.model.press = QPoint(pos)
        self.model.current = QPoint(pos)
        self.model.origin_monitor = monitor
        self.model.allowed = self._allowed_area(monitor)
        self.model.rect = QRect(pos, QSize(0, 0))
        self.model.cursor = QPoint(pos)
        self._repaint()

    def on_move(self, pos: QPoint, mods: Qt.KeyboardModifier) -> None:
        model = self.model
        model.cursor = QPoint(pos)
        if model.dragging:
            if model.moving:
                delta = pos - model.move_anchor
                model.rect = model.move_rect.translated(delta)
            else:
                model.current = self._clamp_point(pos)
                self._recompute(mods)
        self._repaint()

    def on_release(self, pos: QPoint, button: Qt.MouseButton, mods: Qt.KeyboardModifier) -> None:
        model = self.model
        if button != Qt.MouseButton.LeftButton or not model.dragging:
            return
        if not model.moving:
            model.current = self._clamp_point(pos)
            self._recompute(mods)
        rect = QRect(model.rect)
        origin = model.origin_monitor
        if rect.width() >= MIN_SELECTION and rect.height() >= MIN_SELECTION:
            name = origin.name if origin is not None else ""
            self.hide_selection()
            self.region_selected.emit(rect, name)
            return
        # Too small: discard the drag and return to the idle crosshair.
        model.press = None
        model.rect = QRect()
        model.moving = False
        self._repaint()

    def on_key_press(self, event: QKeyEvent) -> None:
        key = event.key()
        model = self.model
        if key == Qt.Key.Key_Escape:
            self._cancel()
            return
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            if model.dragging and not model.moving:
                model.moving = True
                model.move_anchor = QPoint(model.cursor)
                model.move_rect = QRect(model.rect)
                for window in self._windows:
                    window.setCursor(Qt.CursorShape.ClosedHandCursor)
                self._repaint()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not model.dragging:
                model.hint_flash = True
                self._flash_timer.start()
                self._repaint()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if model.dragging:
                return
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx = -step if key == Qt.Key.Key_Left else step if key == Qt.Key.Key_Right else 0
            dy = -step if key == Qt.Key.Key_Up else step if key == Qt.Key.Key_Down else 0
            model.cursor = model.cursor + QPoint(dx, dy)
            QCursor.setPos(model.cursor)
            self._repaint()
            return
        if key in (Qt.Key.Key_Shift, Qt.Key.Key_Alt) and model.dragging and not model.moving:
            self._recompute(_modifiers_after(event, pressed=True))
            self._repaint()

    def on_key_release(self, event: QKeyEvent) -> None:
        key = event.key()
        model = self.model
        if key == Qt.Key.Key_Space and not event.isAutoRepeat() and model.moving:
            model.moving = False
            # Resume resizing from the new position: the cursor keeps its corner.
            rect = model.rect
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                model.press = rect.center()
            else:
                far_x = rect.left() if model.cursor.x() > rect.center().x() else rect.right() + 1
                far_y = rect.top() if model.cursor.y() > rect.center().y() else rect.bottom() + 1
                model.press = QPoint(far_x, far_y)
            model.current = QPoint(model.cursor)
            for window in self._windows:
                window.setCursor(Qt.CursorShape.CrossCursor)
            self._repaint()
            return
        if key in (Qt.Key.Key_Shift, Qt.Key.Key_Alt) and model.dragging and not model.moving:
            self._recompute(_modifiers_after(event, pressed=False))
            self._repaint()

    # --- focus loss (PRD 5.6) ---

    def schedule_focus_check(self) -> None:
        if self._visible and self.cancel_on_focus_loss:
            self._focus_timer.start()

    def _check_focus(self) -> None:
        if not self._visible or not self.cancel_on_focus_loss:
            return
        active = QApplication.activeWindow()
        if active is None or active not in self._windows:
            self._cancel()

    # --- helpers ---

    def _cancel(self) -> None:
        if not self._visible:
            return
        self.hide_selection()
        self.cancelled.emit()

    def _recompute(self, mods: Qt.KeyboardModifier) -> None:
        model = self.model
        if model.press is None:
            return
        square = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        center = bool(mods & Qt.KeyboardModifier.AltModifier)
        rect = compute_rect(model.press, model.current, square=square, from_center=center)
        if not model.allowed.isEmpty():
            rect = rect.intersected(model.allowed)
        model.rect = rect

    def _clamp_point(self, pos: QPoint) -> QPoint:
        """Clamp a drag point to monitors sharing the origin's ratio (PRD 5.7)."""
        model = self.model
        origin = model.origin_monitor
        if origin is None:
            return QPoint(pos)
        here = self._monitor_at(pos)
        if here is not None and here.device_pixel_ratio != origin.device_pixel_ratio:
            model.hint = HINT_CROSS_SCALING
            geo = origin.logical_geometry
            return QPoint(
                min(max(pos.x(), geo.left()), geo.right() + 1),
                min(max(pos.y(), geo.top()), geo.bottom() + 1),
            )
        if model.hint == HINT_CROSS_SCALING:
            model.hint = HINT_TEXT
        return QPoint(pos)

    def _allowed_area(self, origin: MonitorInfo) -> QRect:
        grab = self._grab
        if grab is None:
            return QRect(origin.logical_geometry)
        area = QRect()
        for m in grab.monitors:
            if m.device_pixel_ratio == origin.device_pixel_ratio:
                area = area.united(m.logical_geometry)
        return area

    def _monitor_at(self, pos: QPoint) -> MonitorInfo | None:
        return self._grab.monitor_at(pos) if self._grab is not None else None

    def _window_at(self, pos: QPoint) -> OverlayWindow | None:
        for window in self._windows:
            if window.monitor.logical_geometry.contains(pos):
                return window
        return None

    def _restore_hint(self) -> None:
        if self.model.hint != HINT_CROSS_SCALING:
            self.model.hint = HINT_TEXT
        self._repaint()

    def _end_flash(self) -> None:
        self.model.hint_flash = False
        self._repaint()

    def _forget(self, window: OverlayWindow) -> None:
        """A window was deleted from outside (for example at application exit)."""
        self._windows = [w for w in self._windows if w is not window]

    def _repaint(self) -> None:
        for window in self._windows:
            window.update()


def _modifiers_after(event: QKeyEvent, *, pressed: bool) -> Qt.KeyboardModifier:
    """The modifier state once *event* (a press or release of Shift or Alt) applies.

    ``event.modifiers()`` on a modifier key's own press or release is not
    reliable across platforms, so the key itself decides.
    """
    mods = event.modifiers()
    flag = {
        Qt.Key.Key_Shift: Qt.KeyboardModifier.ShiftModifier,
        Qt.Key.Key_Alt: Qt.KeyboardModifier.AltModifier,
    }.get(Qt.Key(event.key()))
    if flag is None:
        return mods
    return (mods | flag) if pressed else (mods & ~flag)


def make_overlay() -> RegionOverlay:
    """The overlay factory the manager uses (created lazily, PRD 5.1)."""
    return RegionOverlay()
