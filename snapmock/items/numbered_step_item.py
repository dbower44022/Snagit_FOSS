"""NumberedStepItem — circled number with optional label."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter

from snapmock.items.base_item import SnapGraphicsItem

_CIRCLE_RADIUS = 16.0


class NumberedStepItem(SnapGraphicsItem):
    """A circled number annotation (e.g. step 1, step 2)."""

    def __init__(
        self,
        number: int = 1,
        parent: SnapGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._number = number
        self._radius = _CIRCLE_RADIUS
        self._bg_color = QColor("#FF0000")
        self._text_color = QColor(Qt.GlobalColor.white)
        self._font = QFont("Sans Serif", 12, QFont.Weight.Bold)

    @property
    def number(self) -> int:
        return self._number

    @number.setter
    def number(self, value: int) -> None:
        self._number = value
        self.update()

    def boundingRect(self) -> QRectF:
        r = self._radius + 2
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        r = self._radius
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(-r, -r, r * 2, r * 2))
        painter.setFont(self._font)
        painter.setPen(self._text_color)
        painter.drawText(
            QRectF(-r, -r, r * 2, r * 2),
            Qt.AlignmentFlag.AlignCenter,
            str(self._number),
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "type": "NumberedStepItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "number": self._number,
            "bg_color": self._bg_color.name(QColor.NameFormat.HexArgb),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> NumberedStepItem:
        item = cls(number=data.get("number", 1))
        pos = data.get("pos", [0, 0])
        item.setPos(pos[0], pos[1])
        item.item_id = data.get("item_id", item.item_id)
        item.layer_id = data.get("layer_id", "")
        if "bg_color" in data:
            item._bg_color = QColor(data["bg_color"])
        return item
