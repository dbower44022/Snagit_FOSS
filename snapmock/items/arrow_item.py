"""ArrowItem — line with arrowhead annotation."""

from __future__ import annotations

import math
from typing import Any

from PyQt6.QtCore import QLineF, QPointF, QRectF
from PyQt6.QtGui import QBrush, QPainter, QPainterPath, QPainterPathStroker, QPolygonF

from snapmock.items.vector_item import VectorItem, with_alpha

_ARROW_SIZE = 12.0


class ArrowItem(VectorItem):
    """A line with an arrowhead at the end point."""

    def __init__(
        self,
        line: QLineF | None = None,
        parent: VectorItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._line: QLineF = line if line is not None else QLineF(0, 0, 100, 0)

    @property
    def line(self) -> QLineF:
        return QLineF(self._line)

    @line.setter
    def line(self, value: QLineF) -> None:
        self.prepareGeometryChange()
        self._line = QLineF(value)
        self.update()

    def scale_geometry(self, sx: float, sy: float) -> None:
        super().scale_geometry(sx, sy)
        self._line = QLineF(
            self._line.x1() * sx,
            self._line.y1() * sy,
            self._line.x2() * sx,
            self._line.y2() * sy,
        )

    def _arrowhead_polygon(self) -> QPolygonF:
        """Compute a triangle polygon for the arrowhead at p2."""
        angle = math.atan2(
            -(self._line.dy()),
            self._line.dx(),
        )
        size = _ARROW_SIZE + self._stroke_width
        p2 = self._line.p2()
        p1 = QPointF(
            p2.x() - size * math.cos(angle - math.pi / 6),
            p2.y() + size * math.sin(angle - math.pi / 6),
        )
        p3 = QPointF(
            p2.x() - size * math.cos(angle + math.pi / 6),
            p2.y() + size * math.sin(angle + math.pi / 6),
        )
        return QPolygonF([p2, p1, p3])

    def line_path(self) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(self._line.p1())
        path.lineTo(self._line.p2())
        return path

    def _head_path(self) -> QPainterPath:
        head = QPainterPath()
        head.addPolygon(self._arrowhead_polygon())
        head.closeSubpath()
        return head

    def boundingRect(self) -> QRectF:
        margin = _ARROW_SIZE + self._stroke_width + 4
        body = (
            QRectF(self._line.p1(), self._line.p2())
            .normalized()
            .adjusted(-margin, -margin, margin, margin)
        )
        return body.united(self.shadow_rect(body))

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self._stroke_width, 4.0))
        stroke_path = stroker.createStroke(self.line_path())
        stroke_path.addPolygon(self._arrowhead_polygon())
        return stroke_path

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        self._apply_flip(painter)
        head = self._head_path()
        shadow = self.shadow_path(self.line_path(), closed=False)
        shadow = shadow.united(head.united(self.stroke_outline(head)))
        self.paint_shadow(painter, shadow)
        painter.setPen(self.pen())
        painter.drawLine(self._line)
        # The head takes the stroke colour at the stroke opacity (Basic Shape PRD 4.4).
        painter.setBrush(QBrush(with_alpha(self._stroke_color, self._stroke_opacity)))
        painter.drawPolygon(self._arrowhead_polygon())
        self._end_flip(painter)

    def serialize(self) -> dict[str, Any]:
        data = self._base_data()
        data["type"] = "ArrowItem"
        data["line"] = [
            self._line.x1(),
            self._line.y1(),
            self._line.x2(),
            self._line.y2(),
        ]
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> ArrowItem:
        coords = data.get("line", [0, 0, 100, 0])
        item = cls(line=QLineF(QPointF(coords[0], coords[1]), QPointF(coords[2], coords[3])))
        item._apply_base_data(data)
        return item
