"""MoveItemsCommand — undoable movement of one or more items."""

from __future__ import annotations

from PyQt6.QtCore import QPointF

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem

_MOVE_MERGE_ID = 1001


class MoveItemsCommand(BaseCommand):
    """Move items by a delta offset."""

    def __init__(self, items: list[SnapGraphicsItem], delta: QPointF) -> None:
        self._items = list(items)
        self._delta = QPointF(delta)

    def redo(self) -> None:
        for item in self._items:
            item.moveBy(self._delta.x(), self._delta.y())

    def undo(self) -> None:
        for item in self._items:
            item.moveBy(-self._delta.x(), -self._delta.y())

    @property
    def description(self) -> str:
        count = len(self._items)
        return f"Move {count} item{'s' if count != 1 else ''}"

    @property
    def merge_id(self) -> int:
        return _MOVE_MERGE_ID

    def merge_with(self, other: BaseCommand) -> bool:
        if isinstance(other, MoveItemsCommand):
            if [i.item_id for i in self._items] == [i.item_id for i in other._items]:
                self._delta = QPointF(
                    self._delta.x() + other._delta.x(),
                    self._delta.y() + other._delta.y(),
                )
                return True
        return False
