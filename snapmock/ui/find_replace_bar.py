"""FindReplaceBar — inline find/replace bar for rich text editing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor, QTextDocument
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

if TYPE_CHECKING:
    pass

_HIGHLIGHT_COLOR = QColor("#FFFF00")  # Yellow match highlight
_CURRENT_HIGHLIGHT_COLOR = QColor("#FF8C00")  # Orange for current match


class FindReplaceBar(QWidget):
    """Inline find/replace bar that operates on a QTextDocument.

    Emits ``closed`` when the user dismisses the bar (Escape or Close button).
    Emits ``replace_all_requested(old_html, new_html)`` when Replace All is used,
    so the caller can push a single undo command for the batch operation.
    """

    closed = pyqtSignal()
    replace_all_requested = pyqtSignal(str, str)  # old_html, new_html

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document: QTextDocument | None = None
        self._matches: list[tuple[int, int]] = []  # (start, length) pairs
        self._current_match: int = -1
        self._extra_selections_callback = None
        self._show_replace = False

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Search field
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Find...")
        self._search_field.setMaximumWidth(200)
        self._search_field.textChanged.connect(self._on_search_changed)
        self._search_field.returnPressed.connect(self.find_next)
        layout.addWidget(self._search_field)

        # Previous / Next
        self._prev_btn = QPushButton("<")
        self._prev_btn.setFixedWidth(28)
        self._prev_btn.setToolTip("Previous (Shift+Enter)")
        self._prev_btn.clicked.connect(self.find_prev)
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton(">")
        self._next_btn.setFixedWidth(28)
        self._next_btn.setToolTip("Next (Enter)")
        self._next_btn.clicked.connect(self.find_next)
        layout.addWidget(self._next_btn)

        # Case sensitive toggle
        self._case_cb = QCheckBox("Aa")
        self._case_cb.setToolTip("Case sensitive")
        self._case_cb.toggled.connect(self._on_search_changed)
        layout.addWidget(self._case_cb)

        # Match count label
        self._match_label = QPushButton("")
        self._match_label.setFlat(True)
        self._match_label.setEnabled(False)
        self._match_label.setFixedWidth(60)
        layout.addWidget(self._match_label)

        # Replace field (hidden by default)
        self._replace_field = QLineEdit()
        self._replace_field.setPlaceholderText("Replace...")
        self._replace_field.setMaximumWidth(200)
        self._replace_field.setVisible(False)
        layout.addWidget(self._replace_field)

        self._replace_btn = QPushButton("Replace")
        self._replace_btn.setVisible(False)
        self._replace_btn.clicked.connect(self._replace_current)
        layout.addWidget(self._replace_btn)

        self._replace_all_btn = QPushButton("All")
        self._replace_all_btn.setToolTip("Replace All")
        self._replace_all_btn.setVisible(False)
        self._replace_all_btn.clicked.connect(self._replace_all)
        layout.addWidget(self._replace_all_btn)

        # Close button
        close_btn = QPushButton("x")
        close_btn.setFixedWidth(24)
        close_btn.setToolTip("Close (Escape)")
        close_btn.clicked.connect(self._close)
        layout.addWidget(close_btn)

        layout.addStretch()
        self.setStyleSheet(
            "FindReplaceBar {"
            "  background: #f0f0f0;"
            "  border: 1px solid #ccc;"
            "  border-radius: 3px;"
            "}"
        )

    def attach(self, document: QTextDocument) -> None:
        """Attach to a QTextDocument for searching."""
        self._document = document
        self._matches.clear()
        self._current_match = -1

    def detach(self) -> None:
        """Detach from the current document and clear highlights."""
        self._clear_highlights()
        self._document = None
        self._matches.clear()
        self._current_match = -1

    def show_find(self) -> None:
        """Show the find bar (no replace fields)."""
        self._show_replace = False
        self._replace_field.setVisible(False)
        self._replace_btn.setVisible(False)
        self._replace_all_btn.setVisible(False)
        self.setVisible(True)
        self._search_field.setFocus()
        self._search_field.selectAll()

    def show_find_replace(self) -> None:
        """Show the find bar with replace fields."""
        self._show_replace = True
        self._replace_field.setVisible(True)
        self._replace_btn.setVisible(True)
        self._replace_all_btn.setVisible(True)
        self.setVisible(True)
        self._search_field.setFocus()
        self._search_field.selectAll()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.find_prev()
            else:
                self.find_next()
            return
        super().keyPressEvent(event)

    def find_next(self) -> None:
        """Move to the next match."""
        if not self._matches:
            return
        self._current_match = (self._current_match + 1) % len(self._matches)
        self._update_highlights()
        self._scroll_to_current()

    def find_prev(self) -> None:
        """Move to the previous match."""
        if not self._matches:
            return
        self._current_match = (self._current_match - 1) % len(self._matches)
        self._update_highlights()
        self._scroll_to_current()

    @property
    def match_count(self) -> int:
        """Number of matches found."""
        return len(self._matches)

    @property
    def current_match_index(self) -> int:
        """Index of the current match (0-based), or -1 if none."""
        return self._current_match

    def _on_search_changed(self, _: object = None) -> None:
        """Re-run the search when the query or options change."""
        self._find_all()
        self._update_highlights()

    def _find_all(self) -> None:
        """Find all occurrences of the search text in the document."""
        self._matches.clear()
        self._current_match = -1

        if self._document is None:
            self._update_match_label()
            return

        query = self._search_field.text()
        if not query:
            self._update_match_label()
            return

        flags = QTextDocument.FindFlag(0)
        if self._case_cb.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        cursor = QTextCursor(self._document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        while True:
            found = self._document.find(query, cursor, flags)
            if found.isNull() or not found.hasSelection():
                break
            start = found.selectionStart()
            length = found.selectionEnd() - start
            self._matches.append((start, length))
            cursor = found
            cursor.movePosition(QTextCursor.MoveOperation.Right)

        if self._matches:
            self._current_match = 0
        self._update_match_label()

    def _update_match_label(self) -> None:
        if not self._matches:
            if self._search_field.text():
                self._match_label.setText("0/0")
            else:
                self._match_label.setText("")
        else:
            self._match_label.setText(
                f"{self._current_match + 1}/{len(self._matches)}"
            )

    def _update_highlights(self) -> None:
        """Apply yellow highlights to all matches, orange to current match."""
        self._clear_highlights()

        if self._document is None or not self._matches:
            self._update_match_label()
            return

        for i, (start, length) in enumerate(self._matches):
            cursor = QTextCursor(self._document)
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            if i == self._current_match:
                fmt.setBackground(_CURRENT_HIGHLIGHT_COLOR)
            else:
                fmt.setBackground(_HIGHLIGHT_COLOR)
            cursor.mergeCharFormat(fmt)

        self._update_match_label()

    def _clear_highlights(self) -> None:
        """Remove all search highlights from the document."""
        if self._document is None:
            return
        cursor = QTextCursor(self._document)
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.clearBackground()
        cursor.mergeCharFormat(fmt)

    def _scroll_to_current(self) -> None:
        """Ensure the current match is visible (by selecting it)."""
        if self._document is None or self._current_match < 0:
            return
        start, length = self._matches[self._current_match]
        # The parent editor should handle scrolling; we just set selection
        parent = self.parent()
        if parent is not None and hasattr(parent, "textCursor"):
            cursor = QTextCursor(self._document)
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            parent.setTextCursor(cursor)  # type: ignore[attr-defined]

    def _replace_current(self) -> None:
        """Replace the current match with the replace text."""
        if (
            self._document is None
            or self._current_match < 0
            or not self._matches
        ):
            return

        start, length = self._matches[self._current_match]
        replacement = self._replace_field.text()

        cursor = QTextCursor(self._document)
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)

        # Re-search after replacement
        self._find_all()
        self._update_highlights()

    def _replace_all(self) -> None:
        """Replace all matches. Emits replace_all_requested for undo support."""
        if self._document is None or not self._matches:
            return

        old_html = self._document.toHtml()
        replacement = self._replace_field.text()

        # Replace in reverse order to preserve positions
        for start, length in reversed(self._matches):
            cursor = QTextCursor(self._document)
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(replacement)

        new_html = self._document.toHtml()
        self.replace_all_requested.emit(old_html, new_html)

        # Re-search
        self._find_all()
        self._update_highlights()

    def _close(self) -> None:
        """Close the find/replace bar."""
        self._clear_highlights()
        self.setVisible(False)
        self.closed.emit()
