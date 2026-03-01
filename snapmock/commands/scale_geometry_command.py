"""ScaleGeometryCommand — resize an item by scaling its internal geometry."""

from __future__ import annotations

from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem


class ScaleGeometryCommand(BaseCommand):
    """Scale an item's internal geometry by (sx, sy) factors."""

    def __init__(self, item: SnapGraphicsItem, sx: float, sy: float) -> None:
        self._item = item
        self._sx = sx
        self._sy = sy

    def redo(self) -> None:
        self._item.scale_geometry(self._sx, self._sy)
        self._item.update()

    def undo(self) -> None:
        self._item.scale_geometry(1.0 / self._sx, 1.0 / self._sy)
        self._item.update()

    @property
    def description(self) -> str:
        return "Resize item"
