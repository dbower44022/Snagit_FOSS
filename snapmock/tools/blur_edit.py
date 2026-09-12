"""Brush editing of a freeform blur region (Blur PRD 2.8).

Brush-editing mode is the Select tool's second mode, beside the point-editing mode of
``tools/point_edit.py`` (freeform blur silence 3): a double-click on a Freeform blur region
starts a :class:`BlurBrushSession` for it, painting adds blur area and Alt+painting takes it
away, the cursor is the brush circle, and Enter or Escape leaves. Each stroke pushes one
:class:`~snapmock.commands.blur_commands.ModifyBlurMaskCommand` (6.1), so an undo returns
the mask.

The mask is painted in the item's own coordinates, so a rotated or flipped region is painted
where it is seen. Painting outside the region grows its rectangle with the painted bounds;
erasing never shrinks it, so the handles do not jump while the brush is working.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRect, QRectF
from PyQt6.QtGui import QImage, QPainter

from snapmock.commands.blur_commands import MaskState, ModifyBlurMaskCommand, mask_state
from snapmock.config.constants import (
    BLUR_BRUSH_SIZE_MAX,
    BLUR_BRUSH_SIZE_MIN,
    DEFAULT_BLUR_BRUSH_SIZE,
    BlurRegionShape,
)
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.blur_item import BlurItem
from snapmock.items.mask_utils import blank_mask, paint_stroke
from snapmock.tools.point_edit import mirror_point

HINT = "Paint to add blur. Alt+paint to erase. Enter/Escape: finish."
"""The status bar text while brush editing lasts (2.11)."""


def brush_editable(item: SnapGraphicsItem | None) -> bool:
    """Whether a double-click on *item* starts brush editing: only a Freeform region does."""
    return isinstance(item, BlurItem) and item.region_shape is BlurRegionShape.FREEFORM


class BlurBrushSession:
    """The brush editing of one freeform blur region."""

    def __init__(self, item: BlurItem, brush_size: float = DEFAULT_BLUR_BRUSH_SIZE) -> None:
        self.item = item
        self._brush_size = DEFAULT_BLUR_BRUSH_SIZE
        self.brush_size = brush_size
        self._before: MaskState | None = None
        self._erasing = False
        self._last: QPointF | None = None

    @property
    def status_hint(self) -> str:
        return HINT

    @property
    def brush_size(self) -> float:
        """The brush's diameter in the region's own pixels, 5 to 200 (2.5)."""
        return self._brush_size

    @brush_size.setter
    def brush_size(self, value: float) -> None:
        try:
            size = float(value)
        except (TypeError, ValueError):
            size = DEFAULT_BLUR_BRUSH_SIZE
        self._brush_size = max(BLUR_BRUSH_SIZE_MIN, min(BLUR_BRUSH_SIZE_MAX, size))

    @property
    def painting(self) -> bool:
        return self._before is not None

    @property
    def erasing(self) -> bool:
        return self._erasing

    def to_local(self, scene_pos: QPointF) -> QPointF:
        """The region's own point that is painted at *scene_pos*."""
        return mirror_point(self.item, self.item.mapFromScene(scene_pos))

    # --- a stroke ---

    def begin_stroke(self, scene_pos: QPointF, *, erase: bool = False) -> None:
        """Start a stroke at *scene_pos*; *erase* takes blur area away instead (2.8)."""
        self._before = mask_state(self.item)
        self._erasing = erase
        point = self.to_local(scene_pos)
        self._last = point
        self._paint(point, point)

    def stroke_to(self, scene_pos: QPointF) -> None:
        if self._before is None:
            return
        point = self.to_local(scene_pos)
        last = self._last if self._last is not None else point
        self._paint(last, point)
        self._last = point

    def end_stroke(self) -> ModifyBlurMaskCommand | None:
        """The command for the stroke that just ended, or None when nothing changed."""
        before = self._before
        self._before = None
        self._last = None
        self._erasing = False
        if before is None:
            return None
        after = mask_state(self.item)
        if before[0] == after[0] and _same_mask(before[1], after[1]):
            return None
        return ModifyBlurMaskCommand(self.item, before, after)

    def cancel_stroke(self) -> None:
        """Put the mask back as it was before the stroke began (Escape mid-stroke)."""
        before = self._before
        self._before = None
        self._last = None
        self._erasing = False
        if before is not None:
            self.item.rect = QRectF(before[0])
            self.item.alpha_mask = None if before[1] is None else before[1].copy()

    # --- painting ---

    def _paint(self, start: QPointF, end: QPointF) -> None:
        item = self.item
        rect = item.rect
        reach = self._brush_size / 2.0 + 2.0
        segment = QRectF(start, end).normalized().adjusted(-reach, -reach, reach, reach)
        if self._erasing:
            area = rect  # erasing never shrinks the region
        else:
            area = _aligned(rect.united(segment) if rect.isValid() else segment)
        mask = item.alpha_mask
        if mask is None or area != rect:
            grown = blank_mask(max(1, round(area.width())), max(1, round(area.height())))
            if mask is not None:
                offset = rect.topLeft() - area.topLeft()
                painter_target = QRect(
                    round(offset.x()), round(offset.y()), mask.width(), mask.height()
                )
                painter = QPainter(grown)
                painter.drawImage(painter_target, mask)
                painter.end()
            mask = grown
        origin = area.topLeft()
        paint_stroke(mask, start - origin, end - origin, self._brush_size, erase=self._erasing)
        item.rect = area
        item.alpha_mask = mask


def _aligned(rect: QRectF) -> QRectF:
    aligned = rect.toAlignedRect()
    return QRectF(aligned)


def _same_mask(a: object, b: object) -> bool:
    if a is None and b is None:
        return True
    if not isinstance(a, QImage) or not isinstance(b, QImage):
        return False
    return bool(a == b)
