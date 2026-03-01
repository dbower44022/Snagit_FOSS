"""CalloutItem — text box with a pointer/tail shape."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath

from snapmock.config.constants import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
from snapmock.items.base_item import SnapGraphicsItem


class CalloutItem(SnapGraphicsItem):
    """A text callout with a pointer tail."""

    def __init__(
        self,
        text: str = "Callout",
        rect: QRectF | None = None,
        tail_tip: QPointF | None = None,
        parent: SnapGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._rect = rect if rect is not None else QRectF(0, 0, 150, 60)
        self._tail_tip = tail_tip if tail_tip is not None else QPointF(75, 90)
        self._font = QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
        self._bg_color = QColor("#FFFFCC")
        self._border_color = QColor("#000000")
        self._text_color = QColor(Qt.GlobalColor.black)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value
        self.update()

    @property
    def font(self) -> QFont:
        return QFont(self._font)

    @font.setter
    def font(self, value: QFont) -> None:
        self.prepareGeometryChange()
        self._font = QFont(value)
        self.update()

    @property
    def text_color(self) -> QColor:
        return QColor(self._text_color)

    @text_color.setter
    def text_color(self, value: QColor) -> None:
        self._text_color = QColor(value)
        self.update()

    @property
    def tail_tip(self) -> QPointF:
        return QPointF(self._tail_tip)

    @tail_tip.setter
    def tail_tip(self, value: QPointF) -> None:
        self.prepareGeometryChange()
        self._tail_tip = QPointF(value)
        self.update()

    def scale_geometry(self, sx: float, sy: float) -> None:
        self._rect = QRectF(
            self._rect.x() * sx,
            self._rect.y() * sy,
            self._rect.width() * sx,
            self._rect.height() * sy,
        )
        self._tail_tip = QPointF(self._tail_tip.x() * sx, self._tail_tip.y() * sy)
        avg = (sx + sy) / 2.0
        new_size = max(1, int(self._font.pointSize() * avg))
        self._font.setPointSize(new_size)

    def boundingRect(self) -> QRectF:
        r = self._rect.united(QRectF(self._tail_tip, self._tail_tip))
        return r.adjusted(-2, -2, 2, 2)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self._rect)
        # Add tail triangle
        center_x = self._rect.center().x()
        bottom = self._rect.bottom()
        path.moveTo(center_x - 10, bottom)
        path.lineTo(self._tail_tip)
        path.lineTo(center_x + 10, bottom)
        return path

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        # Draw tail
        tail_path = QPainterPath()
        center_x = self._rect.center().x()
        bottom = self._rect.bottom()
        tail_path.moveTo(center_x - 10, bottom)
        tail_path.lineTo(self._tail_tip)
        tail_path.lineTo(center_x + 10, bottom)
        tail_path.closeSubpath()
        painter.setPen(self._border_color)
        painter.setBrush(QBrush(self._bg_color))
        painter.drawPath(tail_path)
        # Draw box
        painter.drawRoundedRect(self._rect, 4, 4)
        # Draw text
        painter.setFont(self._font)
        painter.setPen(self._text_color)
        painter.drawText(self._rect.adjusted(4, 4, -4, -4), Qt.TextFlag.TextWordWrap, self._text)

    def serialize(self) -> dict[str, Any]:
        return {
            "type": "CalloutItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "text": self._text,
            "rect": [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()],
            "tail_tip": [self._tail_tip.x(), self._tail_tip.y()],
            "bg_color": self._bg_color.name(QColor.NameFormat.HexArgb),
            "border_color": self._border_color.name(QColor.NameFormat.HexArgb),
            "font_family": self._font.family(),
            "font_size": self._font.pointSize(),
            "text_color": self._text_color.name(QColor.NameFormat.HexArgb),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> CalloutItem:
        r = data.get("rect", [0, 0, 150, 60])
        t = data.get("tail_tip", [75, 90])
        item = cls(
            text=data.get("text", "Callout"),
            rect=QRectF(r[0], r[1], r[2], r[3]),
            tail_tip=QPointF(t[0], t[1]),
        )
        pos = data.get("pos", [0, 0])
        item.setPos(pos[0], pos[1])
        item.item_id = data.get("item_id", item.item_id)
        item.layer_id = data.get("layer_id", "")
        if "bg_color" in data:
            item._bg_color = QColor(data["bg_color"])
        if "border_color" in data:
            item._border_color = QColor(data["border_color"])
        if "font_family" in data or "font_size" in data:
            item._font = QFont(
                data.get("font_family", DEFAULT_FONT_FAMILY),
                data.get("font_size", DEFAULT_FONT_SIZE),
            )
        if "text_color" in data:
            item._text_color = QColor(data["text_color"])
        return item
