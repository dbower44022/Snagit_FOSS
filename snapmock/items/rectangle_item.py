"""RectangleItem — rectangle / square annotation with optional corner radius."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter, QPainterPath

from snapmock.config.constants import CORNER_RADIUS_MAX
from snapmock.items.vector_item import VectorItem


class RectangleItem(VectorItem):
    """A rectangle (optionally rounded) annotation item."""

    def __init__(
        self,
        rect: QRectF | None = None,
        corner_radius: float = 0.0,
        parent: VectorItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._rect: QRectF = rect if rect is not None else QRectF(0, 0, 100, 60)
        self._corner_radius: float = corner_radius

    @property
    def rect(self) -> QRectF:
        return QRectF(self._rect)

    @rect.setter
    def rect(self, value: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(value)
        self.update()

    @property
    def corner_radius(self) -> float:
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, value: float) -> None:
        """Stored as given (0 to 200); drawn clamped to half the smaller side (Basic Shape
        PRD 5.3), so a later resize restores the rounding the user set."""
        self._corner_radius = max(0.0, min(CORNER_RADIUS_MAX, float(value)))
        self._geometry_changed()

    def effective_corner_radius(self) -> float:
        """The radius drawn: ``corner_radius`` clamped to half the smaller side (5.3)."""
        limit = min(self._rect.width(), self._rect.height()) / 2.0
        return max(0.0, min(self._corner_radius, limit))

    def outline(self) -> QPainterPath:
        """The rectangle's edge, rounded when the effective corner radius is above zero."""
        path = QPainterPath()
        radius = self.effective_corner_radius()
        if radius > 0:
            path.addRoundedRect(self._rect, radius, radius)
        else:
            path.addRect(self._rect)
        return path

    def apply_creation_defaults(self, defaults: dict[str, Any]) -> None:
        super().apply_creation_defaults(defaults)
        if "corner_radius" in defaults:
            self.corner_radius = float(defaults["corner_radius"])

    def scale_geometry(self, sx: float, sy: float) -> None:
        super().scale_geometry(sx, sy)
        self._rect = QRectF(
            self._rect.x() * sx,
            self._rect.y() * sy,
            self._rect.width() * sx,
            self._rect.height() * sy,
        )
        self._corner_radius *= (sx + sy) / 2.0

    # --- QGraphicsItem overrides ---

    def boundingRect(self) -> QRectF:
        margin = self.stroke_margin()
        body = self._rect.adjusted(-margin, -margin, margin, margin)
        return body.united(self.shadow_rect(body))

    def shape(self) -> QPainterPath:
        return self.hit_shape(self.outline())

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        self._apply_flip(painter)
        outline = self.outline()
        self.paint_shadow(painter, self.shadow_path(outline))
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        radius = self.effective_corner_radius()
        if radius > 0:
            painter.drawRoundedRect(self._rect, radius, radius)
        else:
            painter.drawRect(self._rect)
        self._end_flip(painter)

    # --- serialization ---

    def serialize(self) -> dict[str, Any]:
        data = self._base_data()
        data["type"] = "RectangleItem"
        data["rect"] = [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()]
        data["corner_radius"] = self._corner_radius
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> RectangleItem:
        r = data.get("rect", [0, 0, 100, 60])
        item = cls(rect=QRectF(r[0], r[1], r[2], r[3]), corner_radius=data.get("corner_radius", 0))
        item._apply_base_data(data)
        return item
