"""Importer — import images into the scene."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtGui import QPixmap

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.raster_region_item import RasterRegionItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


def import_image(scene: SnapScene, path: Path) -> RasterRegionItem | None:
    """Import an image file as a RasterRegionItem on the active layer."""
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None

    item = RasterRegionItem(pixmap=pixmap)
    layer = scene.layer_manager.active_layer
    if layer is None:
        return None

    cmd = AddItemCommand(scene, item, layer.layer_id)
    scene.command_stack.push(cmd)
    return item
