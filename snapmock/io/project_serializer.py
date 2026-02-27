"""ProjectSerializer — save/load .smk ZIP archives."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from snapmock.config.constants import APP_VERSION, PROJECT_FORMAT_VERSION
from snapmock.core.layer import Layer
from snapmock.core.scene import SnapScene
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.blur_item import BlurItem
from snapmock.items.callout_item import CalloutItem
from snapmock.items.ellipse_item import EllipseItem
from snapmock.items.freehand_item import FreehandItem
from snapmock.items.highlight_item import HighlightItem
from snapmock.items.line_item import LineItem
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem

ITEM_REGISTRY: dict[str, type[SnapGraphicsItem]] = {
    "RectangleItem": RectangleItem,
    "EllipseItem": EllipseItem,
    "LineItem": LineItem,
    "ArrowItem": ArrowItem,
    "TextItem": TextItem,
    "FreehandItem": FreehandItem,
    "CalloutItem": CalloutItem,
    "HighlightItem": HighlightItem,
    "BlurItem": BlurItem,
    "NumberedStepItem": NumberedStepItem,
}


def save_project(scene: SnapScene, path: Path) -> None:
    """Save the scene to a .smk ZIP archive."""
    manifest: dict[str, Any] = {
        "format_version": PROJECT_FORMAT_VERSION,
        "app_version": APP_VERSION,
        "canvas": {
            "width": scene.canvas_size.width(),
            "height": scene.canvas_size.height(),
        },
    }

    layers_data: list[dict[str, Any]] = []
    items_data: list[dict[str, Any]] = []

    for layer in scene.layer_manager.layers:
        layers_data.append({
            "layer_id": layer.layer_id,
            "name": layer.name,
            "visible": layer.visible,
            "locked": layer.locked,
            "opacity": layer.opacity,
            "item_ids": layer.item_ids,
        })

    # Serialize all items from the scene
    for qitem in scene.items():
        if isinstance(qitem, SnapGraphicsItem):
            items_data.append(qitem.serialize())

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("layers.json", json.dumps(layers_data, indent=2))
        zf.writestr("items.json", json.dumps(items_data, indent=2))


def load_project(path: Path) -> SnapScene:
    """Load a .smk ZIP archive and reconstruct the scene."""
    with zipfile.ZipFile(path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        layers_data = json.loads(zf.read("layers.json"))
        items_data = json.loads(zf.read("items.json"))

    canvas = manifest.get("canvas", {})
    scene = SnapScene(
        width=int(canvas.get("width", 1920)),
        height=int(canvas.get("height", 1080)),
    )
    # Remove the default layer
    default_layer = scene.layer_manager.active_layer
    if default_layer is not None:
        scene.layer_manager._layers.clear()  # noqa: SLF001

    # Reconstruct layers
    for ld in layers_data:
        layer = Layer(
            name=ld["name"],
            layer_id=ld["layer_id"],
            visible=ld.get("visible", True),
            locked=ld.get("locked", False),
            opacity=ld.get("opacity", 1.0),
            item_ids=ld.get("item_ids", []),
        )
        scene.layer_manager.insert_layer(layer, scene.layer_manager.count)

    if scene.layer_manager.count > 0:
        scene.layer_manager.set_active(scene.layer_manager.layers[0].layer_id)

    # Reconstruct items
    for item_data in items_data:
        item_type = item_data.get("type", "")
        cls = ITEM_REGISTRY.get(item_type)
        if cls is not None:
            item = cls.deserialize(item_data)
            scene.addItem(item)

    scene.command_stack.clear()
    scene.command_stack.mark_clean()
    return scene
