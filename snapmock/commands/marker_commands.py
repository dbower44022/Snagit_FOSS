"""Marker commands — Renumber All Steps, Change Stamp, and Change Emoji (PRD Section 6).

Numbered Steps, Stamps & Emoji PRD Section 6 defines one command per marker tool beyond
the shared AddItemCommand; each is one undo entry with its own undo (kickoff silence 3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from snapmock.config.constants import DisplayMode
from snapmock.core.command_stack import BaseCommand
from snapmock.items.emoji_item import EmojiItem
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.items.stamp_item import StampItem

if TYPE_CHECKING:
    from snapmock.core.emoji_data import SkinTone
    from snapmock.core.scene import SnapScene
    from snapmock.core.stamp_library import StampInfo


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


class ChangeStampCommand(BaseCommand):
    """Replace a stamp item's stamp (PRD 6.2): id, SVG, colorizable flag, and source."""

    def __init__(self, item: StampItem, new_info: StampInfo, new_svg: str | None) -> None:
        self._item = item
        self._old_state = item.stamp_state()
        self._new_info = new_info
        self._new_svg = new_svg
        self._new_state: dict[str, object] | None = None

    @property
    def item_id(self) -> str:
        return self._item.item_id

    @property
    def old_stamp_id(self) -> str:
        return str(self._old_state["stamp_id"])

    @property
    def new_stamp_id(self) -> str:
        return self._new_info.id

    def redo(self) -> None:
        if self._new_state is None:
            self._item.set_stamp(self._new_info, self._new_svg)
            self._new_state = self._item.stamp_state()
        else:
            self._item.apply_stamp_state(self._new_state)

    def undo(self) -> None:
        self._item.apply_stamp_state(self._old_state)

    @property
    def description(self) -> str:
        return f"Change stamp to {self._new_info.name}"


class ChangeEmojiCommand(BaseCommand):
    """Replace an emoji item's emoji (PRD 6.3): character, name, and skin tone."""

    def __init__(self, item: EmojiItem, new_char: str, new_name: str | None = None) -> None:
        from snapmock.core.emoji_data import emoji_data, skin_tone_of

        self._item = item
        self.old_emoji_char = item.emoji_char
        self.old_emoji_name = item.emoji_name
        self.old_skin_tone: SkinTone = item.skin_tone
        self.new_emoji_char = new_char
        self.new_emoji_name = new_name if new_name is not None else emoji_data().name_of(new_char)
        self.new_skin_tone: SkinTone = skin_tone_of(new_char)

    @property
    def item_id(self) -> str:
        return self._item.item_id

    def redo(self) -> None:
        self._item.set_emoji(self.new_emoji_char, self.new_emoji_name)

    def undo(self) -> None:
        self._item.set_emoji(self.old_emoji_char, self.old_emoji_name)

    @property
    def description(self) -> str:
        return f"Change emoji to {self.new_emoji_name}"
