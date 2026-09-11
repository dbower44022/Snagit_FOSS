"""Marker commands — Renumber All Steps, Change Stamp, and Change Emoji (PRD Section 6).

Numbered Steps, Stamps & Emoji PRD Section 6 defines one command per marker tool beyond
the shared AddItemCommand; each is one undo entry with its own undo (kickoff silence 3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from snapmock.config.constants import DisplayMode
from snapmock.core.command_stack import BaseCommand
from snapmock.items.numbered_step_item import NumberedStepItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


def steps_in_reading_order(scene: SnapScene) -> list[NumberedStepItem]:
    """Every numbered step in the scene, groups' members included, sorted top to bottom
    and then left to right by scene position (PRD 2.3; kickoff silence 14).

    Steps in text mode are left out: they show no number and the counter never advanced
    for them (PRD 2.3, Custom Text Mode).
    """
    steps = [
        item
        for item in scene.all_annotation_items()
        if isinstance(item, NumberedStepItem) and item.display_mode is not DisplayMode.TEXT
    ]
    steps.sort(key=lambda s: (round(s.scenePos().y(), 3), round(s.scenePos().x(), 3)))
    return steps


class RenumberStepsCommand(BaseCommand):
    """Reassign sequential numbers to every step, top to bottom then left to right (6.1)."""

    def __init__(self, scene: SnapScene, starting_number: int) -> None:
        self._starting_number = int(starting_number)
        steps = steps_in_reading_order(scene)
        self._items: list[NumberedStepItem] = steps
        self.item_assignments: list[tuple[str, int, int]] = [
            (item.item_id, item.number_value, self._starting_number + index)
            for index, item in enumerate(steps)
        ]

    @property
    def starting_number(self) -> int:
        return self._starting_number

    @property
    def count(self) -> int:
        """How many steps the command renumbers."""
        return len(self._items)

    def redo(self) -> None:
        for item, (_id, _old, new) in zip(self._items, self.item_assignments):
            item.number_value = new

    def undo(self) -> None:
        for item, (_id, old, _new) in zip(self._items, self.item_assignments):
            item.number_value = old

    @property
    def description(self) -> str:
        return "Renumber all steps"
