"""MoveItemToLayerCommand — move items between layers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


class MoveItemToLayerCommand(BaseCommand):
    """Move one or more items to a different layer."""

    def __init__(
        self, scene: SnapScene, items: list[SnapGraphicsItem], target_layer_id: str
    ) -> None:
        self._scene = scene
        self._items = list(items)
        self._target_layer_id = target_layer_id
        self._original_layer_ids: list[str] = [item.layer_id for item in items]

    def redo(self) -> None:
        lm = self._scene.layer_manager
        target_layer = lm.layer_by_id(self._target_layer_id)
        if target_layer is None:
            return
        for item in self._items:
            old_layer = lm.layer_by_id(item.layer_id)
            if old_layer is not None and item.item_id in old_layer.item_ids:
                old_layer.item_ids.remove(item.item_id)
            item.layer_id = self._target_layer_id
            if item.item_id not in target_layer.item_ids:
                target_layer.item_ids.append(item.item_id)

    def undo(self) -> None:
        lm = self._scene.layer_manager
        target_layer = lm.layer_by_id(self._target_layer_id)
        for item, orig_id in zip(self._items, self._original_layer_ids):
            if target_layer is not None and item.item_id in target_layer.item_ids:
                target_layer.item_ids.remove(item.item_id)
            item.layer_id = orig_id
            orig_layer = lm.layer_by_id(orig_id)
            if orig_layer is not None and item.item_id not in orig_layer.item_ids:
                orig_layer.item_ids.append(item.item_id)

    @property
    def description(self) -> str:
        return "Move to layer"
