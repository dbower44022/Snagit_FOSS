"""Blur commands — the mask edit of Blur PRD Section 6.1.

``ModifyBlurMaskCommand`` records a freeform blur region's alpha mask before and after one
brush stroke in brush-editing mode (2.8), so an undo returns the mask exactly. The command
carries the region's rectangle with the mask, which 6.1 does not name: the rectangle
follows the painted bounds (freeform blur decision 1), so a stroke that paints outside the
region moves it and an undo must put it back.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage

from snapmock.core.command_stack import BaseCommand
from snapmock.items.blur_item import BlurItem

MaskState = tuple[QRectF, QImage | None]
"""A region's rectangle and its mask together: what one stroke may change."""


def mask_state(item: BlurItem) -> MaskState:
    """The rectangle and mask of *item* as they stand, copied so later edits cannot reach."""
    return QRectF(item.rect), item.alpha_mask


class ModifyBlurMaskCommand(BaseCommand):
    """Set a freeform blur region's mask and rectangle (6.1)."""

    def __init__(self, item: BlurItem, old_state: MaskState, new_state: MaskState) -> None:
        self._item = item
        self._old = old_state
        self._new = new_state

    @property
    def item(self) -> BlurItem:
        return self._item

    def _apply(self, state: MaskState) -> None:
        rect, mask = state
        self._item.rect = QRectF(rect)
        self._item.alpha_mask = None if mask is None else mask.copy()

    def redo(self) -> None:
        self._apply(self._new)

    def undo(self) -> None:
        self._apply(self._old)

    @property
    def description(self) -> str:
        return "Edit blur region mask"
