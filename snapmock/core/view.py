"""SnapView — QGraphicsView with zoom, pan, and tool event routing."""

from __future__ import annotations

import bisect
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import QGraphicsView, QWidget

from snapmock.config.constants import (
    CANVAS_SHADOW_COLOR,
    CANVAS_SHADOW_OFFSET,
    CHECKERBOARD_CELL_SIZE,
    CHECKERBOARD_COLOR_A,
    CHECKERBOARD_COLOR_B,
    EMPTY_CANVAS_FONT_SIZE,
    EMPTY_CANVAS_TEXT,
    EMPTY_CANVAS_TEXT_COLOR,
    GRID_COLOR,
    GRID_COLOR_MAJOR,
    GRID_MAJOR_MULTIPLE,
    GRID_MIN_PIXEL_SPACING,
    GRID_SIZE_DEFAULT,
    PASTEBOARD_COLOR,
    RULER_SIZE,
    ZOOM_DEFAULT,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_PIXEL_GRID_THRESHOLD,
    ZOOM_STEPS,
)
from snapmock.core.scene import SnapScene

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

        # Cached checkerboard tile
        self._checkerboard_tile: QPixmap | None = None

        # Ruler widgets (created lazily by set_rulers_visible)
        self._h_ruler: QWidget | None = None
        self._v_ruler: QWidget | None = None
        self._ruler_corner: QWidget | None = None

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
        from snapmock.config.constants import RULER_BG_COLOR

        self._ruler_corner.setStyleSheet(f"background-color: {RULER_BG_COLOR};")
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
        self.set_zoom(self._next_zoom_step())

    def zoom_out(self) -> None:
        self.set_zoom(self._prev_zoom_step())

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

    # --- drawBackground ---

    def drawBackground(self, painter: QPainter | None, rect: QRectF) -> None:  # noqa: N802
        if painter is None:
            return
        snap = self._snap_scene
        if snap is None:
            super().drawBackground(painter, rect)
            return

        canvas = snap.canvas_rect

        # 1. Pasteboard fill
        painter.fillRect(rect, QColor(PASTEBOARD_COLOR))

        # 2. Drop shadow behind canvas
        shadow_rect = canvas.translated(CANVAS_SHADOW_OFFSET, CANVAS_SHADOW_OFFSET)
        painter.fillRect(shadow_rect, QColor(CANVAS_SHADOW_COLOR))

        # 3. Canvas background (white)
        painter.fillRect(canvas, QColor("white"))

        # 4. Canvas border (1px)
        painter.setPen(QPen(QColor(180, 180, 180), 0))
        painter.drawRect(canvas)

        # 5. Empty canvas prompt
        if self._scene_has_no_user_items(snap):
            painter.setPen(QPen(QColor(EMPTY_CANVAS_TEXT_COLOR)))
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
            size = CHECKERBOARD_CELL_SIZE * 2
            tile = QPixmap(size, size)
            p = QPainter(tile)
            p.fillRect(0, 0, size, size, QColor(CHECKERBOARD_COLOR_A))
            p.fillRect(
                0,
                0,
                CHECKERBOARD_CELL_SIZE,
                CHECKERBOARD_CELL_SIZE,
                QColor(CHECKERBOARD_COLOR_B),
            )
            p.fillRect(
                CHECKERBOARD_CELL_SIZE,
                CHECKERBOARD_CELL_SIZE,
                CHECKERBOARD_CELL_SIZE,
                CHECKERBOARD_CELL_SIZE,
                QColor(CHECKERBOARD_COLOR_B),
            )
            p.end()
            self._checkerboard_tile = tile
        return self._checkerboard_tile

    # --- drawForeground (grid) ---

    def drawForeground(self, painter: QPainter | None, rect: QRectF) -> None:  # noqa: N802
        if painter is None:
            return
        if not self._grid_visible:
            return
        snap = self._snap_scene
        if snap is None:
            return

        canvas = snap.canvas_rect
        clip = canvas.intersected(rect)
        if clip.isEmpty():
            return

        zoom_factor = self._zoom_pct / 100.0
        grid_size = self._grid_size

        # Pixel grid at extreme zoom
        if self._zoom_pct >= ZOOM_PIXEL_GRID_THRESHOLD:
            pixel_screen = zoom_factor
            if pixel_screen >= GRID_MIN_PIXEL_SPACING:
                painter.setPen(QPen(QColor(GRID_COLOR), 0))
                px_left = int(clip.left())
                px_right = int(clip.right()) + 1
                px_top = int(clip.top())
                px_bottom = int(clip.bottom()) + 1
                for px in range(px_left, px_right):
                    painter.drawLine(QPointF(px, clip.top()), QPointF(px, clip.bottom()))
                for py in range(px_top, px_bottom):
                    painter.drawLine(QPointF(clip.left(), py), QPointF(clip.right(), py))
                return

        # Normal grid
        pixel_spacing = grid_size * zoom_factor
        if pixel_spacing < GRID_MIN_PIXEL_SPACING:
            return

        painter.save()
        minor_pen = QPen(QColor(GRID_COLOR), 0)
        major_pen = QPen(QColor(GRID_COLOR_MAJOR), 0)

        left = int(clip.left() / grid_size) * grid_size
        top_val = int(clip.top() / grid_size) * grid_size

        x = float(left)
        while x <= clip.right():
            if x >= canvas.left() and x <= canvas.right():
                grid_idx = round(x / grid_size)
                if grid_idx % GRID_MAJOR_MULTIPLE == 0:
                    painter.setPen(major_pen)
                else:
                    painter.setPen(minor_pen)
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
                else:
                    painter.setPen(minor_pen)
                painter.drawLine(
                    QPointF(max(clip.left(), canvas.left()), y),
                    QPointF(min(clip.right(), canvas.right()), y),
                )
            y += grid_size

        painter.restore()

    # --- resize / scroll → ruler reposition ---

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._position_rulers()

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # noqa: N802
        super().scrollContentsBy(dx, dy)
        if self._h_ruler is not None:
            self._h_ruler.update()
        if self._v_ruler is not None:
            self._v_ruler.update()

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

    # --- drag and drop ---

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        mime: QMimeData | None = event.mimeData()
        if mime is not None and self._has_image_urls(mime):
            event.acceptProposedAction()
            return
        if mime is not None and mime.hasImage():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        mime: QMimeData | None = event.mimeData()
        if mime is None:
            return
        scene_pos = self.mapToScene(event.position().toPoint())

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
