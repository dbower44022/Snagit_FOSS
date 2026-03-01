"""RasterRegionItem — extracted pixel region from raster selection/cut/paste."""

from __future__ import annotations

import base64
from typing import Any

from PyQt6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PyQt6.QtGui import QImage, QPainter, QPixmap

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

    def scale_geometry(self, sx: float, sy: float) -> None:
        new_w = max(1, int(self._pixmap.width() * sx))
        new_h = max(1, int(self._pixmap.height() * sy))
        self.prepareGeometryChange()
        self._pixmap = self._pixmap.scaled(
            new_w, new_h, transformMode=Qt.TransformationMode.SmoothTransformation
        )

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._pixmap.width(), self._pixmap.height())

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        painter.drawPixmap(0, 0, self._pixmap)

    def serialize(self) -> dict[str, Any]:
        image_b64 = ""
        if not self._pixmap.isNull():
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            self._pixmap.save(buf, "PNG")
            image_b64 = base64.b64encode(buf.data().data()).decode("ascii")
        return {
            "type": "RasterRegionItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "width": self._pixmap.width(),
            "height": self._pixmap.height(),
            "image_data": image_b64,
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> RasterRegionItem:
        image_b64 = data.get("image_data", "")
        if image_b64:
            img_bytes = base64.b64decode(image_b64)
            img = QImage()
            img.loadFromData(img_bytes)
            pixmap = QPixmap.fromImage(img)
        else:
            w = data.get("width", 100)
            h = data.get("height", 100)
            pixmap = QPixmap(w, h)
        item = cls(pixmap=pixmap)
        pos = data.get("pos", [0, 0])
        item.setPos(pos[0], pos[1])
        item.item_id = data.get("item_id", item.item_id)
        item.layer_id = data.get("layer_id", "")
        return item
