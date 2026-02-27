"""Raster commands — CropCanvas, RasterCut, RasterPaste."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QRectF, QSizeF

from snapmock.core.command_stack import BaseCommand

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


class CropCanvasCommand(BaseCommand):
    """Crop the canvas to a specified rectangle."""

    def __init__(self, scene: SnapScene, crop_rect: QRectF) -> None:
        self._scene = scene
        self._crop_rect = QRectF(crop_rect)
        self._old_size = QSizeF(scene.canvas_size)

    def redo(self) -> None:
        self._scene.set_canvas_size(self._crop_rect.size())

    def undo(self) -> None:
        self._scene.set_canvas_size(self._old_size)

    @property
    def description(self) -> str:
        return "Crop canvas"
