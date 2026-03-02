"""TextFormatCommand — undo/redo for text formatting changes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtGui import QTextCharFormat, QTextCursor

from snapmock.core.command_stack import BaseCommand

if TYPE_CHECKING:
    from snapmock.core.rich_text_mixin import RichTextMixin

_TEXT_FORMAT_MERGE_ID = 3001


class TextFormatCommand(BaseCommand):
    """Records a formatting change applied to a text selection.

    Stores per-character old format values so that undo restores each
    character position to its original formatting.
    """

    def __init__(
        self,
        item: RichTextMixin,
        selection_start: int,
        selection_end: int,
        format_property: str,
        old_values: dict[int, Any],
        new_value: Any,
    ) -> None:
        self._item = item
        self._selection_start = selection_start
        self._selection_end = selection_end
        self._format_property = format_property
        self._old_values = old_values
        self._new_value = new_value

    def redo(self) -> None:
        cursor = QTextCursor(self._item.text_document)
        cursor.setPosition(self._selection_start)
        cursor.setPosition(self._selection_end, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        self._apply_format_value(fmt, self._format_property, self._new_value)
        cursor.mergeCharFormat(fmt)

    def undo(self) -> None:
        for pos, old_val in self._old_values.items():
            cursor = QTextCursor(self._item.text_document)
            cursor.setPosition(pos)
            cursor.setPosition(pos + 1, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            self._apply_format_value(fmt, self._format_property, old_val)
            cursor.mergeCharFormat(fmt)

    @staticmethod
    def _apply_format_value(fmt: QTextCharFormat, prop: str, value: Any) -> None:
        """Apply a format value to a QTextCharFormat by property name."""
        from PyQt6.QtGui import QColor, QFont

        if prop == "bold":
            fmt.setFontWeight(QFont.Weight.Bold if value else QFont.Weight.Normal)
        elif prop == "italic":
            fmt.setFontItalic(bool(value))
        elif prop == "underline":
            fmt.setFontUnderline(bool(value))
        elif prop == "strikethrough":
            fmt.setFontStrikeOut(bool(value))
        elif prop == "font_size":
            fmt.setFontPointSize(float(value))
        elif prop == "font_family":
            fmt.setFontFamilies([str(value)])
        elif prop == "foreground":
            fmt.setForeground(QColor(value))
        elif prop == "background":
            fmt.setBackground(QColor(value))

    @property
    def description(self) -> str:
        return f"Format text {self._format_property}"

    @property
    def merge_id(self) -> int:
        return 0  # Format commands don't merge — each is a separate undo step
