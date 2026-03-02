"""TextItem — editable rich text annotation with optional frame."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from snapmock.config.constants import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_TEXT_BG_COLOR,
    DEFAULT_TEXT_BORDER_COLOR,
    DEFAULT_TEXT_BORDER_RADIUS,
    DEFAULT_TEXT_BORDER_WIDTH,
    DEFAULT_TEXT_PADDING,
    DEFAULT_TEXT_WIDTH,
    VerticalAlign,
)
from snapmock.core.rich_text_mixin import RichTextMixin
from snapmock.items.base_item import SnapGraphicsItem


class TextItem(RichTextMixin, SnapGraphicsItem):
    """An editable text annotation item backed by QTextDocument."""

    def __init__(
        self,
        text: str = "Text",
        pos_x: float = 0,
        pos_y: float = 0,
        parent: SnapGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        font = QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
        color = QColor(Qt.GlobalColor.black)
        self._init_document(text, font, color)
        self._width: float = DEFAULT_TEXT_WIDTH
        self._height: float | None = None  # None = auto-size from document
        self._bg_color: QColor = QColor(DEFAULT_TEXT_BG_COLOR)
        self._border_color: QColor = QColor(DEFAULT_TEXT_BORDER_COLOR)
        self._border_width: float = DEFAULT_TEXT_BORDER_WIDTH
        self._border_radius: float = DEFAULT_TEXT_BORDER_RADIUS
        self._padding: float = DEFAULT_TEXT_PADDING
        self._vertical_align: VerticalAlign = VerticalAlign.TOP
        self._auto_size: bool = True
        self.setPos(pos_x, pos_y)

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
    def text_width(self) -> float:
        return self._width

    @text_width.setter
    def text_width(self, value: float) -> None:
        self.prepareGeometryChange()
        self._width = max(20.0, value)
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

    @property
    def auto_size(self) -> bool:
        return self._auto_size

    @auto_size.setter
    def auto_size(self, value: bool) -> None:
        self.prepareGeometryChange()
        self._auto_size = value
        if value:
            self._height = None
        self.update()

    @property
    def text_height(self) -> float | None:
        return self._height

    @text_height.setter
    def text_height(self, value: float | None) -> None:
        self.prepareGeometryChange()
        self._height = value
        self.update()

    # --- geometry helpers ---

    def _content_width(self) -> float:
        return max(1.0, self._width - 2 * self._padding)

    def _frame_height(self) -> float:
        if self._auto_size or self._height is None:
            return self.document_height(self._content_width()) + 2 * self._padding
        return self._height

    def scale_geometry(self, sx: float, sy: float) -> None:
        self.prepareGeometryChange()
        avg = (sx + sy) / 2.0
        self._width = max(20.0, self._width * sx)
        if self._height is not None:
            self._height = max(1.0, self._height * sy)
        self._padding = max(0.0, self._padding * avg)
        self._border_width = max(0.0, self._border_width * avg)
        self._border_radius = max(0.0, self._border_radius * avg)

    def boundingRect(self) -> QRectF:
        frame = QRectF(0, 0, self._width, self._frame_height())
        half = self._border_width / 2
        return frame.adjusted(-half, -half, half, half)

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return

        frame_rect = QRectF(0, 0, self._width, self._frame_height())

        # Draw background fill (if alpha > 0)
        if self._bg_color.alpha() > 0:
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._bg_color))
            if self._border_radius > 0:
                painter.drawRoundedRect(
                    frame_rect, self._border_radius, self._border_radius
                )
            else:
                painter.drawRect(frame_rect)
            painter.restore()

        # Draw border (if width > 0 and alpha > 0)
        if self._border_width > 0 and self._border_color.alpha() > 0:
            painter.save()
            pen = QPen(self._border_color, self._border_width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if self._border_radius > 0:
                painter.drawRoundedRect(
                    frame_rect, self._border_radius, self._border_radius
                )
            else:
                painter.drawRect(frame_rect)
            painter.restore()

        # Draw edit-mode indicator
        if self._is_editing:
            painter.save()
            pen = QPen(QColor("#0078d7"), 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(frame_rect)
            painter.restore()

        # Compute text rect with padding and vertical alignment
        content_w = self._content_width()
        doc_h = self.document_height(content_w)
        frame_h = frame_rect.height()
        inner_h = frame_h - 2 * self._padding

        y_offset = self._padding
        if self._vertical_align == VerticalAlign.CENTER:
            y_offset += max(0.0, (inner_h - doc_h) / 2)
        elif self._vertical_align == VerticalAlign.BOTTOM:
            y_offset += max(0.0, inner_h - doc_h)

        text_rect = QRectF(self._padding, y_offset, content_w, doc_h)
        self.draw_document(painter, text_rect)

    def serialize(self) -> dict[str, Any]:
        font = self._document.defaultFont()
        return {
            "type": "TextItem",
            "item_id": self.item_id,
            "layer_id": self.layer_id,
            "pos": [self.pos().x(), self.pos().y()],
            "text": self._document.toPlainText(),
            "html": self._document.toHtml(),
            "font_family": font.family(),
            "font_size": font.pointSize(),
            "color": self._get_text_color().name(QColor.NameFormat.HexArgb),
            "width": self._width,
            "height": self._height,
            "bg_color": self._bg_color.name(QColor.NameFormat.HexArgb),
            "border_color": self._border_color.name(QColor.NameFormat.HexArgb),
            "border_width": self._border_width,
            "border_radius": self._border_radius,
            "padding": self._padding,
            "vertical_align": self._vertical_align.value,
            "auto_size": self._auto_size,
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> TextItem:
        item = cls(text=data.get("text", "Text"))
        pos = data.get("pos", [0, 0])
        item.setPos(pos[0], pos[1])
        item.item_id = data.get("item_id", item.item_id)
        item.layer_id = data.get("layer_id", "")
        item._width = data.get("width", DEFAULT_TEXT_WIDTH)

        # Frame properties (backward-compat defaults: transparent/zero)
        item._height = data.get("height", None)
        item._bg_color = QColor(data.get("bg_color", DEFAULT_TEXT_BG_COLOR))
        item._border_color = QColor(data.get("border_color", DEFAULT_TEXT_BORDER_COLOR))
        item._border_width = data.get("border_width", DEFAULT_TEXT_BORDER_WIDTH)
        item._border_radius = data.get("border_radius", DEFAULT_TEXT_BORDER_RADIUS)
        item._padding = data.get("padding", DEFAULT_TEXT_PADDING)
        va_str = data.get("vertical_align", VerticalAlign.TOP.value)
        try:
            item._vertical_align = VerticalAlign(va_str)
        except ValueError:
            item._vertical_align = VerticalAlign.TOP
        item._auto_size = data.get("auto_size", True)

        if "html" in data:
            # Rich text: restore from HTML
            item._document.setHtml(data["html"])
            # Restore default font from serialized values for consistency
            font = QFont(
                data.get("font_family", DEFAULT_FONT_FAMILY),
                data.get("font_size", DEFAULT_FONT_SIZE),
            )
            item._document.setDefaultFont(font)
        else:
            # Legacy plain-text format
            font = QFont(
                data.get("font_family", DEFAULT_FONT_FAMILY),
                data.get("font_size", DEFAULT_FONT_SIZE),
            )
            color = QColor(data.get("color", "#ff000000"))
            item._init_document(data.get("text", "Text"), font, color)

        return item
