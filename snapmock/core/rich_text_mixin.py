"""RichTextMixin — shared QTextDocument-based rich text for TextItem and CalloutItem."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QTextCharFormat, QTextDocument


class RichTextMixin:
    """Mixin providing a QTextDocument data model for text-bearing items.

    Both TextItem and CalloutItem use this to replace plain ``str`` + ``QFont``
    + ``QColor`` with a single QTextDocument that supports rich text.
    """

    _document: QTextDocument
    _is_editing: bool

    def _init_document(
        self,
        text: str,
        font: QFont,
        color: QColor,
    ) -> None:
        """Initialise the QTextDocument with default text, font, and color."""
        self._document = QTextDocument()
        self._document.setDocumentMargin(0)
        self._document.setDefaultFont(font)
        self._is_editing = False

        self._document.setPlainText(text)
        # Apply color to all existing text
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        root = self._document.rootFrame()
        if root is not None:
            cursor = root.firstCursorPosition()
            cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(fmt)

    @property
    def text_document(self) -> QTextDocument:
        """Return the underlying QTextDocument."""
        return self._document

    @property
    def is_editing(self) -> bool:
        """True when the item is being edited inline."""
        return self._is_editing

    @is_editing.setter
    def is_editing(self, value: bool) -> None:
        self._is_editing = value

    def plain_text(self) -> str:
        """Return the document's plain text content."""
        return self._document.toPlainText()

    def html(self) -> str:
        """Return the document's HTML content."""
        return self._document.toHtml()

    def set_html(self, html: str) -> None:
        """Set the document's HTML content."""
        self._document.setHtml(html)

    def draw_document(self, painter: QPainter, text_rect: QRectF) -> None:
        """Render the document into *text_rect* using *painter*.

        The painter's current transform is used; the document is drawn at the
        top-left of *text_rect* with its text width set to ``text_rect.width()``.
        """
        self._document.setTextWidth(text_rect.width())
        painter.save()
        painter.translate(text_rect.topLeft())
        clip = QRectF(0, 0, text_rect.width(), text_rect.height())
        self._document.drawContents(painter, clip)
        painter.restore()

    def document_height(self, width: float) -> float:
        """Return the ideal document height for the given width."""
        self._document.setTextWidth(width)
        return self._document.size().height()

    # --- backward-compat property helpers ---

    def _get_text(self) -> str:
        return self._document.toPlainText()

    def _set_text(self, value: str) -> None:
        self._document.setPlainText(value)

    def _get_font(self) -> QFont:
        return QFont(self._document.defaultFont())

    def _set_font(self, value: QFont) -> None:
        self._document.setDefaultFont(QFont(value))
        # Update all existing text to the new font
        root = self._document.rootFrame()
        if root is not None:
            cursor = root.firstCursorPosition()
            cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setFont(
                value, QTextCharFormat.FontPropertiesInheritanceBehavior.FontPropertiesAll
            )
            cursor.mergeCharFormat(fmt)

    def _get_text_color(self) -> QColor:
        root = self._document.rootFrame()
        if root is not None:
            cursor = root.firstCursorPosition()
            fmt = cursor.charFormat()
            fg = fmt.foreground()
            if fg.style() != Qt.BrushStyle.NoBrush:
                return QColor(fg.color())
        return QColor(Qt.GlobalColor.black)

    def _set_text_color(self, value: QColor) -> None:
        root = self._document.rootFrame()
        if root is not None:
            cursor = root.firstCursorPosition()
            cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setForeground(value)
            cursor.mergeCharFormat(fmt)
