"""Importer — import images into the scene."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPixmap

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.layer_commands import CreateBackgroundLayerCommand
from snapmock.items.raster_region_item import RasterRegionItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


def takes_background(scene: SnapScene) -> bool:
    """True while an image placed on *scene* becomes its Background layer: the project has
    no Background layer and no annotation item (follow-up step 5, silences 5 and 6)."""
    return scene.layer_manager.background_layer is None and not scene.annotation_items()


def place_image(scene: SnapScene, pixmap: QPixmap, top_left: QPointF) -> RasterRegionItem | None:
    """Put *pixmap* on *scene* as one undo step and return its item.

    On a project with no Background layer and no annotation item the image becomes a
    Background layer at the bottom of the stack and the canvas takes its size (General UI
    PRD 6.2, 16.1, 17.4). Otherwise it is a raster region on the active layer with its
    top-left corner at *top_left*, as before this work. None when there is no active layer.
    """
    if pixmap.isNull():
        return None
    if takes_background(scene):
        background = CreateBackgroundLayerCommand(scene, pixmap)
        scene.command_stack.push(background)
        return background.item
    layer = scene.layer_manager.active_layer
    if layer is None:
        return None
    item = RasterRegionItem(pixmap=pixmap)
    item.setPos(top_left)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def import_image(scene: SnapScene, path: Path) -> RasterRegionItem | None:
    """Import an image file (File > Import Image): the background, or a region at the origin."""
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return place_image(scene, pixmap, QPointF(0, 0))
