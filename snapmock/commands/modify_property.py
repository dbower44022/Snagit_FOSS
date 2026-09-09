"""Property commands — change one property on one item or on a whole selection."""

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


class ModifyPropertiesCommand(BaseCommand):
    """Set one property to one value on every item of a selection (General UI PRD 8.6).

    One undo entry restores each item's own previous value. Consecutive edits
    of the same property on the same items merge, so a slider drag stays one
    entry.
    """

    def __init__(self, items: list[SnapGraphicsItem], prop_name: str, new_value: Any) -> None:
        self._items = list(items)
        self._prop_name = prop_name
        self._old_values = [getattr(item, prop_name) for item in self._items]
        self._new_value = new_value

    def redo(self) -> None:
        for item in self._items:
            setattr(item, self._prop_name, self._new_value)

    def undo(self) -> None:
        for item, old in zip(self._items, self._old_values):
            setattr(item, self._prop_name, old)

    @property
    def description(self) -> str:
        return f"Change {self._prop_name} on {len(self._items)} items"

    @property
    def merge_id(self) -> int:
        return _PROPERTY_MERGE_BASE + 1000 + hash(self._prop_name) % 1000

    def merge_with(self, other: BaseCommand) -> bool:
        if (
            isinstance(other, ModifyPropertiesCommand)
            and other._prop_name == self._prop_name
            and len(other._items) == len(self._items)
            and all(a is b for a, b in zip(other._items, self._items))
        ):
            self._new_value = other._new_value
            return True
        return False
