"""BlurItem — region that applies blur/pixelate effect to layers below."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter

from snapmock.items.base_item import SnapGraphicsItem


class BlurItem(SnapGraphicsItem):
    """A region that visually blurs content beneath it."""

    def __init__(
        self,
        rect: QRectF | None = None,
        blur_radius: float = 10.0,
        parent: SnapGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._rect = rect if rect is not None else QRectF(0, 0, 100, 100)
        self._blur_radius = blur_radius

    @property
    def rect(self) -> QRectF:
        return QRectF(self._rect)

    @rect.setter
    def rect(self, value: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(value)
        self.update()

    @property
    def blur_radius(self) -> float:
        return self._blur_radius

    @blur_radius.setter
    def blur_radius(self, value: float) -> None:
        self._blur_radius = max(1.0, value)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        # Draw a semi-transparent overlay to indicate the blur region
        from PyQt6.QtGui import QBrush, QColor

        painter.setBrush(QBrush(QColor(128, 128, 128, 80)))
        painter.setPen(QColor(100, 100, 100, 150))
        painter.drawRect(self._rect)

    def serialize(self) -> dict[str, Any]:
        return {
            "type": "BlurItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "rect": [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()],
            "blur_radius": self._blur_radius,
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> BlurItem:
        r = data.get("rect", [0, 0, 100, 100])
        item = cls(
            rect=QRectF(r[0], r[1], r[2], r[3]),
            blur_radius=data.get("blur_radius", 10.0),
        )
        pos = data.get("pos", [0, 0])
        item.setPos(pos[0], pos[1])
        item.item_id = data.get("item_id", item.item_id)
        item.layer_id = data.get("layer_id", "")
        return item
