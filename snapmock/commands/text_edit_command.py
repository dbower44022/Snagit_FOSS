"""TextEditCommand — undo/redo for rich text editing sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from snapmock.core.command_stack import BaseCommand

if TYPE_CHECKING:
    from snapmock.core.rich_text_mixin import RichTextMixin

_TEXT_EDIT_MERGE_ID = 3000


class TextEditCommand(BaseCommand):
    """Stores before/after HTML snapshots of a text editing session.

    Pushed when the user finishes editing (Escape / click away).  The
    document's built-in undo handles per-keystroke undo *during* editing;
    this command handles app-level undo of the entire session.
    """

    def __init__(
        self,
        item: RichTextMixin,
        old_html: str,
        new_html: str,
    ) -> None:
        self._item = item
        self._old_html = old_html
        self._new_html = new_html

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
        if isinstance(other, TextEditCommand) and other._item is self._item:
            self._new_html = other._new_html
            return True
        return False
