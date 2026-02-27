"""SelectionOverlay — marching ants border for raster selections."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimeLine
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
)

from snapmock.ui.crop_overlay import CropHandleItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene

HANDLE_SIZE = 8.0


class SelectionOverlay(QGraphicsItemGroup):
    """Animated marching-ants selection overlay with resize handles.

    Supports both rectangular (QRectF) and freeform (QPainterPath) selections.
    """

    def __init__(self, scene: SnapScene) -> None:
        super().__init__()
        self._scene_ref = scene
        self.setZValue(999985)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

        # Dim overlay outside selection (10% black)
        self._dim_path_item = QGraphicsPathItem()
        self._dim_path_item.setPen(QPen(Qt.PenStyle.NoPen))
        self._dim_path_item.setBrush(QBrush(QColor(0, 0, 0, 25)))
        self._dim_path_item.setZValue(999985)
        self.addToGroup(self._dim_path_item)

        # Marching ants border (two layers: black + white dashed)
        self._ants_black = QGraphicsPathItem()
        self._ants_black.setPen(QPen(QColor(0, 0, 0), 1))
        self._ants_black.setBrush(Qt.GlobalColor.transparent)
        self._ants_black.setZValue(999986)
        self.addToGroup(self._ants_black)

        self._ants_white = QGraphicsPathItem()
        pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
        pen.setDashOffset(0)
        self._ants_white.setPen(pen)
        self._ants_white.setBrush(Qt.GlobalColor.transparent)
        self._ants_white.setZValue(999987)
        self.addToGroup(self._ants_white)

        # Resize handles (8 for rectangular)
        handle_positions = [
            "top_left",
            "top_center",
            "top_right",
            "middle_left",
            "middle_right",
            "bottom_left",
            "bottom_center",
            "bottom_right",
        ]
        self._handles: dict[str, CropHandleItem] = {}
        for pos in handle_positions:
            handle = CropHandleItem(pos)
            self._handles[pos] = handle
            self.addToGroup(handle)

        self._selection_rect = QRectF()
        self._selection_path: QPainterPath | None = None
        self._is_freeform = False
        self._show_handles = True

        # Marching ants animation
        self._dash_offset: float = 0.0
        self._timeline = QTimeLine(1000)
        self._timeline.setFrameRange(0, 10)
        self._timeline.setLoopCount(0)  # loop forever
        self._timeline.frameChanged.connect(self._advance_ants)

    def _advance_ants(self, _frame: int) -> None:
        self._dash_offset += 1.0
        pen = self._ants_white.pen()
        pen.setDashOffset(self._dash_offset)
        self._ants_white.setPen(pen)

    def start_animation(self) -> None:
        if self._timeline.state() != QTimeLine.State.Running:
            self._timeline.start()

    def stop_animation(self) -> None:
        self._timeline.stop()

    def set_selection_rect(self, rect: QRectF) -> None:
        """Set a rectangular selection."""
        self._selection_rect = QRectF(rect)
        self._selection_path = None
        self._is_freeform = False
        self._show_handles = True
        self._update_visuals()

    def set_selection_path(self, path: QPainterPath) -> None:
        """Set a freeform selection path."""
        self._selection_path = QPainterPath(path)
        self._selection_rect = path.boundingRect()
        self._is_freeform = True
        self._show_handles = False
        self._update_visuals()

    @property
    def selection_rect(self) -> QRectF:
        return QRectF(self._selection_rect)

    def _update_visuals(self) -> None:
        canvas = self._scene_ref.sceneRect()

        # Build the selection path
        if self._selection_path is not None:
            sel_path = self._selection_path
        else:
            sel_path = QPainterPath()
            sel_path.addRect(self._selection_rect)

        # Dim overlay
        dim_path = QPainterPath()
        dim_path.addRect(canvas)
        dim_path = dim_path.subtracted(sel_path)
        self._dim_path_item.setPath(dim_path)

        # Ants border
        self._ants_black.setPath(sel_path)
        self._ants_white.setPath(sel_path)

        # Handles
        if self._show_handles and not self._selection_rect.isEmpty():
            rect = self._selection_rect
            cx = rect.center().x()
            cy = rect.center().y()
            positions = {
                "top_left": rect.topLeft(),
                "top_center": QPointF(cx, rect.top()),
                "top_right": rect.topRight(),
                "middle_left": QPointF(rect.left(), cy),
                "middle_right": QPointF(rect.right(), cy),
                "bottom_left": rect.bottomLeft(),
                "bottom_center": QPointF(cx, rect.bottom()),
                "bottom_right": rect.bottomRight(),
            }
            for name, point in positions.items():
                self._handles[name].setPos(point)
                self._handles[name].setVisible(True)
        else:
            for handle in self._handles.values():
                handle.setVisible(False)

    def handle_at(self, scene_pos: QPointF) -> str | None:
        """Return which handle name is at *scene_pos*, or None."""
        if not self._show_handles:
            return None
        for name, handle in self._handles.items():
            if not handle.isVisible():
                continue
            hr = handle.sceneBoundingRect()
            hr.adjust(-3, -3, 3, 3)
            if hr.contains(scene_pos):
                return name
        return None

    def is_inside(self, scene_pos: QPointF) -> bool:
        """Return True if *scene_pos* is inside the selection."""
        if self._selection_path is not None:
            return self._selection_path.contains(scene_pos)
        return self._selection_rect.contains(scene_pos)

    def add_to_scene(self) -> None:
        if self.scene() is None:
            self._scene_ref.addItem(self)
        self.start_animation()

    def remove_from_scene(self) -> None:
        self.stop_animation()
        if self.scene() is not None:
            self._scene_ref.removeItem(self)
