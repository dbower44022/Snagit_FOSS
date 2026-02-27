"""Layer commands — undoable layer add, remove, reorder, property change."""

from __future__ import annotations

from typing import TYPE_CHECKING

from snapmock.core.command_stack import BaseCommand
from snapmock.core.layer import Layer

if TYPE_CHECKING:
    from snapmock.core.layer_manager import LayerManager


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
    """Change a layer property (visibility, lock, opacity, name)."""

    def __init__(
        self,
        manager: LayerManager,
        layer_id: str,
        prop_name: str,
        old_value: object,
        new_value: object,
    ) -> None:
        self._mgr = manager
        self._layer_id = layer_id
        self._prop_name = prop_name
        self._old_value = old_value
        self._new_value = new_value

    def _apply(self, value: object) -> None:
        if self._prop_name == "visible":
            self._mgr.set_visibility(self._layer_id, bool(value))
        elif self._prop_name == "locked":
            self._mgr.set_locked(self._layer_id, bool(value))
        elif self._prop_name == "opacity":
            self._mgr.set_opacity(self._layer_id, float(value))  # type: ignore[arg-type]
        elif self._prop_name == "name":
            self._mgr.rename_layer(self._layer_id, str(value))

    def redo(self) -> None:
        self._apply(self._new_value)

    def undo(self) -> None:
        self._apply(self._old_value)

    @property
    def description(self) -> str:
        return f"Change layer {self._prop_name}"
