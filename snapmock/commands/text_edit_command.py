"""TextEditCommand — undo/redo for rich text editing sessions."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QRectF

from snapmock.core.command_stack import BaseCommand

if TYPE_CHECKING:
    from snapmock.core.rich_text_mixin import RichTextMixin

_TEXT_EDIT_MERGE_ID = 3000
_MERGE_TIMEOUT_MS = 1000


class TextEditCommand(BaseCommand):
    """Stores before/after HTML snapshots of a text editing session.

    Pushed when the user finishes editing (Escape / click away).  The
    document's built-in undo handles per-keystroke undo *during* editing;
    this command handles app-level undo of the entire session.

    Merge boundaries (prevent merging):
    - Formatting changes (bold, italic, font, size, color)
    - Paragraph operations (Enter, Shift+Enter)
    - Clipboard operations (paste, cut)
    - Selection replacements (typing while text is selected)
    - A pause of more than 1000ms between keystrokes
    """

    def __init__(
        self,
        item: RichTextMixin,
        old_html: str,
        new_html: str,
        old_rect: QRectF | None = None,
        new_rect: QRectF | None = None,
        cursor_position: int = 0,
        is_format_change: bool = False,
        is_paragraph_op: bool = False,
        is_clipboard_op: bool = False,
        is_selection_replace: bool = False,
    ) -> None:
        self._item = item
        self._old_html = old_html
        self._new_html = new_html
        self._old_rect = old_rect
        self._new_rect = new_rect
        self._cursor_position = cursor_position
        self._is_format_change = is_format_change
        self._is_paragraph_op = is_paragraph_op
        self._is_clipboard_op = is_clipboard_op
        self._is_selection_replace = is_selection_replace
        self._timestamp = time.monotonic()

    def redo(self) -> None:
        self._item.set_html(self._new_html)

    def undo(self) -> None:
        self._item.set_html(self._old_html)

    @property
    def description(self) -> str:
        return "Edit text"

    @property
    def merge_id(self) -> int:
        return _TEXT_EDIT_MERGE_ID

    def merge_with(self, other: BaseCommand) -> bool:
        if not isinstance(other, TextEditCommand):
            return False
        if other._item is not self._item:
            return False
        # Merge boundaries: don't merge if either command is a special operation
        if (
            self._is_format_change
            or other._is_format_change
            or self._is_paragraph_op
            or other._is_paragraph_op
            or self._is_clipboard_op
            or other._is_clipboard_op
            or self._is_selection_replace
            or other._is_selection_replace
        ):
            return False
        # Timeout boundary
        elapsed_ms = (other._timestamp - self._timestamp) * 1000
        if elapsed_ms > _MERGE_TIMEOUT_MS:
            return False
        # Merge: keep old state, take new state
        self._new_html = other._new_html
        self._new_rect = other._new_rect
        self._cursor_position = other._cursor_position
        self._timestamp = other._timestamp
        return True
