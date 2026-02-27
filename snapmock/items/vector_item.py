"""VectorItem — abstract base for items defined by vector paths."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPen

from snapmock.config.constants import (
    DEFAULT_FILL_COLOR,
    DEFAULT_STROKE_COLOR,
    DEFAULT_STROKE_WIDTH,
)
from snapmock.items.base_item import SnapGraphicsItem


class VectorItem(SnapGraphicsItem):
    """Abstract base for vector-based annotation items.

    Provides shared stroke/fill properties and serialization helpers.
    Concrete subclasses must implement ``boundingRect``, ``paint``, ``serialize``,
    and ``deserialize``.
    """

    def __init__(self, parent: SnapGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._stroke_color: QColor = QColor(DEFAULT_STROKE_COLOR)
        self._stroke_width: float = DEFAULT_STROKE_WIDTH
        self._fill_color: QColor = QColor(DEFAULT_FILL_COLOR)

    # --- pen / brush ---

    @property
    def stroke_color(self) -> QColor:
        return QColor(self._stroke_color)

    @stroke_color.setter
    def stroke_color(self, color: QColor) -> None:
        self._stroke_color = QColor(color)
        self.update()

    @property
    def stroke_width(self) -> float:
        return self._stroke_width

    @stroke_width.setter
    def stroke_width(self, width: float) -> None:
        self.prepareGeometryChange()
        self._stroke_width = max(0.0, width)
        self.update()

    @property
    def fill_color(self) -> QColor:
        return QColor(self._fill_color)

    @fill_color.setter
    def fill_color(self, color: QColor) -> None:
        self._fill_color = QColor(color)
        self.update()

    def pen(self) -> QPen:
        """Return a QPen configured from the current stroke properties."""
        p = QPen(self._stroke_color, self._stroke_width)
        p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setCapStyle(Qt.PenCapStyle.RoundCap)
        return p

    # --- serialization helpers ---

    def _base_data(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "rotation": self.rotation(),
            "opacity": self.opacity(),
            "stroke_color": self._stroke_color.name(QColor.NameFormat.HexArgb),
            "stroke_width": self._stroke_width,
            "fill_color": self._fill_color.name(QColor.NameFormat.HexArgb),
        }

    def _apply_base_data(self, data: dict[str, Any]) -> None:
        self.item_id = data.get("item_id", self.item_id)
        self.layer_id = data.get("layer_id", "")
        pos = data.get("pos", [0, 0])
        self.setPos(pos[0], pos[1])
        self.setRotation(data.get("rotation", 0.0))
        self.setOpacity(data.get("opacity", 1.0))
        self._stroke_color = QColor(data.get("stroke_color", DEFAULT_STROKE_COLOR))
        self._stroke_width = data.get("stroke_width", DEFAULT_STROKE_WIDTH)
        self._fill_color = QColor(data.get("fill_color", DEFAULT_FILL_COLOR))

    # --- still abstract ---

    def boundingRect(self) -> QRectF:
        raise NotImplementedError

    def paint(self, painter: Any, option: Any, widget: Any = None) -> None:
        raise NotImplementedError

    def serialize(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> VectorItem:
        raise NotImplementedError
