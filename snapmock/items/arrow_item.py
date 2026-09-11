"""ArrowItem — line with arrowhead annotation.

Basic Shape Annotation Tools PRD Section 4: a straight shaft from the tail (``p1``) to the
head (``p2``) with a head style and a tail style from the six of 4.3 (None, Open, Filled,
Diamond, Circle, Square), a head size from the four named sizes or a custom size, all
painted per 4.4: an open head is two stroked lines at 30 degrees with a round cap; the
filled heads take the stroke colour at the stroke opacity, and the shaft ends at a filled
head's base so nothing overlaps. ``line_style`` is stored and stays Straight; curved and
elbow arrows (4.5, 4.6) are the following kickoff's (Vector Item Properties decision 3).
"""

from __future__ import annotations

import math
from typing import Any

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF

from snapmock.config.constants import (
    HEAD_SIZE_CUSTOM_MAX,
    HEAD_SIZE_PX,
    HeadSize,
    HeadStyle,
    LineStyle,
)
from snapmock.items.vector_item import VectorItem, _enum, with_alpha

_OPEN_HALF_ANGLE = math.radians(30.0)


class ArrowItem(VectorItem):
    """A line with an arrowhead at the end point and an optional one at the start."""

    def __init__(
        self,
        line: QLineF | None = None,
        parent: VectorItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._line: QLineF = line if line is not None else QLineF(0, 0, 100, 0)
        self._head_style: HeadStyle = HeadStyle.OPEN
        self._tail_style: HeadStyle = HeadStyle.NONE
        self._head_size: HeadSize = HeadSize.MEDIUM
        self._head_size_custom: float = 0.0
        self._line_style: LineStyle = LineStyle.STRAIGHT

    # ------------------------------------------------------------ properties

    @property
    def line(self) -> QLineF:
        return QLineF(self._line)

    @line.setter
    def line(self, value: QLineF) -> None:
        self._line = QLineF(value)
        self._geometry_changed()

    @property
    def head_style(self) -> HeadStyle:
        """The style at the end point (4.3); Open by default."""
        return self._head_style

    @head_style.setter
    def head_style(self, value: HeadStyle) -> None:
        self._head_style = HeadStyle(value)
        self._geometry_changed()

    @property
    def tail_style(self) -> HeadStyle:
        """The style at the start point (4.3); None by default."""
        return self._tail_style

    @tail_style.setter
    def tail_style(self, value: HeadStyle) -> None:
        self._tail_style = HeadStyle(value)
        self._geometry_changed()

    @property
    def head_size(self) -> HeadSize:
        """Small, Medium, Large, or XLarge (4.3); the custom size wins when set."""
        return self._head_size

    @head_size.setter
    def head_size(self, value: HeadSize) -> None:
        self._head_size = HeadSize(value)
        self._geometry_changed()

    @property
    def head_size_custom(self) -> float:
        """A custom size in pixels, 4 to 60; 0 means the named size applies (4.3)."""
        return self._head_size_custom

    @head_size_custom.setter
    def head_size_custom(self, value: float) -> None:
        size = float(value)
        self._head_size_custom = 0.0 if size <= 0 else max(4.0, min(HEAD_SIZE_CUSTOM_MAX, size))
        self._geometry_changed()

    @property
    def line_style(self) -> LineStyle:
        """Straight; Curved and Elbow are stored for the following kickoff and drawn straight."""
        return self._line_style

    @line_style.setter
    def line_style(self, value: LineStyle) -> None:
        self._line_style = LineStyle(value)
        self._geometry_changed()

    def effective_head_size(self) -> float:
        """The head's size in pixels: the custom size, else the named size, plus the stroke
        width (4.3: the size scales with the stroke width; the addition is the shipped rule)."""
        base = (
            self._head_size_custom if self._head_size_custom > 0 else HEAD_SIZE_PX[self._head_size]
        )
        return base + self._stroke_width

    # ------------------------------------------------------------ geometry

    def scale_geometry(self, sx: float, sy: float) -> None:
        super().scale_geometry(sx, sy)
        self._line = QLineF(
            self._line.x1() * sx,
            self._line.y1() * sy,
            self._line.x2() * sx,
            self._line.y2() * sy,
        )
        if self._head_size_custom > 0:
            self._head_size_custom = max(
                4.0, min(HEAD_SIZE_CUSTOM_MAX, self._head_size_custom * (sx + sy) / 2.0)
            )

    def _direction(self) -> QPointF:
        """The unit vector from the tail to the head; along x for a zero-length line."""
        length = self._line.length()
        if length <= 0.0:
            return QPointF(1.0, 0.0)
        return QPointF(self._line.dx() / length, self._line.dy() / length)

    def _head_geometry(
        self, tip: QPointF, forward: QPointF, style: HeadStyle
    ) -> tuple[QPainterPath, QPainterPath, float]:
        """The filled path, the open lines path, and how far the shaft retreats from *tip*
        for a head of *style* pointing along *forward* (4.4)."""
        size = self.effective_head_size()
        u = forward
        v = QPointF(-u.y(), u.x())
        filled = QPainterPath()
        lines = QPainterPath()
        if style is HeadStyle.OPEN:
            length = size
            for sign in (1.0, -1.0):
                end = QPointF(
                    tip.x()
                    - length
                    * (
                        math.cos(_OPEN_HALF_ANGLE) * u.x()
                        + sign * math.sin(_OPEN_HALF_ANGLE) * v.x()
                    ),
                    tip.y()
                    - length
                    * (
                        math.cos(_OPEN_HALF_ANGLE) * u.y()
                        + sign * math.sin(_OPEN_HALF_ANGLE) * v.y()
                    ),
                )
                lines.moveTo(tip)
                lines.lineTo(end)
            return filled, lines, 0.0
        if style is HeadStyle.FILLED:
            base = QPointF(tip.x() - size * u.x(), tip.y() - size * u.y())
            filled.addPolygon(
                QPolygonF(
                    [
                        tip,
                        QPointF(base.x() + size * v.x(), base.y() + size * v.y()),
                        QPointF(base.x() - size * v.x(), base.y() - size * v.y()),
                    ]
                )
            )
            filled.closeSubpath()
            return filled, lines, size
        half = size / 2.0
        if style is HeadStyle.DIAMOND:
            filled.addPolygon(
                QPolygonF(
                    [
                        QPointF(tip.x() + half * u.x(), tip.y() + half * u.y()),
                        QPointF(tip.x() + half * v.x(), tip.y() + half * v.y()),
                        QPointF(tip.x() - half * u.x(), tip.y() - half * u.y()),
                        QPointF(tip.x() - half * v.x(), tip.y() - half * v.y()),
                    ]
                )
            )
            filled.closeSubpath()
            return filled, lines, half
        if style is HeadStyle.CIRCLE:
            filled.addEllipse(tip, half, half)
            return filled, lines, half
        if style is HeadStyle.SQUARE:
            filled.addPolygon(
                QPolygonF(
                    [
                        QPointF(
                            tip.x() + half * (u.x() + v.x()), tip.y() + half * (u.y() + v.y())
                        ),
                        QPointF(
                            tip.x() + half * (u.x() - v.x()), tip.y() + half * (u.y() - v.y())
                        ),
                        QPointF(
                            tip.x() - half * (u.x() + v.x()), tip.y() - half * (u.y() + v.y())
                        ),
                        QPointF(
                            tip.x() - half * (u.x() - v.x()), tip.y() - half * (u.y() - v.y())
                        ),
                    ]
                )
            )
            filled.closeSubpath()
            return filled, lines, half
        return filled, lines, 0.0

    def head_paths(self) -> tuple[QPainterPath, QPainterPath, QLineF]:
        """The filled heads, the open heads' lines, and the shaft that remains between them."""
        u = self._direction()
        back = QPointF(-u.x(), -u.y())
        head_fill, head_lines, head_retreat = self._head_geometry(
            self._line.p2(), u, self._head_style
        )
        tail_fill, tail_lines, tail_retreat = self._head_geometry(
            self._line.p1(), back, self._tail_style
        )
        filled = head_fill.united(tail_fill) if not tail_fill.isEmpty() else head_fill
        if head_fill.isEmpty():
            filled = tail_fill
        lines = QPainterPath(head_lines)
        lines.addPath(tail_lines)
        length = self._line.length()
        head_retreat = min(head_retreat, length)
        tail_retreat = min(tail_retreat, max(0.0, length - head_retreat))
        shaft = QLineF(
            QPointF(
                self._line.x1() + u.x() * tail_retreat, self._line.y1() + u.y() * tail_retreat
            ),
            QPointF(
                self._line.x2() - u.x() * head_retreat, self._line.y2() - u.y() * head_retreat
            ),
        )
        return filled, lines, shaft

    def _arrowhead_polygon(self) -> QPolygonF:
        """The head's outline as a polygon (kept for callers that had the one filled head)."""
        filled, _lines, _shaft = self.head_paths()
        return filled.toFillPolygon()

    def line_path(self) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(self._line.p1())
        path.lineTo(self._line.p2())
        return path

    def boundingRect(self) -> QRectF:
        margin = self.effective_head_size() + self._stroke_width + 4
        body = (
            QRectF(self._line.p1(), self._line.p2())
            .normalized()
            .adjusted(-margin, -margin, margin, margin)
        )
        return body.united(self.shadow_rect(body))

    def shape(self) -> QPainterPath:
        filled, lines, _shaft = self.head_paths()
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self._stroke_width, 4.0))
        stroke_path = stroker.createStroke(self.line_path())
        stroke_path.addPath(filled)
        if not lines.isEmpty():
            stroke_path.addPath(stroker.createStroke(lines))
        return stroke_path

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        self._apply_flip(painter)
        filled, lines, shaft = self.head_paths()
        shaft_path = QPainterPath()
        shaft_path.moveTo(shaft.p1())
        shaft_path.lineTo(shaft.p2())
        shadow = self.shadow_path(shaft_path, closed=False)
        if not filled.isEmpty():
            shadow = shadow.united(filled.united(self.stroke_outline(filled)))
        if not lines.isEmpty():
            shadow = shadow.united(self.stroke_outline(lines))
        self.paint_shadow(painter, shadow)
        pen = self.pen()
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if shaft.length() > 0.0:
            painter.drawLine(shaft)
        if not lines.isEmpty():
            # The open head keeps a round cap (4.4) and a solid line
            open_pen = QPen(pen)
            open_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            open_pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(open_pen)
            painter.drawPath(lines)
        if not filled.isEmpty():
            # The filled heads take the stroke colour at the stroke opacity (4.4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(with_alpha(self._stroke_color, self._stroke_opacity)))
            painter.drawPath(filled)
        self._end_flip(painter)

    # ------------------------------------------------------------ creation defaults

    def apply_creation_defaults(self, defaults: dict[str, Any]) -> None:
        super().apply_creation_defaults(defaults)
        head = defaults.get("head_style")
        if isinstance(head, HeadStyle):
            self._head_style = head
        tail = defaults.get("tail_style")
        if isinstance(tail, HeadStyle):
            self._tail_style = tail
        size = defaults.get("head_size")
        if isinstance(size, HeadSize):
            self._head_size = size
        if "head_size_custom" in defaults:
            self.head_size_custom = float(defaults["head_size_custom"])
        self._geometry_changed()

    # ------------------------------------------------------------ serialization

    def serialize(self) -> dict[str, Any]:
        data = self._base_data()
        data["type"] = "ArrowItem"
        data["line"] = [
            self._line.x1(),
            self._line.y1(),
            self._line.x2(),
            self._line.y2(),
        ]
        data["head_style"] = self._head_style.value
        data["tail_style"] = self._tail_style.value
        data["head_size"] = self._head_size.value
        data["head_size_custom"] = self._head_size_custom
        data["line_style"] = self._line_style.value
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> ArrowItem:
        coords = data.get("line", [0, 0, 100, 0])
        item = cls(line=QLineF(QPointF(coords[0], coords[1]), QPointF(coords[2], coords[3])))
        item._apply_base_data(data)
        # A file saved before the arrowheads existed drew one filled head (decision 3).
        item._head_style = _enum(HeadStyle, data.get("head_style"), HeadStyle.FILLED)
        item._tail_style = _enum(HeadStyle, data.get("tail_style"), HeadStyle.NONE)
        item._head_size = _enum(HeadSize, data.get("head_size"), HeadSize.MEDIUM)
        item.head_size_custom = float(data.get("head_size_custom", 0.0))
        item._line_style = _enum(LineStyle, data.get("line_style"), LineStyle.STRAIGHT)
        return item
