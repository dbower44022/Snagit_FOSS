"""Layer commands — undoable layer add, remove, reorder, property change."""

from __future__ import annotations

from typing import TYPE_CHECKING

from snapmock.core.command_stack import BaseCommand
from snapmock.core.layer import Layer
from snapmock.items.base_item import SnapGraphicsItem

if TYPE_CHECKING:
    from snapmock.core.layer_manager import LayerManager
    from snapmock.core.scene import SnapScene


class AddLayerCommand(BaseCommand):
    """Add a new layer."""

    def __init__(self, manager: LayerManager, name: str, index: int | None = None) -> None:
        self._mgr = manager
        self._name = name
        self._index = index
        self._layer: Layer | None = None

    def redo(self) -> None:
        if self._layer is None:
            self._layer = self._mgr.add_layer(self._name, self._index)
        else:
            self._mgr.insert_layer(self._layer, self._index or self._mgr.count)

    def undo(self) -> None:
        if self._layer is not None:
            self._mgr.remove_layer(self._layer.layer_id)

    @property
    def description(self) -> str:
        return f'Add layer "{self._name}"'


class DuplicateLayerCommand(BaseCommand):
    """Duplicate a layer and every item on it, above the original (General UI PRD 3.4)."""

    def __init__(self, scene: SnapScene, layer_id: str) -> None:
        self._scene = scene
        self._mgr = scene.layer_manager
        self._source_id = layer_id
        self._layer: Layer | None = None
        self._clones: list[SnapGraphicsItem] = []

    def redo(self) -> None:
        source = self._mgr.layer_by_id(self._source_id)
        if source is None:
            return
        if self._layer is None:
            self._layer = source.clone()
            self._layer.item_ids = []
            # Top-level items: a group's clone carries its members
            self._clones = [
                item.clone()
                for item in self._scene.annotation_items()
                if item.layer_id == self._source_id
            ]
        self._mgr.insert_layer(self._layer, self._mgr.index_of(self._source_id) + 1)
        for clone in self._clones:
            clone.layer_id = self._layer.layer_id
            self._scene.addItem(clone)
            if clone.item_id not in self._layer.item_ids:
                self._layer.item_ids.append(clone.item_id)
        self._mgr.set_active(self._layer.layer_id)

    def undo(self) -> None:
        if self._layer is None:
            return
        for clone in self._clones:
            if clone.scene() is self._scene:
                self._scene.removeItem(clone)
        self._layer.item_ids.clear()
        self._mgr.remove_layer(self._layer.layer_id)
        self._mgr.set_active(self._source_id)

    @property
    def description(self) -> str:
        return "Duplicate layer"


class RemoveLayerCommand(BaseCommand):
    """Remove a layer (undoable)."""

    def __init__(self, manager: LayerManager, layer_id: str) -> None:
        self._mgr = manager
        self._layer_id = layer_id
        self._layer: Layer | None = None
        self._index: int = -1

    def redo(self) -> None:
        self._index = self._mgr.index_of(self._layer_id)
        self._layer = self._mgr.remove_layer(self._layer_id)

    def undo(self) -> None:
        if self._layer is not None and self._index >= 0:
            self._mgr.insert_layer(self._layer, self._index)

    @property
    def description(self) -> str:
        return "Remove layer"


class ReorderLayerCommand(BaseCommand):
    """Move a layer to a new position in the stack."""

    def __init__(self, manager: LayerManager, layer_id: str, new_index: int) -> None:
        self._mgr = manager
        self._layer_id = layer_id
        self._new_index = new_index
        self._old_index: int = -1

    def redo(self) -> None:
        self._old_index = self._mgr.index_of(self._layer_id)
        self._mgr.move_layer(self._layer_id, self._new_index)

    def undo(self) -> None:
        self._mgr.move_layer(self._layer_id, self._old_index)

    @property
    def description(self) -> str:
        return "Reorder layers"


class ChangeLayerPropertyCommand(BaseCommand):
    """Change a layer property (visibility, lock, opacity, name, blend mode, layer type).

    With *mergeable* set, consecutive changes to the same property of the
    same layer collapse into one undo entry (the Layer Panel's opacity slider).
    """

    def __init__(
        self,
        manager: LayerManager,
        layer_id: str,
        prop_name: str,
        old_value: object,
        new_value: object,
        *,
        mergeable: bool = False,
    ) -> None:
        self._mgr = manager
        self._layer_id = layer_id
        self._prop_name = prop_name
        self._old_value = old_value
        self._new_value = new_value
        self._mergeable = mergeable

    @property
    def merge_id(self) -> int:
        if not self._mergeable:
            return 0
        return hash((self._layer_id, self._prop_name)) & 0x7FFFFFFF or 1

    def merge_with(self, other: BaseCommand) -> bool:
        if not isinstance(other, ChangeLayerPropertyCommand) or not other._mergeable:
            return False
        if other._layer_id != self._layer_id or other._prop_name != self._prop_name:
            return False
        self._new_value = other._new_value
        return True

    def _apply(self, value: object) -> None:
        if self._prop_name == "visible":
            self._mgr.set_visibility(self._layer_id, bool(value))
        elif self._prop_name == "locked":
            self._mgr.set_locked(self._layer_id, bool(value))
        elif self._prop_name == "opacity":
            self._mgr.set_opacity(self._layer_id, float(value))  # type: ignore[arg-type]
        elif self._prop_name == "name":
            self._mgr.rename_layer(self._layer_id, str(value))
        elif self._prop_name == "blend_mode":
            self._mgr.set_blend_mode(self._layer_id, str(value))
        elif self._prop_name == "layer_type":
            self._mgr.set_layer_type(self._layer_id, str(value))

    def redo(self) -> None:
        self._apply(self._new_value)

    def undo(self) -> None:
        self._apply(self._old_value)

    @property
    def description(self) -> str:
        return f"Change layer {self._prop_name}"
