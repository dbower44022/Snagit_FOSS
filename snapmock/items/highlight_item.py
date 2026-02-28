"""HighlightItem — semi-transparent wide stroke annotation."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen

from snapmock.items.vector_item import VectorItem


class HighlightItem(VectorItem):
    """A semi-transparent wide-stroke path used as a highlighter."""

    def __init__(self, parent: VectorItem | None = None) -> None:
        super().__init__(parent)
        self._stroke_color = QColor(255, 255, 0, 128)  # semi-transparent yellow
        self._stroke_width = 20.0
        self._path = QPainterPath()
        self._points: list[tuple[float, float]] = []

    @property
    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def add_point(self, x: float, y: float) -> None:
        self.prepareGeometryChange()
        self._points.append((x, y))
        if len(self._points) == 1:
            self._path.moveTo(x, y)
        else:
            self._path.lineTo(x, y)
        self.update()

    def scale_geometry(self, sx: float, sy: float) -> None:
        super().scale_geometry(sx, sy)
        self._points = [(x * sx, y * sy) for x, y in self._points]
        self._path = QPainterPath()
        if self._points:
            self._path.moveTo(self._points[0][0], self._points[0][1])
            for x, y in self._points[1:]:
                self._path.lineTo(x, y)

    def boundingRect(self) -> QRectF:
        half = self._stroke_width / 2 + 2
        return self._path.boundingRect().adjusted(-half, -half, half, half)

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(self._stroke_width + 4)
        return stroker.createStroke(self._path)

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        pen = QPen(self._stroke_color, self._stroke_width)
        pen.setCapStyle(pen.capStyle().RoundCap)
        pen.setJoinStyle(pen.joinStyle().RoundJoin)
        painter.setPen(pen)
        painter.drawPath(self._path)

    def serialize(self) -> dict[str, Any]:
        data = self._base_data()
        data["type"] = "HighlightItem"
        data["points"] = self._points
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> HighlightItem:
        item = cls()
        item._apply_base_data(data)
        raw_points: list[list[float]] = data.get("points", [])
        for pt in raw_points:
            item.add_point(pt[0], pt[1])
        return item
