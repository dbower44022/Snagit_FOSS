"""CalloutItem — text box with a pointer/tail shape."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen

from snapmock.config.constants import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, VerticalAlign
from snapmock.core.rich_text_mixin import RichTextMixin
from snapmock.items.base_item import SnapGraphicsItem


class CalloutItem(RichTextMixin, SnapGraphicsItem):
    """A text callout with a pointer tail, backed by QTextDocument."""

    def __init__(
        self,
        text: str = "Callout",
        rect: QRectF | None = None,
        tail_tip: QPointF | None = None,
        parent: SnapGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._rect = rect if rect is not None else QRectF(0, 0, 150, 60)
        self._tail_tip = tail_tip if tail_tip is not None else QPointF(75, 90)
        self._bg_color = QColor("#FFFFCC")
        self._border_color = QColor("#000000")
        self._border_width: float = 2.0
        self._border_radius: float = 4.0
        self._padding: float = 4.0
        self._vertical_align: VerticalAlign = VerticalAlign.CENTER

        font = QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
        color = QColor(Qt.GlobalColor.black)
        self._init_document(text, font, color)

    # --- backward-compat property shims ---

    @property
    def text(self) -> str:
        return self._get_text()

    @text.setter
    def text(self, value: str) -> None:
        self._set_text(value)
        self.update()

    @property
    def font(self) -> QFont:
        return self._get_font()

    @font.setter
    def font(self, value: QFont) -> None:
        self.prepareGeometryChange()
        self._set_font(value)
        self.update()

    @property
    def text_color(self) -> QColor:
        return self._get_text_color()

    @text_color.setter
    def text_color(self, value: QColor) -> None:
        self._set_text_color(value)
        self.update()

    @property
    def tail_tip(self) -> QPointF:
        return QPointF(self._tail_tip)

    @tail_tip.setter
    def tail_tip(self, value: QPointF) -> None:
        self.prepareGeometryChange()
        self._tail_tip = QPointF(value)
        self.update()

    @property
    def box_rect(self) -> QRectF:
        return QRectF(self._rect)

    @box_rect.setter
    def box_rect(self, value: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(value)
        self.update()

    # --- frame properties ---

    @property
    def bg_color(self) -> QColor:
        return QColor(self._bg_color)

    @bg_color.setter
    def bg_color(self, value: QColor) -> None:
        self._bg_color = QColor(value)
        self.update()

    @property
    def border_color(self) -> QColor:
        return QColor(self._border_color)

    @border_color.setter
    def border_color(self, value: QColor) -> None:
        self._border_color = QColor(value)
        self.update()

    @property
    def border_width(self) -> float:
        return self._border_width

    @border_width.setter
    def border_width(self, value: float) -> None:
        self.prepareGeometryChange()
        self._border_width = max(0.0, value)
        self.update()

    @property
    def border_radius(self) -> float:
        return self._border_radius

    @border_radius.setter
    def border_radius(self, value: float) -> None:
        self._border_radius = max(0.0, value)
        self.update()

    @property
    def padding(self) -> float:
        return self._padding

    @padding.setter
    def padding(self, value: float) -> None:
        self.prepareGeometryChange()
        self._padding = max(0.0, value)
        self.update()

    @property
    def vertical_align(self) -> VerticalAlign:
        return self._vertical_align

    @vertical_align.setter
    def vertical_align(self, value: VerticalAlign) -> None:
        self._vertical_align = value
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
        self._border_width = max(0.0, self._border_width * avg)
        self._border_radius = max(0.0, self._border_radius * avg)
        self._padding = max(0.0, self._padding * avg)

    def boundingRect(self) -> QRectF:
        r = self._rect.united(QRectF(self._tail_tip, self._tail_tip))
        half = self._border_width / 2
        margin = max(half, 1.0)
        return r.adjusted(-margin, -margin, margin, margin)

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
        pen = QPen(self._border_color, self._border_width)
        painter.setPen(pen)
        painter.setBrush(QBrush(self._bg_color))
        painter.drawPath(tail_path)
        # Draw box
        if self._border_radius > 0:
            painter.drawRoundedRect(
                self._rect, self._border_radius, self._border_radius
            )
        else:
            painter.drawRect(self._rect)

        # Draw edit-mode border
        if self._is_editing:
            painter.save()
            edit_pen = QPen(QColor("#0078d7"), 2)
            edit_pen.setCosmetic(True)
            painter.setPen(edit_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._rect)
            painter.restore()

        # Draw text via document with padding and vertical alignment
        p = self._padding
        content_w = max(1.0, self._rect.width() - 2 * p)
        content_h = max(1.0, self._rect.height() - 2 * p)
        doc_h = self.document_height(content_w)

        y_offset = self._rect.y() + p
        if self._vertical_align == VerticalAlign.CENTER:
            y_offset += max(0.0, (content_h - doc_h) / 2)
        elif self._vertical_align == VerticalAlign.BOTTOM:
            y_offset += max(0.0, content_h - doc_h)

        text_rect = QRectF(self._rect.x() + p, y_offset, content_w, doc_h)
        self.draw_document(painter, text_rect)

    def serialize(self) -> dict[str, Any]:
        font = self._document.defaultFont()
        return {
            "type": "CalloutItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "text": self._document.toPlainText(),
            "html": self._document.toHtml(),
            "rect": [self._rect.x(), self._rect.y(), self._rect.width(), self._rect.height()],
            "tail_tip": [self._tail_tip.x(), self._tail_tip.y()],
            "bg_color": self._bg_color.name(QColor.NameFormat.HexArgb),
            "border_color": self._border_color.name(QColor.NameFormat.HexArgb),
            "border_width": self._border_width,
            "border_radius": self._border_radius,
            "padding": self._padding,
            "vertical_align": self._vertical_align.value,
            "font_family": font.family(),
            "font_size": font.pointSize(),
            "text_color": self._get_text_color().name(QColor.NameFormat.HexArgb),
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
        item._border_width = data.get("border_width", 2.0)
        item._border_radius = data.get("border_radius", 4.0)
        item._padding = data.get("padding", 4.0)
        va_str = data.get("vertical_align", VerticalAlign.CENTER.value)
        try:
            item._vertical_align = VerticalAlign(va_str)
        except ValueError:
            item._vertical_align = VerticalAlign.CENTER

        if "html" in data:
            # Rich text: restore from HTML
            item._document.setHtml(data["html"])
            if "font_family" in data or "font_size" in data:
                font = QFont(
                    data.get("font_family", DEFAULT_FONT_FAMILY),
                    data.get("font_size", DEFAULT_FONT_SIZE),
                )
                item._document.setDefaultFont(font)
        else:
            # Legacy plain-text format
            if "font_family" in data or "font_size" in data:
                font = QFont(
                    data.get("font_family", DEFAULT_FONT_FAMILY),
                    data.get("font_size", DEFAULT_FONT_SIZE),
                )
                text_color = QColor(data.get("text_color", "#ff000000"))
                item._init_document(data.get("text", "Callout"), font, text_color)
            elif "text_color" in data:
                item._set_text_color(QColor(data["text_color"]))

        return item
