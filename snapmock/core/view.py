"""SnapView — QGraphicsView with zoom, pan, and tool event routing."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPainter, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

from snapmock.config.constants import ZOOM_DEFAULT, ZOOM_MAX, ZOOM_MIN
from snapmock.core.scene import SnapScene


class SnapView(QGraphicsView):
    """Extended QGraphicsView with zoom (10%-3200%) and pan support.

    Signals
    -------
    zoom_changed(int)
        Emitted with the new zoom percentage after every zoom change.
    """

    zoom_changed = pyqtSignal(int)

    def __init__(self, scene: SnapScene) -> None:
        super().__init__(scene)
        self._zoom_pct: int = ZOOM_DEFAULT
        self._panning: bool = False
        self._pan_start: QPoint = QPoint()

        # Rendering quality
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)

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

    def zoom_in(self) -> None:
        self.set_zoom(int(self._zoom_pct * 1.25))

    def zoom_out(self) -> None:
        self.set_zoom(int(self._zoom_pct / 1.25))

    def fit_in_view_all(self) -> None:
        """Fit the entire scene rect in the viewport."""
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        # Derive actual zoom from current transform
        t = self.transform()
        self._zoom_pct = max(ZOOM_MIN, min(ZOOM_MAX, int(t.m11() * 100)))
        self.zoom_changed.emit(self._zoom_pct)

    # --- wheel event (Ctrl+scroll for zoom) ---

    def wheelEvent(self, event: QWheelEvent | None) -> None:
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

    # --- middle-mouse pan ---

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._pan_start = event.position().toPoint()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
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
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
