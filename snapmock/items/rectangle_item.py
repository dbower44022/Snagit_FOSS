"""RectangleItem — rectangle / square annotation with optional corner radius."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QBrush, QPainter, QPainterPath

from snapmock.items.vector_item import VectorItem


class RectangleItem(VectorItem):
    """A rectangle (optionally rounded) annotation item."""

    def __init__(
        self,
        rect: QRectF | None = None,
        corner_radius: float = 0.0,
        parent: VectorItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._rect: QRectF = rect if rect is not None else QRectF(0, 0, 100, 60)
        self._corner_radius: float = corner_radius

    @property
    def rect(self) -> QRectF:
        return QRectF(self._rect)

    @rect.setter
    def rect(self, value: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(value)
        self.update()

    @property
    def corner_radius(self) -> float:
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, value: float) -> None:
        self._corner_radius = max(0.0, value)
        self.update()

    # --- QGraphicsItem overrides ---

    def boundingRect(self) -> QRectF:
        half = self._stroke_width / 2
        return self._rect.adjusted(-half, -half, half, half)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if self._corner_radius > 0:
            path.addRoundedRect(self._rect, self._corner_radius, self._corner_radius)
        else:
            path.addRect(self._rect)
        return path

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        painter.setPen(self.pen())
        painter.setBrush(QBrush(self._fill_color))
        if self._corner_radius > 0:
            painter.drawRoundedRect(self._rect, self._corner_radius, self._corner_radius)
        else:
            painter.drawRect(self._rect)

    # --- serialization ---

    def serialize(self) -> dict[str, Any]:
        data = self._base_data()
        data["type"] = "RectangleItem"
        data["rect"] = [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()]
        data["corner_radius"] = self._corner_radius
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> RectangleItem:
        r = data.get("rect", [0, 0, 100, 60])
        item = cls(rect=QRectF(r[0], r[1], r[2], r[3]), corner_radius=data.get("corner_radius", 0))
        item._apply_base_data(data)
        return item
