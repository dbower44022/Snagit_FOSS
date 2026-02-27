"""Raster commands — CropCanvas, RasterCut, ResizeCanvas, ResizeImage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QPointF, QRectF, QSizeF
from PyQt6.QtGui import QColor, QImage

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


class CropCanvasCommand(BaseCommand):
    """Crop the canvas to a specified rectangle, repositioning items."""

    def __init__(self, scene: SnapScene, crop_rect: QRectF) -> None:
        self._scene = scene
        self._crop_rect = QRectF(crop_rect)
        self._old_size = QSizeF(scene.canvas_size)
        self._offset = QPointF(crop_rect.topLeft())
        # Store original item positions for undo
        self._item_positions: list[tuple[SnapGraphicsItem, QPointF]] = []
        for gitem in scene.items():
            if isinstance(gitem, SnapGraphicsItem):
                self._item_positions.append((gitem, QPointF(gitem.pos())))
        # Track items removed because they were entirely outside the crop
        self._removed_items: list[tuple[SnapGraphicsItem, str]] = []

    def redo(self) -> None:
        # Translate all items by -offset
        for gitem, _orig_pos in self._item_positions:
            gitem.setPos(gitem.pos() - self._offset)

        # Remove items entirely outside the new canvas bounds
        new_rect = QRectF(0, 0, self._crop_rect.width(), self._crop_rect.height())
        self._removed_items.clear()
        for gitem, _orig_pos in self._item_positions:
            item_rect = gitem.sceneBoundingRect()
            if not new_rect.intersects(item_rect):
                self._removed_items.append((gitem, gitem.layer_id))
                self._scene.removeItem(gitem)

        self._scene.set_canvas_size(self._crop_rect.size())

    def undo(self) -> None:
        self._scene.set_canvas_size(self._old_size)

        # Re-add removed items
        for gitem, layer_id in self._removed_items:
            gitem.layer_id = layer_id
            self._scene.addItem(gitem)
        self._removed_items.clear()

        # Restore original positions
        for gitem, orig_pos in self._item_positions:
            gitem.setPos(orig_pos)

    @property
    def description(self) -> str:
        return "Crop canvas"


class RasterCutCommand(BaseCommand):
    """Cut (erase) pixels from a raster selection region."""

    def __init__(
        self,
        scene: SnapScene,
        selection_rect: QRectF,
        original_pixels: QImage,
        source_layer_id: str,
    ) -> None:
        self._scene = scene
        self._selection_rect = QRectF(selection_rect)
        self._original_pixels = QImage(original_pixels)
        self._source_layer_id = source_layer_id

    def redo(self) -> None:
        # Erase pixels in the selection area on the source layer
        # This is a simplified implementation — actual pixel erasure
        # requires modifying raster items within the layer
        pass

    def undo(self) -> None:
        # Restore original pixels
        pass

    @property
    def description(self) -> str:
        return "Raster cut"


class ResizeCanvasCommand(BaseCommand):
    """Resize the canvas, repositioning items based on an anchor point."""

    # Anchor grid: 0=top-left, 1=top-center, 2=top-right, etc.
    def __init__(
        self,
        scene: SnapScene,
        new_size: QSizeF,
        anchor: int = 4,  # center
        fill_color: QColor | None = None,
    ) -> None:
        self._scene = scene
        self._new_size = QSizeF(new_size)
        self._old_size = QSizeF(scene.canvas_size)
        self._anchor = anchor
        self._fill_color = fill_color or QColor("white")
        self._item_offsets: list[tuple[SnapGraphicsItem, QPointF]] = []
        for gitem in scene.items():
            if isinstance(gitem, SnapGraphicsItem):
                self._item_offsets.append((gitem, QPointF(gitem.pos())))
        self._offset = self._compute_offset()

    def _compute_offset(self) -> QPointF:
        dw = self._new_size.width() - self._old_size.width()
        dh = self._new_size.height() - self._old_size.height()
        row = self._anchor // 3
        col = self._anchor % 3
        ox = dw * col / 2.0
        oy = dh * row / 2.0
        return QPointF(ox, oy)

    def redo(self) -> None:
        for gitem, _orig in self._item_offsets:
            gitem.setPos(gitem.pos() + self._offset)
        self._scene.set_canvas_size(self._new_size)

    def undo(self) -> None:
        self._scene.set_canvas_size(self._old_size)
        for gitem, orig in self._item_offsets:
            gitem.setPos(orig)

    @property
    def description(self) -> str:
        return "Resize canvas"


class ResizeImageCommand(BaseCommand):
    """Scale all items and the canvas to a new size."""

    def __init__(
        self,
        scene: SnapScene,
        new_size: QSizeF,
    ) -> None:
        self._scene = scene
        self._new_size = QSizeF(new_size)
        self._old_size = QSizeF(scene.canvas_size)
        # Store original transforms
        self._item_states: list[tuple[SnapGraphicsItem, QPointF, Any]] = []
        for gitem in scene.items():
            if isinstance(gitem, SnapGraphicsItem):
                self._item_states.append(
                    (
                        gitem,
                        QPointF(gitem.pos()),
                        gitem.transform(),
                    )
                )

    def redo(self) -> None:
        sx = self._new_size.width() / max(self._old_size.width(), 1)
        sy = self._new_size.height() / max(self._old_size.height(), 1)
        for gitem, orig_pos, _orig_xform in self._item_states:
            gitem.setPos(orig_pos.x() * sx, orig_pos.y() * sy)
        self._scene.set_canvas_size(self._new_size)

    def undo(self) -> None:
        self._scene.set_canvas_size(self._old_size)
        for gitem, orig_pos, orig_xform in self._item_states:
            gitem.setPos(orig_pos)
            gitem.setTransform(orig_xform)

    @property
    def description(self) -> str:
        return "Resize image"
