"""Eyedropper commands — the colour apply of Blur PRD Section 6.2.

``ApplyEyedropperColorCommand`` sets one colour property to one sampled colour on every
selected item, remembering each item's own previous value, so one undo entry returns all
of them. It replaces the macro of property commands the Apply to Stroke and Apply to Fill
buttons pushed before this work: 6.2 defines exactly this command, with its own
description.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem


class ApplyEyedropperColorCommand(BaseCommand):
    """Apply a sampled colour to the selected items' target property (6.2)."""

    def __init__(
        self, items: list[SnapGraphicsItem], property_name: str, new_value: QColor
    ) -> None:
        # Only the items that carry the target as a colour: a name a non-colour property
        # answers to is not one this command can set.
        self._items = [
            item for item in items if isinstance(getattr(item, property_name, None), QColor)
        ]
        self._property_name = property_name
        self._new_value = QColor(new_value)
        self._old_values: dict[str, QColor] = {
            item.item_id: QColor(getattr(item, property_name)) for item in self._items
        }

    @property
    def items(self) -> list[SnapGraphicsItem]:
        """The items the command reaches: those carrying the target property as a colour."""
        return list(self._items)

    @property
    def property_name(self) -> str:
        return self._property_name

    def redo(self) -> None:
        for item in self._items:
            setattr(item, self._property_name, QColor(self._new_value))

    def undo(self) -> None:
        for item in self._items:
            old = self._old_values.get(item.item_id)
            if old is not None:
                setattr(item, self._property_name, QColor(old))

    @property
    def description(self) -> str:
        return "Apply eyedropper color"
