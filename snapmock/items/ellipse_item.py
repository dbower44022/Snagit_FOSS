"""EllipseItem — ellipse / circle annotation."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QBrush, QPainter, QPainterPath

from snapmock.items.vector_item import VectorItem


class EllipseItem(VectorItem):
    """An ellipse annotation item."""

    def __init__(
        self,
        rect: QRectF | None = None,
        parent: VectorItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._rect: QRectF = rect if rect is not None else QRectF(0, 0, 100, 100)

    @property
    def rect(self) -> QRectF:
        return QRectF(self._rect)

    @rect.setter
    def rect(self, value: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(value)
        self.update()

    def boundingRect(self) -> QRectF:
        half = self._stroke_width / 2
        return self._rect.adjusted(-half, -half, half, half)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(self._rect)
        return path

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        painter.setPen(self.pen())
        painter.setBrush(QBrush(self._fill_color))
        painter.drawEllipse(self._rect)

    def serialize(self) -> dict[str, Any]:
        data = self._base_data()
        data["type"] = "EllipseItem"
        data["rect"] = [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()]
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> EllipseItem:
        r = data.get("rect", [0, 0, 100, 100])
        item = cls(rect=QRectF(r[0], r[1], r[2], r[3]))
        item._apply_base_data(data)
        return item
