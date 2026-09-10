"""Merge commands — Merge Down, Merge Visible, and Flatten All of General UI PRD 3.4.

One command, :class:`MergeLayersCommand`, serves all three rows (Technical Architecture
PRD 3.7.3; Navigation and Raster Operations follow-up decision 1, option A): the merged
layers are rendered together into one raster region the size of the canvas on the result
layer, every item of every merged layer leaves the scene, the other merged layers leave
the stack, and undo restores the layers, their properties, their items, and the active
layer. Flatten All's result is a new Background layer that replaces every layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QColor, QPixmap

from snapmock.commands.arrange_commands import apply_layer_z_values
from snapmock.core.command_stack import BaseCommand
from snapmock.core.layer import LAYER_TYPE_BACKGROUND, Layer
from snapmock.core.render_engine import RenderEngine
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.raster_region_item import RasterRegionItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene

FLATTENED_LAYER_NAME = "Background"
"""The name of the layer Flatten All leaves (follow-up silence 2)."""


class _MergedLayer:
    """One merged layer as it was: its object, stack index, item order, and items."""

    def __init__(self, layer: Layer, index: int, items: list[SnapGraphicsItem]) -> None:
        self.layer = layer
        self.index = index
        self.item_ids = list(layer.item_ids)
        self.items = items


class MergeLayersCommand(BaseCommand):
    """Composite *layer_ids* into one raster region on the result layer (undoable).

    *layer_ids* are the layers to merge, in any order. With *target_id* the result layer
    is that layer, which must be among *layer_ids*; it keeps its own name, opacity, blend
    mode, type, lock, and visibility, and the other layers' opacity and blend mode are
    baked into the pixels. Without *target_id* (Flatten All) every layer is merged into a
    new Background layer, the canvas colour painted first when it is opaque.
    """

    def __init__(
        self,
        scene: SnapScene,
        layer_ids: list[str],
        target_id: str | None = None,
        *,
        description: str = "Merge layers",
    ) -> None:
        self._scene = scene
        self._mgr = scene.layer_manager
        self._description = description
        order = {layer.layer_id: i for i, layer in enumerate(self._mgr.layers)}
        self._layer_ids = sorted((lid for lid in layer_ids if lid in order), key=order.__getitem__)
        self._target_id = target_id
        self._merged: list[_MergedLayer] = []
        self._result: Layer | None = None
        self._region: RasterRegionItem | None = None
        self._active_before = self._mgr.active_layer_id

    @classmethod
    def flatten_all(cls, scene: SnapScene) -> MergeLayersCommand:
        """Every layer into one new Background layer holding one canvas-sized region."""
        ids = [layer.layer_id for layer in scene.layer_manager.layers]
        return cls(scene, ids, None, description="Flatten All")

    @property
    def result_layer(self) -> Layer | None:
        return self._result

    @property
    def region(self) -> RasterRegionItem | None:
        return self._region

    def _render(self) -> RasterRegionItem:
        background: QColor | None = None
        if self._target_id is None:
            colour = self._scene.background_color
            background = colour if colour.alpha() == 255 else None
        image = RenderEngine(self._scene).render_layers_composite(
            self._layer_ids, plain_layer_id=self._target_id, background=background
        )
        return RasterRegionItem(pixmap=QPixmap.fromImage(image))

    def redo(self) -> None:
        if not self._merged:
            # Top-level items: a group is rendered with its members and leaves with them
            by_layer: dict[str, list[SnapGraphicsItem]] = {lid: [] for lid in self._layer_ids}
            for item in self._scene.annotation_items():
                if item.layer_id in by_layer:
                    by_layer[item.layer_id].append(item)
            for lid in self._layer_ids:
                layer = self._mgr.layer_by_id(lid)
                if layer is not None:
                    self._merged.append(
                        _MergedLayer(layer, self._mgr.index_of(lid), by_layer[lid])
                    )
            self._region = self._render()
            if self._target_id is None:
                self._result = Layer(name=FLATTENED_LAYER_NAME, layer_type=LAYER_TYPE_BACKGROUND)
            else:
                self._result = self._mgr.layer_by_id(self._target_id)
        result = self._result
        region = self._region
        if result is None or region is None:
            return

        for merged in self._merged:
            for item in merged.items:
                if item.scene() is self._scene:
                    self._scene.removeItem(item)
        if self._target_id is None:
            # The new layer goes in before the old ones leave: the last layer never leaves
            self._mgr.insert_layer(result, 0)
        for merged in self._merged:
            if merged.layer is not result:
                merged.layer.item_ids = []
                self._mgr.remove_layer(merged.layer.layer_id)
        result.item_ids = [region.item_id]
        region.layer_id = result.layer_id
        self._scene.addItem(region)
        apply_layer_z_values(self._scene, result.layer_id)
        self._mgr.set_active(result.layer_id)

    def undo(self) -> None:
        result = self._result
        region = self._region
        if result is None or region is None:
            return
        if region.scene() is self._scene:
            self._scene.removeItem(region)
        result.item_ids = []
        # The merged layers return at their places, lowest first. Flatten All's originals
        # go in above its new Background layer in their order (nothing is inserted below a
        # Background layer) and the new layer leaves once they are back, so the stack is
        # never empty and the originals end up at their old indices.
        for merged in sorted(self._merged, key=lambda m: m.index):
            if merged.layer is not result:
                index = self._mgr.count if self._target_id is None else merged.index
                self._mgr.insert_layer(merged.layer, index)
        if self._target_id is None:
            self._mgr.remove_layer(result.layer_id)
        for merged in self._merged:
            merged.layer.item_ids = list(merged.item_ids)
            for item in merged.items:
                if item.scene() is not self._scene:
                    self._scene.addItem(item)
            apply_layer_z_values(self._scene, merged.layer.layer_id)
        if self._mgr.layer_by_id(self._active_before) is not None:
            self._mgr.set_active(self._active_before)

    @property
    def description(self) -> str:
        return self._description
