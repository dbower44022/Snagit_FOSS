"""SnapView — QGraphicsView with zoom, pan, and tool event routing."""

from __future__ import annotations

import bisect
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRectF, Qt, QTimeLine, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import QGraphicsView, QWidget

from snapmock.config.constants import (
    CANVAS_SHADOW_OFFSET,
    CHECKERBOARD_CELL_SIZE,
    EMPTY_CANVAS_FONT_SIZE,
    EMPTY_CANVAS_TEXT,
    GRID_MAJOR_MULTIPLE,
    GRID_MIN_PIXEL_SPACING,
    GRID_MINOR_MIN_ZOOM,
    GRID_SIZE_DEFAULT,
    LIBRARY_PATHS_MIME,
    RULER_SIZE,
    ZOOM_DEFAULT,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_PIXEL_GRID_THRESHOLD,
    ZOOM_STEPS,
)
from snapmock.core.scene import SnapScene
from snapmock.core.theme_manager import current_theme

if TYPE_CHECKING:
    from snapmock.tools.tool_manager import ToolManager

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


class SnapView(QGraphicsView):
    """Extended QGraphicsView with zoom (10%-3200%) and pan support.

    Signals
    -------
    zoom_changed(int)
        Emitted with the new zoom percentage after every zoom change.
    cursor_moved(float, float)
        Emitted with scene coordinates when the mouse moves over the viewport.
    """

    zoom_changed = pyqtSignal(int)
    cursor_moved = pyqtSignal(float, float)
    library_files_dropped = pyqtSignal(list)

    def __init__(self, scene: SnapScene) -> None:
        super().__init__(scene)
        self._zoom_pct: int = ZOOM_DEFAULT
        self._panning: bool = False
        self._pan_start: QPoint = QPoint()
        self._tool_manager: ToolManager | None = None

        # Grid / ruler state
        self._grid_visible: bool = False
        self._grid_size: int = GRID_SIZE_DEFAULT
        self._rulers_visible: bool = False

        # Crosshairs (General UI PRD 3.3): full-width lines through the cursor position
        self._crosshairs_visible: bool = False
        self._crosshair_pos: QPointF | None = None

        # Cached checkerboard tile, rebuilt when the theme or its preferences change
        self._checkerboard_tile: QPixmap | None = None

        # Preferences that override the theme (General UI PRD 11.3); None = theme value
        self._pasteboard_override: QColor | None = None
        self._grid_color_override: QColor | None = None
        self._grid_opacity_override: int | None = None
        self._checkerboard_size: int = CHECKERBOARD_CELL_SIZE
        self._checkerboard_override: tuple[QColor, QColor] | None = None
        self._pixel_grid_threshold: int = ZOOM_PIXEL_GRID_THRESHOLD

        # Ruler widgets (created lazily by set_rulers_visible)
        self._h_ruler: QWidget | None = None
        self._v_ruler: QWidget | None = None
        self._ruler_corner: QWidget | None = None

        # Auto edge scroll
        from PyQt6.QtCore import QTimer

        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(16)
        self._auto_scroll_timer.timeout.connect(self._do_auto_scroll)
        self._auto_scroll_dx: int = 0
        self._auto_scroll_dy: int = 0

        # Zoom animation
        self._zoom_timeline: QTimeLine | None = None

        # Rendering quality
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    # --- typed scene accessor ---

    @property
    def _snap_scene(self) -> SnapScene | None:
        s = self.scene()
        if isinstance(s, SnapScene):
            return s
        return None

    # --- tool manager ---

    def set_tool_manager(self, tool_manager: ToolManager) -> None:
        """Set the tool manager for mouse event delegation."""
        self._tool_manager = tool_manager
        tool_manager.tool_changed.connect(self._apply_tool_cursor)

    def _apply_tool_cursor(self, _tool_id: str = "") -> None:
        """Apply the active tool's cursor to the viewport."""
        vp = self.viewport()
        if vp is None or self._tool_manager is None:
            return
        tool = self._tool_manager.active_tool
        if tool is not None:
            vp.setCursor(tool.cursor)
        else:
            vp.unsetCursor()

    def set_hover_cursor(self, cursor: QCursor | Qt.CursorShape | None) -> None:
        """A cursor for what is under the pointer (PRD 6.6); None returns to the tool's own."""
        if cursor is None:
            self._apply_tool_cursor()
            return
        vp = self.viewport()
        if vp is not None:
            vp.setCursor(cursor)

    # --- grid & ruler visibility ---

    def set_grid_visible(self, visible: bool) -> None:
        self._grid_visible = visible
        vp = self.viewport()
        if vp is not None:
            vp.update()

    def set_grid_size(self, size: int) -> None:
        self._grid_size = max(1, size)
        if self._grid_visible:
            vp = self.viewport()
            if vp is not None:
                vp.update()

    # --- crosshairs (General UI PRD 3.3) ---

    @property
    def crosshairs_visible(self) -> bool:
        return self._crosshairs_visible

    def set_crosshairs_visible(self, visible: bool) -> None:
        """Show or hide the crosshair lines that follow the cursor."""
        self._crosshairs_visible = visible
        if not visible:
            self._crosshair_pos = None
        self._repaint()

    @property
    def crosshair_pos(self) -> QPointF | None:
        """Scene position of the crosshairs, or None while the cursor is off the viewport."""
        return QPointF(self._crosshair_pos) if self._crosshair_pos is not None else None

    def _move_crosshairs(self, scene_pos: QPointF | None) -> None:
        """Repaint the strips of the old and new crosshair lines only."""
        vp = self.viewport()
        if vp is None:
            self._crosshair_pos = scene_pos
            return
        for pos in (self._crosshair_pos, scene_pos):
            if pos is None:
                continue
            vp_pos = self.mapFromScene(pos)
            vp.update(vp_pos.x() - 1, 0, 3, vp.height())
            vp.update(0, vp_pos.y() - 1, vp.width(), 3)
        self._crosshair_pos = scene_pos

    def _draw_crosshairs(self, painter: QPainter, rect: QRectF) -> None:
        pos = self._crosshair_pos
        if pos is None:
            return
        pen = QPen(current_theme().crosshair, 0)
        painter.setPen(pen)
        painter.drawLine(QPointF(rect.left(), pos.y()), QPointF(rect.right(), pos.y()))
        painter.drawLine(QPointF(pos.x(), rect.top()), QPointF(pos.x(), rect.bottom()))

    # --- theme and appearance preferences (General UI PRD 11.3, 13.4) ---

    def apply_theme(self) -> None:
        """Repaint after a theme change; the paint paths read the theme each time."""
        self._checkerboard_tile = None
        if self._ruler_corner is not None:
            self._ruler_corner.setStyleSheet(
                f"background-color: {current_theme().ruler_bg.name()};"
            )
        for ruler in (self._h_ruler, self._v_ruler):
            if ruler is not None:
                ruler.update()
        vp = self.viewport()
        if vp is not None:
            vp.update()

    def set_pasteboard_color(self, color: QColor | None) -> None:
        """Override the theme's pasteboard colour; None returns to the theme."""
        self._pasteboard_override = QColor(color) if color is not None else None
        self._repaint()

    def set_grid_style(self, color: QColor | None, opacity_pct: int | None) -> None:
        """Override the theme's grid colour and/or opacity; None keeps the theme value."""
        self._grid_color_override = QColor(color) if color is not None else None
        self._grid_opacity_override = opacity_pct
        self._repaint()

    def set_checkerboard(self, size: int, colors: tuple[QColor, QColor] | None) -> None:
        """Checkerboard cell size and, optionally, the two colours (None = theme)."""
        self._checkerboard_size = max(1, size)
        self._checkerboard_override = (
            (QColor(colors[0]), QColor(colors[1])) if colors is not None else None
        )
        self._checkerboard_tile = None
        self._repaint()

    def set_pixel_grid_threshold(self, zoom_pct: int) -> None:
        """Zoom percentage at and above which the grid shows every pixel."""
        self._pixel_grid_threshold = max(100, zoom_pct)
        self._repaint()

    @property
    def pasteboard_color(self) -> QColor:
        return QColor(self._pasteboard_override or current_theme().pasteboard)

    def _grid_pens(self) -> tuple[QPen, QPen]:
        theme = current_theme().grid_lines
        base = self._grid_color_override or theme
        alpha = (
            round(self._grid_opacity_override * 2.55)
            if self._grid_opacity_override is not None
            else theme.alpha()
        )
        minor = QColor(base)
        minor.setAlpha(max(0, min(255, alpha)))
        major = QColor(base)
        major.setAlpha(max(0, min(255, round(alpha * 5 / 3))))
        return QPen(minor, 0), QPen(major, 0)

    @property
    def shows_minor_grid_lines(self) -> bool:
        """Minor grid lines draw at and above GRID_MINOR_MIN_ZOOM percent (PRD 6.4)."""
        return self._zoom_pct >= GRID_MINOR_MIN_ZOOM

    def _repaint(self) -> None:
        vp = self.viewport()
        if vp is not None:
            vp.update()

    def set_rulers_visible(self, visible: bool) -> None:
        self._rulers_visible = visible
        self._ensure_rulers()
        if self._h_ruler is not None:
            self._h_ruler.setVisible(visible)
        if self._v_ruler is not None:
            self._v_ruler.setVisible(visible)
        if self._ruler_corner is not None:
            self._ruler_corner.setVisible(visible)
        margin = RULER_SIZE if visible else 0
        self.setViewportMargins(margin, margin, 0, 0)
        self._position_rulers()

    def _ensure_rulers(self) -> None:
        if self._h_ruler is not None:
            return
        from snapmock.ui.ruler_widget import RulerWidget

        self._h_ruler = RulerWidget(Qt.Orientation.Horizontal, self, parent=self)
        self._v_ruler = RulerWidget(Qt.Orientation.Vertical, self, parent=self)
        self._ruler_corner = QWidget(self)
        self._ruler_corner.setFixedSize(RULER_SIZE, RULER_SIZE)
        self._ruler_corner.setStyleSheet(f"background-color: {current_theme().ruler_bg.name()};")
        self._ruler_corner.setVisible(False)

        # Wire signals
        self.cursor_moved.connect(self._update_ruler_cursor)
        self.zoom_changed.connect(self._on_zoom_for_rulers)

    def _position_rulers(self) -> None:
        if self._h_ruler is None:
            return
        vp = self.viewport()
        if vp is None:
            return
        vp_geo = vp.geometry()
        self._h_ruler.setGeometry(
            vp_geo.left(), vp_geo.top() - RULER_SIZE, vp_geo.width(), RULER_SIZE
        )
        self._v_ruler.setGeometry(  # type: ignore[union-attr]
            vp_geo.left() - RULER_SIZE, vp_geo.top(), RULER_SIZE, vp_geo.height()
        )
        self._ruler_corner.setGeometry(  # type: ignore[union-attr]
            vp_geo.left() - RULER_SIZE, vp_geo.top() - RULER_SIZE, RULER_SIZE, RULER_SIZE
        )

    def _update_ruler_cursor(self, x: float, y: float) -> None:
        from snapmock.ui.ruler_widget import RulerWidget

        if isinstance(self._h_ruler, RulerWidget):
            self._h_ruler.set_cursor_pos(x, y)
        if isinstance(self._v_ruler, RulerWidget):
            self._v_ruler.set_cursor_pos(x, y)

    def _on_zoom_for_rulers(self, _pct: int) -> None:
        if self._h_ruler is not None:
            self._h_ruler.update()
        if self._v_ruler is not None:
            self._v_ruler.update()

    # --- zoom ---

    @property
    def zoom_percent(self) -> int:
        return self._zoom_pct

    def set_zoom(self, percent: int) -> None:
        """Set the zoom level to *percent* (clamped to ZOOM_MIN..ZOOM_MAX)."""
        percent = max(ZOOM_MIN, min(ZOOM_MAX, percent))
        if percent == self._zoom_pct:
            return
        factor = percent / self._zoom_pct
        self._zoom_pct = percent
        self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom_pct)

    def set_zoom_centered(self, percent: int, scene_pos: QPoint | None = None) -> None:
        """Set zoom level, keeping *scene_pos* centered under the cursor.

        Falls back to viewport center if *scene_pos* is None.
        """
        percent = max(ZOOM_MIN, min(ZOOM_MAX, percent))
        if percent == self._zoom_pct:
            return
        if scene_pos is not None:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
            old_scene_pt = self.mapToScene(scene_pos)
            factor = percent / self._zoom_pct
            self._zoom_pct = percent
            self.scale(factor, factor)
            new_scene_pt = self.mapToScene(scene_pos)
            delta = new_scene_pt - old_scene_pt
            self.translate(delta.x(), delta.y())
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        else:
            factor = percent / self._zoom_pct
            self._zoom_pct = percent
            self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom_pct)

    def _next_zoom_step(self) -> int:
        """Return the next zoom step above the current zoom level."""
        idx = bisect.bisect_right(ZOOM_STEPS, self._zoom_pct)
        if idx < len(ZOOM_STEPS):
            return ZOOM_STEPS[idx]
        return ZOOM_STEPS[-1]

    def _prev_zoom_step(self) -> int:
        """Return the next zoom step below the current zoom level."""
        idx = bisect.bisect_left(ZOOM_STEPS, self._zoom_pct) - 1
        if idx >= 0:
            return ZOOM_STEPS[idx]
        return ZOOM_STEPS[0]

    def zoom_in(self) -> None:
        self.animate_zoom_to(self._next_zoom_step())

    def zoom_out(self) -> None:
        self.animate_zoom_to(self._prev_zoom_step())

    def zoom_to_rect(self, rect: QRectF) -> None:
        """Zoom and scroll so that *rect* (in scene coordinates) fills the viewport."""
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        t = self.transform()
        self._zoom_pct = max(ZOOM_MIN, min(ZOOM_MAX, int(t.m11() * 100)))
        self.zoom_changed.emit(self._zoom_pct)

    def fit_in_view_all(self) -> None:
        """Fit the canvas rect in the viewport."""
        snap = self._snap_scene
        if snap is not None:
            self.fitInView(snap.canvas_rect, Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        # Derive actual zoom from current transform
        t = self.transform()
        self._zoom_pct = max(ZOOM_MIN, min(ZOOM_MAX, int(t.m11() * 100)))
        self.zoom_changed.emit(self._zoom_pct)

    # --- auto edge scroll ---

    def _check_auto_scroll(self, viewport_pos: QPoint) -> None:
        """Start/stop auto-scroll based on cursor proximity to viewport edges."""
        vp = self.viewport()
        if vp is None:
            self._stop_auto_scroll()
            return
        edge = 20
        vp_rect = vp.rect()
        dx = dy = 0
        dist_left = viewport_pos.x() - vp_rect.left()
        dist_right = vp_rect.right() - viewport_pos.x()
        dist_top = viewport_pos.y() - vp_rect.top()
        dist_bottom = vp_rect.bottom() - viewport_pos.y()

        if dist_left < edge:
            dx = -max(2, int(15 * (1.0 - dist_left / edge)))
        elif dist_right < edge:
            dx = max(2, int(15 * (1.0 - dist_right / edge)))
        if dist_top < edge:
            dy = -max(2, int(15 * (1.0 - dist_top / edge)))
        elif dist_bottom < edge:
            dy = max(2, int(15 * (1.0 - dist_bottom / edge)))

        if dx != 0 or dy != 0:
            self._auto_scroll_dx = dx
            self._auto_scroll_dy = dy
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        else:
            self._stop_auto_scroll()

    def _stop_auto_scroll(self) -> None:
        self._auto_scroll_timer.stop()
        self._auto_scroll_dx = 0
        self._auto_scroll_dy = 0

    def _do_auto_scroll(self) -> None:
        # Stop if cursor has left the viewport (e.g. moved to ruler or toolbar)
        vp = self.viewport()
        if vp is not None and not vp.underMouse():
            self._stop_auto_scroll()
            return
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        if h_bar is not None and self._auto_scroll_dx != 0:
            h_bar.setValue(h_bar.value() + self._auto_scroll_dx)
        if v_bar is not None and self._auto_scroll_dy != 0:
            v_bar.setValue(v_bar.value() + self._auto_scroll_dy)

    # --- animated zoom ---

    def animate_zoom_to(self, target_pct: int, center: QPoint | None = None) -> None:
        """Smoothly animate zoom to *target_pct*."""
        target_pct = max(ZOOM_MIN, min(ZOOM_MAX, target_pct))
        if target_pct == self._zoom_pct:
            return
        # Cancel any running animation
        if self._zoom_timeline is not None:
            self._zoom_timeline.stop()
        start_pct = self._zoom_pct
        self._zoom_timeline = QTimeLine(150)
        self._zoom_timeline.setFrameRange(start_pct, target_pct)
        from PyQt6.QtCore import QEasingCurve

        self._zoom_timeline.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._zoom_timeline.frameChanged.connect(lambda pct: self.set_zoom_centered(pct, center))
        self._zoom_timeline.start()

    # --- drawBackground ---

    def drawBackground(self, painter: QPainter | None, rect: QRectF) -> None:  # noqa: N802
        if painter is None:
            return
        snap = self._snap_scene
        if snap is None:
            super().drawBackground(painter, rect)
            return

        canvas = snap.canvas_rect
        theme = current_theme()

        # 1. Pasteboard fill
        painter.fillRect(rect, self.pasteboard_color)

        # 2. Drop shadow behind canvas
        shadow_rect = canvas.translated(CANVAS_SHADOW_OFFSET, CANVAS_SHADOW_OFFSET)
        painter.fillRect(shadow_rect, theme.canvas_shadow)

        # 3. Canvas background: checkerboard shows through any transparency (PRD 6.2)
        background = snap.background_color
        if background.alpha() < 255:
            painter.save()
            painter.setClipRect(canvas)
            painter.drawTiledPixmap(canvas, self._get_checkerboard_tile())
            painter.restore()
        painter.fillRect(canvas, background)

        # 4. Canvas border (1px)
        painter.setPen(QPen(theme.canvas_border, 0))
        painter.drawRect(canvas)

        # 5. Empty canvas prompt
        if self._scene_has_no_user_items(snap):
            painter.setPen(QPen(theme.empty_canvas_text))
            font = QFont()
            font.setPixelSize(EMPTY_CANVAS_FONT_SIZE)
            painter.setFont(font)
            painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, EMPTY_CANVAS_TEXT)

    def _scene_has_no_user_items(self, snap: SnapScene) -> bool:
        from snapmock.items.base_item import SnapGraphicsItem

        for item in snap.items():
            if isinstance(item, SnapGraphicsItem):
                return False
        return True

    def _get_checkerboard_tile(self) -> QPixmap:
        if self._checkerboard_tile is None:
            cell = self._checkerboard_size
            theme = current_theme()
            color_a, color_b = self._checkerboard_override or (
                theme.checkerboard_a,
                theme.checkerboard_b,
            )
            size = cell * 2
            tile = QPixmap(size, size)
            p = QPainter(tile)
            p.fillRect(0, 0, size, size, color_a)
            p.fillRect(0, 0, cell, cell, color_b)
            p.fillRect(cell, cell, cell, cell, color_b)
            p.end()
            self._checkerboard_tile = tile
        return self._checkerboard_tile

    # --- drawForeground (grid, crosshairs) ---

    def drawForeground(self, painter: QPainter | None, rect: QRectF) -> None:  # noqa: N802
        if painter is None:
            return
        snap = self._snap_scene
        if snap is None:
            return
        if self._grid_visible:
            self._draw_grid(painter, rect, snap)
        if self._crosshairs_visible:
            self._draw_crosshairs(painter, rect)

    def _draw_grid(self, painter: QPainter, rect: QRectF, snap: SnapScene) -> None:
        canvas = snap.canvas_rect
        clip = canvas.intersected(rect)
        if clip.isEmpty():
            return

        zoom_factor = self._zoom_pct / 100.0
        grid_size = self._grid_size
        minor_pen, major_pen = self._grid_pens()

        # Pixel grid at extreme zoom
        if self._zoom_pct >= self._pixel_grid_threshold:
            pixel_screen = zoom_factor
            if pixel_screen >= GRID_MIN_PIXEL_SPACING:
                painter.setPen(minor_pen)
                px_left = int(clip.left())
                px_right = int(clip.right()) + 1
                px_top = int(clip.top())
                px_bottom = int(clip.bottom()) + 1
                for px in range(px_left, px_right):
                    painter.drawLine(QPointF(px, clip.top()), QPointF(px, clip.bottom()))
                for py in range(px_top, px_bottom):
                    painter.drawLine(QPointF(clip.left(), py), QPointF(clip.right(), py))
                return

        # Normal grid: below GRID_MINOR_MIN_ZOOM only the major lines show (PRD 6.4)
        show_minor = self.shows_minor_grid_lines
        pixel_spacing = grid_size * zoom_factor
        if not show_minor:
            pixel_spacing *= GRID_MAJOR_MULTIPLE
        if pixel_spacing < GRID_MIN_PIXEL_SPACING:
            return

        painter.save()

        left = int(clip.left() / grid_size) * grid_size
        top_val = int(clip.top() / grid_size) * grid_size

        x = float(left)
        while x <= clip.right():
            if x >= canvas.left() and x <= canvas.right():
                grid_idx = round(x / grid_size)
                if grid_idx % GRID_MAJOR_MULTIPLE == 0:
                    painter.setPen(major_pen)
                elif show_minor:
                    painter.setPen(minor_pen)
                else:
                    x += grid_size
                    continue
                painter.drawLine(
                    QPointF(x, max(clip.top(), canvas.top())),
                    QPointF(x, min(clip.bottom(), canvas.bottom())),
                )
            x += grid_size

        y = float(top_val)
        while y <= clip.bottom():
            if y >= canvas.top() and y <= canvas.bottom():
                grid_idx = round(y / grid_size)
                if grid_idx % GRID_MAJOR_MULTIPLE == 0:
                    painter.setPen(major_pen)
                elif show_minor:
                    painter.setPen(minor_pen)
                else:
                    y += grid_size
                    continue
                painter.drawLine(
                    QPointF(max(clip.left(), canvas.left()), y),
                    QPointF(min(clip.right(), canvas.right()), y),
                )
            y += grid_size

        painter.restore()

    # --- resize / scroll → ruler reposition ---

    def event(self, event: QEvent | None) -> bool:
        """Give the active tool Tab and Shift+Tab before Qt uses them for focus (PRD 12.3)."""
        if (
            event is not None
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
            and self._tool_manager is not None
            and self._tool_manager.handle_key_press(event)
        ):
            event.accept()
            return True
        return super().event(event)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._position_rulers()

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # noqa: N802
        super().scrollContentsBy(dx, dy)
        if self._h_ruler is not None:
            self._h_ruler.update()
        if self._v_ruler is not None:
            self._v_ruler.update()

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        """Stop auto-scroll and hide the crosshairs when the mouse leaves the viewport."""
        self._stop_auto_scroll()
        if self._crosshair_pos is not None:
            self._move_crosshairs(None)
        super().leaveEvent(event)  # type: ignore[arg-type]

    # --- wheel event (Ctrl+scroll for zoom) ---

    def wheelEvent(self, event: QWheelEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    # --- mouse event routing ---

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        # Middle-mouse pan
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            vp = self.viewport()
            if vp is not None:
                vp.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._pan_start = event.position().toPoint()
            event.accept()
            return
        # Delegate to tool manager
        if self._tool_manager is not None and self._tool_manager.handle_mouse_press(event):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        # Emit cursor position for status bar
        scene_pos = self.mapToScene(event.position().toPoint())
        self.cursor_moved.emit(scene_pos.x(), scene_pos.y())
        if self._crosshairs_visible:
            self._move_crosshairs(scene_pos)

        # Auto edge scroll during active drag operations (mouse button held)
        if (
            self._tool_manager is not None
            and self._tool_manager.active_tool is not None
            and self._tool_manager.active_tool.is_active_operation
            and event.buttons() != Qt.MouseButton.NoButton
        ):
            self._check_auto_scroll(event.position().toPoint())

        # Middle-mouse pan
        if self._panning:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            if h_bar is not None:
                h_bar.setValue(h_bar.value() - delta.x())
            if v_bar is not None:
                v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
            return
        # Delegate to tool manager
        if self._tool_manager is not None and self._tool_manager.handle_mouse_move(event):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        self._stop_auto_scroll()
        # Middle-mouse pan
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self._apply_tool_cursor()
            event.accept()
            return
        # Delegate to tool manager
        if self._tool_manager is not None and self._tool_manager.handle_mouse_release(event):
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        # Delegate to tool manager
        if self._tool_manager is not None and self._tool_manager.handle_mouse_double_click(event):
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    # --- focus loss ---

    def focusOutEvent(self, event: object) -> None:  # noqa: N802
        """Release temporary pan and cancel active tool on focus loss."""
        # Don't cancel if focus moved to a child of our viewport (e.g. inline text editor)
        from PyQt6.QtWidgets import QApplication

        focus_widget = QApplication.focusWidget()
        vp = self.viewport()
        focus_to_child = (
            focus_widget is not None and vp is not None and vp.isAncestorOf(focus_widget)
        )

        if self._panning:
            self._panning = False
            self._apply_tool_cursor()
        # Check if a mouse button is held — indicates a drag in progress.
        # Transient focus loss (e.g. QToolTip on Linux) should not cancel the drag;
        # the drag will complete normally via mouse_release.
        mouse_held = QApplication.mouseButtons() != Qt.MouseButton.NoButton

        if self._tool_manager is not None and not focus_to_child and not mouse_held:
            # Restore space-bar temporary pan if active
            if self._tool_manager._previous_tool_id is not None:  # noqa: SLF001
                self._tool_manager.restore_previous()
            # Cancel active tool operation
            active = self._tool_manager.active_tool
            if active is not None and active.is_active_operation:
                active.cancel()
        self._stop_auto_scroll()
        super().focusOutEvent(event)  # type: ignore[arg-type]

    # --- context menu ---

    def contextMenuEvent(self, event: object) -> None:  # noqa: N802
        from PyQt6.QtGui import QContextMenuEvent

        if isinstance(event, QContextMenuEvent):
            if self._tool_manager is not None and self._tool_manager.handle_context_menu(event):
                event.accept()
                return
        super().contextMenuEvent(event)  # type: ignore[arg-type]

    # --- drag and drop ---

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        mime: QMimeData | None = event.mimeData()
        if mime is not None and mime.hasFormat(LIBRARY_PATHS_MIME):
            event.acceptProposedAction()
            return
        if mime is not None and (self._has_image_urls(mime) or mime.hasImage()):
            # An external image is copied in, so the copy cursor shows (PRD 6.6)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        mime: QMimeData | None = event.mimeData()
        if mime is not None and not mime.hasFormat(LIBRARY_PATHS_MIME):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        mime: QMimeData | None = event.mimeData()
        if mime is None:
            return
        scene_pos = self.mapToScene(event.position().toPoint())

        if mime.hasFormat(LIBRARY_PATHS_MIME):
            # Dragging a library file onto the canvas opens it in a tab
            raw = bytes(mime.data(LIBRARY_PATHS_MIME).data()).decode("utf-8")
            paths = [Path(line) for line in raw.splitlines() if line]
            if paths:
                self.library_files_dropped.emit(paths)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return

        if self._has_image_urls(mime):
            for url in mime.urls():
                path = url.toLocalFile()
                if path:
                    p = Path(path)
                    if p.suffix.lower() in _IMAGE_EXTENSIONS:
                        self._import_dropped_image(p, scene_pos)
            event.acceptProposedAction()
            return

        if mime.hasImage():
            from PyQt6.QtGui import QImage

            image = mime.imageData()
            if isinstance(image, QImage):
                pixmap = QPixmap.fromImage(image)
                self._import_dropped_pixmap(pixmap, scene_pos)
            event.acceptProposedAction()

    def _has_image_urls(self, mime: QMimeData) -> bool:
        if not mime.hasUrls():
            return False
        for url in mime.urls():
            path = url.toLocalFile()
            if path and Path(path).suffix.lower() in _IMAGE_EXTENSIONS:
                return True
        return False

    def _import_dropped_image(self, path: Path, scene_pos: QPointF) -> None:
        snap = self._snap_scene
        if snap is None:
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self._import_dropped_pixmap(pixmap, scene_pos)

    def _import_dropped_pixmap(self, pixmap: QPixmap, scene_pos: QPointF) -> None:
        snap = self._snap_scene
        if snap is None:
            return
        from snapmock.commands.add_item import AddItemCommand
        from snapmock.items.raster_region_item import RasterRegionItem

        item = RasterRegionItem(pixmap=pixmap)
        item.setPos(scene_pos.x() - pixmap.width() / 2, scene_pos.y() - pixmap.height() / 2)
        layer = snap.layer_manager.active_layer
        if layer is not None:
            snap.command_stack.push(AddItemCommand(snap, item, layer.layer_id))
