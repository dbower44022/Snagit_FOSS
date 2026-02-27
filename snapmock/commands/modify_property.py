"""ModifyPropertyCommand — change a single property on an item (with merge support)."""

from __future__ import annotations

from typing import Any

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem

_PROPERTY_MERGE_BASE = 2000


class ModifyPropertyCommand(BaseCommand):
    """Change one property on a SnapGraphicsItem, with merge support for
    continuous edits (e.g. slider drags)."""

    def __init__(
        self,
        item: SnapGraphicsItem,
        prop_name: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        self._item = item
        self._prop_name = prop_name
        self._old_value = old_value
        self._new_value = new_value

    def redo(self) -> None:
        setattr(self._item, self._prop_name, self._new_value)

    def undo(self) -> None:
        setattr(self._item, self._prop_name, self._old_value)

    @property
    def description(self) -> str:
        return f"Change {self._prop_name}"

    @property
    def merge_id(self) -> int:
        return _PROPERTY_MERGE_BASE + hash(self._prop_name) % 1000

    def merge_with(self, other: BaseCommand) -> bool:
        if (
            isinstance(other, ModifyPropertyCommand)
            and other._item is self._item
            and other._prop_name == self._prop_name
        ):
            self._new_value = other._new_value
            return True
        return False
