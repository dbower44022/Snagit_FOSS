"""SnapGraphicsItem — abstract base class for all scene annotation items."""

from __future__ import annotations

import uuid
from abc import abstractmethod
from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsObject


class SnapGraphicsItem(QGraphicsObject):
    """Base class for every annotation item in the scene.

    Adds a stable UUID, layer association, and serialization hooks on top of
    QGraphicsObject (which provides signal support).
    """

    def __init__(self, parent: QGraphicsObject | None = None) -> None:
        super().__init__(parent)
        self._item_id: str = uuid.uuid4().hex
        self._layer_id: str = ""
        self._locked: bool = False
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    # --- identity ---

    @property
    def item_id(self) -> str:
        return self._item_id

    @item_id.setter
    def item_id(self, value: str) -> None:
        self._item_id = value

    @property
    def layer_id(self) -> str:
        return self._layer_id

    @layer_id.setter
    def layer_id(self, value: str) -> None:
        self._layer_id = value

    @property
    def locked(self) -> bool:
        return self._locked

    @locked.setter
    def locked(self, value: bool) -> None:
        self._locked = value

    # --- required overrides ---

    @abstractmethod
    def boundingRect(self) -> QRectF: ...

    @abstractmethod
    def paint(
        self,
        painter: Any,
        option: Any,
        widget: Any = None,
    ) -> None: ...

    def shape(self) -> QPainterPath:
        """Return an accurate shape for hit testing (default: bounding rect)."""
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    # --- serialization ---

    @abstractmethod
    def serialize(self) -> dict[str, Any]:
        """Return a JSON-serializable dict of item state."""

    @classmethod
    @abstractmethod
    def deserialize(cls, data: dict[str, Any]) -> SnapGraphicsItem:
        """Reconstruct an item from serialized data."""

    def clone(self) -> SnapGraphicsItem:
        """Return a deep copy with a new item_id."""
        data = self.serialize()
        new_item = type(self).deserialize(data)
        new_item._item_id = uuid.uuid4().hex
        return new_item

    # --- geometry scaling ---

    def scale_geometry(self, sx: float, sy: float) -> None:
        """Scale internal geometry by the given factors.

        Subclasses override to scale rects, paths, radii, etc. Default is no-op.
        """

    # --- type label for UI ---

    @property
    def type_name(self) -> str:
        return type(self).__name__
