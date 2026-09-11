"""HighlightItem — semi-transparent wide stroke annotation.

Blur, Highlighter & Eyedropper PRD Section 3: the stroke colour is the highlight colour,
whose alpha is the primary opacity (3.7); the cap is Flat by default (3.4) so the band
has a clean marker edge; the shadow, when enabled, is drawn first (3.7).
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker

from snapmock.config.constants import StrokeCap
from snapmock.items.vector_item import VectorItem


class HighlightItem(VectorItem):
    """A semi-transparent wide-stroke path used as a highlighter."""

    def __init__(self, parent: VectorItem | None = None) -> None:
        super().__init__(parent)
        self._stroke_color = QColor(255, 255, 0, 128)  # semi-transparent yellow
        self._stroke_width = 20.0
        self._stroke_cap = StrokeCap.FLAT
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
        margin = self.stroke_margin() + 2.0
        body = self._path.boundingRect().adjusted(-margin, -margin, margin, margin)
        return body.united(self.shadow_rect(body))

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(self._stroke_width + 4)
        return stroker.createStroke(self._path)

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        self._apply_flip(painter)
        self.paint_shadow(painter, self.shadow_path(self._path, closed=False))
        painter.setPen(self.pen())
        painter.drawPath(self._path)
        self._end_flip(painter)

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
