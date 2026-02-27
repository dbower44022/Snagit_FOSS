"""RasterRegionItem — extracted pixel region from raster selection/cut/paste."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter, QPixmap

from snapmock.items.base_item import SnapGraphicsItem


class RasterRegionItem(SnapGraphicsItem):
    """Holds a raster pixel region extracted from another layer."""

    def __init__(
        self,
        pixmap: QPixmap | None = None,
        parent: SnapGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._pixmap = pixmap if pixmap is not None else QPixmap(100, 100)

    @property
    def pixmap(self) -> QPixmap:
        return QPixmap(self._pixmap)

    @pixmap.setter
    def pixmap(self, value: QPixmap) -> None:
        self.prepareGeometryChange()
        self._pixmap = QPixmap(value)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._pixmap.width(), self._pixmap.height())

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        painter.drawPixmap(0, 0, self._pixmap)

    def serialize(self) -> dict[str, Any]:
        return {
            "type": "RasterRegionItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "width": self._pixmap.width(),
            "height": self._pixmap.height(),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> RasterRegionItem:
        w = data.get("width", 100)
        h = data.get("height", 100)
        item = cls(pixmap=QPixmap(w, h))
        pos = data.get("pos", [0, 0])
        item.setPos(pos[0], pos[1])
        item.item_id = data.get("item_id", item.item_id)
        item.layer_id = data.get("layer_id", "")
        return item
