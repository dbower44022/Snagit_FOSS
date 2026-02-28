"""TextItem — editable rich text annotation."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter

from snapmock.config.constants import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
from snapmock.items.base_item import SnapGraphicsItem


class TextItem(SnapGraphicsItem):
    """An editable text annotation item."""

    def __init__(
        self,
        text: str = "Text",
        pos_x: float = 0,
        pos_y: float = 0,
        parent: SnapGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._font = QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
        self._color = QColor(Qt.GlobalColor.black)
        self._width: float = 200.0
        self.setPos(pos_x, pos_y)

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
        return QColor(self._color)

    @text_color.setter
    def text_color(self, value: QColor) -> None:
        self._color = QColor(value)
        self.update()

    def scale_geometry(self, sx: float, sy: float) -> None:
        avg = (sx + sy) / 2.0
        new_size = max(1, int(self._font.pointSize() * avg))
        self._font.setPointSize(new_size)
        self._width *= sx

    def boundingRect(self) -> QRectF:
        from PyQt6.QtGui import QFontMetricsF

        fm = QFontMetricsF(self._font)
        text_rect = QRectF(0, 0, self._width, 10000)
        br = fm.boundingRect(text_rect, Qt.TextFlag.TextWordWrap, self._text)
        return QRectF(0, 0, max(br.width(), 20), max(br.height(), fm.height()))

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        painter.setFont(self._font)
        painter.setPen(self._color)
        painter.drawText(self.boundingRect(), Qt.TextFlag.TextWordWrap, self._text)

    def serialize(self) -> dict[str, Any]:
        return {
            "type": "TextItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "text": self._text,
            "font_family": self._font.family(),
            "font_size": self._font.pointSize(),
            "color": self._color.name(QColor.NameFormat.HexArgb),
            "width": self._width,
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> TextItem:
        item = cls(text=data.get("text", "Text"))
        pos = data.get("pos", [0, 0])
        item.setPos(pos[0], pos[1])
        item.item_id = data.get("item_id", item.item_id)
        item.layer_id = data.get("layer_id", "")
        item._font = QFont(
            data.get("font_family", DEFAULT_FONT_FAMILY),
            data.get("font_size", DEFAULT_FONT_SIZE),
        )
        item._color = QColor(data.get("color", "#ff000000"))
        item._width = data.get("width", 200.0)
        return item
