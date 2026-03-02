"""RichTextMixin — shared QTextDocument-based rich text for TextItem and CalloutItem."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
)


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

    # --- paragraph-level formatting ---

    def get_block_format(self, cursor: QTextCursor | None = None) -> QTextBlockFormat:
        """Return the QTextBlockFormat for the block at *cursor* (or first block)."""
        if cursor is None:
            root = self._document.rootFrame()
            if root is None:
                return QTextBlockFormat()
            cursor = root.firstCursorPosition()
        return cursor.blockFormat()

    def set_block_format(
        self, fmt: QTextBlockFormat, cursor: QTextCursor | None = None
    ) -> None:
        """Merge *fmt* into all blocks touched by *cursor* (or the entire document)."""
        if cursor is None:
            root = self._document.rootFrame()
            if root is None:
                return
            cursor = root.firstCursorPosition()
            cursor.movePosition(
                QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
            )
        cursor.mergeBlockFormat(fmt)

    def set_alignment(
        self,
        alignment: Qt.AlignmentFlag,
        cursor: QTextCursor | None = None,
    ) -> None:
        """Set paragraph alignment for blocks touched by *cursor*."""
        fmt = QTextBlockFormat()
        fmt.setAlignment(alignment)
        self.set_block_format(fmt, cursor)

    def set_line_height(
        self,
        height: float,
        height_type: int = QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        cursor: QTextCursor | None = None,
    ) -> None:
        """Set line spacing for blocks touched by *cursor*.

        *height_type* defaults to ``ProportionalHeight`` (percentage, e.g. 150 = 1.5x).
        """
        fmt = QTextBlockFormat()
        fmt.setLineHeight(height, height_type)
        self.set_block_format(fmt, cursor)

    def set_text_indent(
        self, indent: float, cursor: QTextCursor | None = None
    ) -> None:
        """Set first-line text indent (in pixels) for blocks touched by *cursor*."""
        fmt = QTextBlockFormat()
        fmt.setTextIndent(indent)
        self.set_block_format(fmt, cursor)

    def set_indent(self, level: int, cursor: QTextCursor | None = None) -> None:
        """Set block indent level for blocks touched by *cursor*."""
        fmt = QTextBlockFormat()
        fmt.setIndent(level)
        self.set_block_format(fmt, cursor)

    def set_space_before(
        self, spacing: float, cursor: QTextCursor | None = None
    ) -> None:
        """Set space above paragraph (in pixels)."""
        fmt = QTextBlockFormat()
        fmt.setTopMargin(spacing)
        self.set_block_format(fmt, cursor)

    def set_space_after(
        self, spacing: float, cursor: QTextCursor | None = None
    ) -> None:
        """Set space below paragraph (in pixels)."""
        fmt = QTextBlockFormat()
        fmt.setBottomMargin(spacing)
        self.set_block_format(fmt, cursor)

    def toggle_list(
        self,
        style: QTextListFormat.Style,
        cursor: QTextCursor | None = None,
    ) -> None:
        """Toggle a list style on the blocks at *cursor*.

        If the current block is already in a list with the given *style*,
        remove it from the list.  Otherwise create or change to that style.
        """
        if cursor is None:
            root = self._document.rootFrame()
            if root is None:
                return
            cursor = root.firstCursorPosition()
        current_list = cursor.currentList()
        if current_list is not None and current_list.format().style() == style:
            # Remove from list — reset indent and clear list format
            fmt = QTextBlockFormat()
            fmt.setIndent(0)
            cursor.setBlockFormat(fmt)
        else:
            list_fmt = QTextListFormat()
            list_fmt.setStyle(style)
            cursor.createList(list_fmt)
