"""RemoveItemCommand — removes a SnapGraphicsItem from the scene."""

from __future__ import annotations

from typing import TYPE_CHECKING

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


class RemoveItemCommand(BaseCommand):
    """Remove an item from the scene (undoable)."""

    def __init__(self, scene: SnapScene, item: SnapGraphicsItem) -> None:
        self._scene = scene
        self._item = item
        self._layer_id = item.layer_id

    def redo(self) -> None:
        layer = self._scene.layer_manager.layer_by_id(self._layer_id)
        if layer is not None and self._item.item_id in layer.item_ids:
            layer.item_ids.remove(self._item.item_id)
        self._scene.removeItem(self._item)

    def undo(self) -> None:
        self._scene.addItem(self._item)
        layer = self._scene.layer_manager.layer_by_id(self._layer_id)
        if layer is not None and self._item.item_id not in layer.item_ids:
            layer.item_ids.append(self._item.item_id)

    @property
    def description(self) -> str:
        return f"Remove {self._item.type_name}"
