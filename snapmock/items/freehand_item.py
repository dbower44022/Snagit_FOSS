"""FreehandItem — freehand drawn path annotation."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QPainterPathStroker

from snapmock.items.vector_item import VectorItem


class FreehandItem(VectorItem):
    """A freehand drawn path annotation item."""

    def __init__(self, parent: VectorItem | None = None) -> None:
        super().__init__(parent)
        self._path = QPainterPath()
        self._points: list[tuple[float, float]] = []

    @property
    def path(self) -> QPainterPath:
        return QPainterPath(self._path)

    @property
    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def add_point(self, point: QPointF) -> None:
        """Append a point to the path."""
        self.prepareGeometryChange()
        self._points.append((point.x(), point.y()))
        if len(self._points) == 1:
            self._path.moveTo(point)
        else:
            self._path.lineTo(point)
        self.update()

    def scale_geometry(self, sx: float, sy: float) -> None:
        super().scale_geometry(sx, sy)
        self._points = [(x * sx, y * sy) for x, y in self._points]
        self._path = QPainterPath()
        if self._points:
            self._path.moveTo(QPointF(self._points[0][0], self._points[0][1]))
            for x, y in self._points[1:]:
                self._path.lineTo(QPointF(x, y))

    def boundingRect(self) -> QRectF:
        half = self._stroke_width / 2 + 2
        return self._path.boundingRect().adjusted(-half, -half, half, half)

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self._stroke_width, 4.0))
        return stroker.createStroke(self._path)

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        painter.setPen(self.pen())
        painter.drawPath(self._path)

    def serialize(self) -> dict[str, Any]:
        data = self._base_data()
        data["type"] = "FreehandItem"
        data["points"] = self._points
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> FreehandItem:
        item = cls()
        item._apply_base_data(data)
        raw_points: list[list[float]] = data.get("points", [])
        for pt in raw_points:
            item.add_point(QPointF(pt[0], pt[1]))
        return item
