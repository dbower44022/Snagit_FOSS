"""MoveTailCommand — undo/redo for callout tail adjustments."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF

from snapmock.core.command_stack import BaseCommand

if TYPE_CHECKING:
    from snapmock.items.callout_item import CalloutItem

_MOVE_TAIL_MERGE_ID = 3002
_MERGE_TIMEOUT_MS = 300


class MoveTailCommand(BaseCommand):
    """Records a tail position/attachment change on a CalloutItem.

    Consecutive tail drags on the same item within 300ms merge into a
    single command for smoother undo behavior.
    """

    def __init__(
        self,
        item: CalloutItem,
        old_tail_tip: QPointF,
        new_tail_tip: QPointF,
        old_tail_base_position: float,
        new_tail_base_position: float,
        old_tail_base_edge: str,
        new_tail_base_edge: str,
        old_control_point: QPointF | None = None,
        new_control_point: QPointF | None = None,
    ) -> None:
        self._item = item
        self._old_tail_tip = QPointF(old_tail_tip)
        self._new_tail_tip = QPointF(new_tail_tip)
        self._old_tail_base_position = old_tail_base_position
        self._new_tail_base_position = new_tail_base_position
        self._old_tail_base_edge = old_tail_base_edge
        self._new_tail_base_edge = new_tail_base_edge
        self._old_control_point = QPointF(old_control_point) if old_control_point else None
        self._new_control_point = QPointF(new_control_point) if new_control_point else None
        self._timestamp = time.monotonic()

    def redo(self) -> None:
        from snapmock.config.constants import TailBaseEdge

        self._item.tail_tip = self._new_tail_tip
        self._item.tail_base_position = self._new_tail_base_position
        try:
            self._item.tail_base_edge = TailBaseEdge(self._new_tail_base_edge)
        except ValueError:
            pass
        self._item.tail_control_point = self._new_control_point

    def undo(self) -> None:
        from snapmock.config.constants import TailBaseEdge

        self._item.tail_tip = self._old_tail_tip
        self._item.tail_base_position = self._old_tail_base_position
        try:
            self._item.tail_base_edge = TailBaseEdge(self._old_tail_base_edge)
        except ValueError:
            pass
        self._item.tail_control_point = self._old_control_point

    @property
    def description(self) -> str:
        return "Move callout tail"

    @property
    def merge_id(self) -> int:
        return _MOVE_TAIL_MERGE_ID

    def merge_with(self, other: BaseCommand) -> bool:
        if not isinstance(other, MoveTailCommand):
            return False
        if other._item is not self._item:
            return False
        elapsed_ms = (other._timestamp - self._timestamp) * 1000
        if elapsed_ms > _MERGE_TIMEOUT_MS:
            return False
        # Merge: keep old values from self, take new values from other
        self._new_tail_tip = other._new_tail_tip
        self._new_tail_base_position = other._new_tail_base_position
        self._new_tail_base_edge = other._new_tail_base_edge
        self._new_control_point = other._new_control_point
        self._timestamp = other._timestamp
        return True
