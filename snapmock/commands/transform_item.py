"""TransformItemCommand — record a before/after QTransform for an item."""

from __future__ import annotations

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QTransform

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem


class TransformItemCommand(BaseCommand):
    """Undoable transform of a single item (position, rotation, scale)."""

    def __init__(
        self,
        item: SnapGraphicsItem,
        old_pos: QPointF,
        new_pos: QPointF,
        old_transform: QTransform,
        new_transform: QTransform,
    ) -> None:
        self._item = item
        self._old_pos = QPointF(old_pos)
        self._new_pos = QPointF(new_pos)
        self._old_transform = QTransform(old_transform)
        self._new_transform = QTransform(new_transform)

    def redo(self) -> None:
        self._item.setPos(self._new_pos)
        self._item.setTransform(self._new_transform)

    def undo(self) -> None:
        self._item.setPos(self._old_pos)
        self._item.setTransform(self._old_transform)

    @property
    def description(self) -> str:
        return f"Transform {self._item.type_name}"
