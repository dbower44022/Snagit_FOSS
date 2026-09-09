"""Guides — user-placed horizontal and vertical reference lines (General UI PRD 6.5).

A guide is an orientation and a scene coordinate. The list lives on the
:class:`~snapmock.core.scene.SnapScene`; every change goes through a command in
``snapmock/commands/guide_commands.py``. :func:`snap_value` and
:func:`snap_rect_delta` are the snapping arithmetic that the view offers tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from PyQt6.QtCore import QPointF, QRectF


class GuideOrientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(frozen=True)
class Guide:
    """One guide: a horizontal line at ``y = position`` or a vertical one at ``x``."""

    orientation: GuideOrientation
    position: float

    def moved_to(self, position: float) -> Guide:
        return Guide(self.orientation, position)

    def to_dict(self) -> dict[str, Any]:
        return {"orientation": self.orientation.value, "position": self.position}

    @classmethod
    def from_dict(cls, data: object) -> Guide | None:
        """A guide from a manifest entry, or None when the entry is malformed."""
        if not isinstance(data, dict):
            return None
        try:
            orientation = GuideOrientation(str(data.get("orientation")))
            position = float(data["position"])
        except (KeyError, TypeError, ValueError):
            return None
        return cls(orientation, position)


def snap_value(value: float, targets: list[float], tolerance: float) -> float | None:
    """The target nearest *value* within *tolerance*, or None when none is close."""
    best: float | None = None
    best_distance = tolerance
    for target in targets:
        distance = abs(target - value)
        if distance <= best_distance:
            best, best_distance = target, distance
    return best


def snap_rect_delta(rect: QRectF, guides: list[Guide], tolerance: float) -> QPointF:
    """The offset that brings an edge or the centre of *rect* onto the nearest guide.

    Each axis is considered on its own: the left, centre, and right of the
    rectangle against the vertical guides, the top, middle, and bottom against
    the horizontal ones. The axis stays put when nothing is within *tolerance*.
    """
    vertical = [g.position for g in guides if g.orientation is GuideOrientation.VERTICAL]
    horizontal = [g.position for g in guides if g.orientation is GuideOrientation.HORIZONTAL]
    dx = _axis_delta((rect.left(), rect.center().x(), rect.right()), vertical, tolerance)
    dy = _axis_delta((rect.top(), rect.center().y(), rect.bottom()), horizontal, tolerance)
    return QPointF(dx, dy)


def _axis_delta(candidates: tuple[float, ...], targets: list[float], tolerance: float) -> float:
    best = 0.0
    best_distance = tolerance
    for candidate in candidates:
        target = snap_value(candidate, targets, best_distance)
        if target is not None and abs(target - candidate) <= best_distance:
            best, best_distance = target - candidate, abs(target - candidate)
    return best
