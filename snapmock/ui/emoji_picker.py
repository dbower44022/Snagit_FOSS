"""Emoji picker — the popover of PRD Section 4.2 and the skin-tone palette.

Numbered Steps, Stamps & Emoji PRD Section 4.2: a search field over names and keywords, the
recent row (the last 24 used, most recent first, for the session), the nine Unicode
categories as tabs over a grid of emoji drawn in the colour emoji font, a right-click on a
skin-tone-capable emoji opening the six-tone palette, the chosen tone remembered for the
session and shown in the grid, and the open category and scroll position remembered across
uses. A click chooses the emoji and closes the picker. Built on the colour picker's popover
pattern and placed beside its anchor, kept on screen.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from snapmock.core.emoji_data import (
    SKIN_TONE_SWATCHES,
    EmojiData,
    EmojiInfo,
    SkinTone,
    emoji_data,
)
from snapmock.items.emoji_item import resolved_emoji_family
from snapmock.ui.accessibility import apply_default_names

GRID_ICON = 32
RECENT_MAX = 24
"""The recent row's length (PRD 4.2)."""
PANEL_WIDTH = 340
GRID_ROWS = 6
NO_RESULTS_TEXT = "No emoji found for “{query}”"
_CHAR_ROLE = Qt.ItemDataRole.UserRole

_pixmap_cache: dict[tuple[str, int], QPixmap] = {}


def emoji_pixmap(chars: str, size: int) -> QPixmap:
    """*chars* drawn in the emoji font into a square *size* pixmap, cached (previews, the
    cursor, the grid)."""
    key = (chars, size)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if chars:
        family = resolved_emoji_family()
        font = QFont(family) if family else QFont()
        font.setPixelSize(max(1, int(round(size * 0.85))))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)
        painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, chars)
        painter.end()
    if len(_pixmap_cache) > 4096:
        _pixmap_cache.clear()
    _pixmap_cache[key] = pixmap
    return pixmap


class SkinTonePalette(QWidget):
    """The six skin-tone swatches (PRD 4.2), a popup beside the emoji that was right-clicked.

    Signals
    -------
    tone_chosen(SkinTone)
    """

    tone_chosen = pyqtSignal(object)

    def __init__(self, current: SkinTone, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAccessibleName("Skin tone palette")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.buttons: dict[SkinTone, QToolButton] = {}
        for tone in SkinTone:
            button = QToolButton()
            button.setFixedSize(26, 26)
            label = tone.value.replace("_", " ").title()
            button.setToolTip(f"Skin tone: {label}")
            button.setAccessibleName(f"Skin tone {label}")
            button.setCheckable(True)
            button.setChecked(tone is current)
            button.setStyleSheet(
                f"QToolButton {{ background: {SKIN_TONE_SWATCHES[tone]}; border: 1px solid #888;"
                " border-radius: 13px; }"
                " QToolButton:checked { border: 2px solid #1a73e8; }"
            )
            button.clicked.connect(lambda _checked=False, t=tone: self._choose(t))
            layout.addWidget(button)
            self.buttons[tone] = button

    def _choose(self, tone: SkinTone) -> None:
        self.tone_chosen.emit(tone)
        self.hide()


class _EmojiGrid(QListWidget):
    """The grid; a right-click on a capable emoji asks for the skin-tone palette."""

    tone_requested = pyqtSignal(QListWidgetItem)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.pos())
            if item is not None:
                self.tone_requested.emit(item)
                return
        super().mousePressEvent(event)


class EmojiPicker(QWidget):
    """The emoji picker popover (PRD 4.2).

    Signals
    -------
    emoji_chosen(str)
        The chosen sequence, toned when the session's tone applies; the picker closes.
    skin_tone_chosen(SkinTone)
        A tone chosen in the palette, remembered for the session.
    closed()
    """

    emoji_chosen = pyqtSignal(str)
    skin_tone_chosen = pyqtSignal(object)
    closed = pyqtSignal()

    def __init__(
        self,
        data: EmojiData | None = None,
        parent: QWidget | None = None,
        *,
        popup: bool = True,
    ) -> None:
        flags = Qt.WindowType.Popup if popup else Qt.WindowType.Widget
        super().__init__(parent, flags)
        self._data = data if data is not None else emoji_data()
        self._tone = SkinTone.DEFAULT
        self._recent: list[str] = []
        self._current: str = ""
        self._palette: SkinTonePalette | None = None
        self._palette_item: QListWidgetItem | None = None
        self.setAccessibleName("Emoji picker")
        self.setFixedWidth(PANEL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search emoji by name or keyword")
        self.search_edit.setAccessibleName("Search emoji")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._refresh)
        layout.addWidget(self.search_edit)

        self.recent_label = QLabel("Recent")
        self.recent_label.setAccessibleName("Recent emoji label")
        layout.addWidget(self.recent_label)
        self.recent_list = QListWidget()
        self.recent_list.setAccessibleName("Recent emoji")
        self._style_grid(self.recent_list, rows=1)
        self.recent_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.recent_list)

        self.tabs = QTabBar()
        self.tabs.setAccessibleName("Emoji categories")
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        for group in self._data.groups():
            index = self.tabs.addTab(group)
            self.tabs.setTabData(index, group)
        self.tabs.currentChanged.connect(self._refresh)
        layout.addWidget(self.tabs)

        self.grid = _EmojiGrid()
        self.grid.setAccessibleName("Emoji")
        self._style_grid(self.grid, rows=GRID_ROWS)
        self.grid.itemClicked.connect(self._on_item_clicked)
        self.grid.itemActivated.connect(self._on_item_clicked)
        self.grid.tone_requested.connect(self.show_skin_tone_palette)
        layout.addWidget(self.grid)

        self.empty_label = QLabel("")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setAccessibleName("Emoji picker message")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        apply_default_names(self)
        self._refresh()

    @staticmethod
    def _style_grid(widget: QListWidget, *, rows: int) -> None:
        widget.setViewMode(QListWidget.ViewMode.IconMode)
        widget.setIconSize(QSize(GRID_ICON, GRID_ICON))
        widget.setGridSize(QSize(GRID_ICON + 8, GRID_ICON + 8))
        widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        widget.setMovement(QListWidget.Movement.Static)
        widget.setUniformItemSizes(True)
        widget.setFixedHeight(rows * (GRID_ICON + 8) + 6)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    # --- state (PRD 4.2: the session memories) ---

    @property
    def skin_tone(self) -> SkinTone:
        return self._tone

    def set_skin_tone(self, tone: SkinTone) -> None:
        """The session's tone; capable emoji in the grid show it."""
        if tone is not self._tone:
            self._tone = tone
            self._refresh()

    @property
    def recent(self) -> list[str]:
        return list(self._recent)

    def note_used(self, chars: str) -> None:
        """Move *chars* to the front of the recent row, capped at 24 (PRD 4.2)."""
        self._recent = [chars, *[c for c in self._recent if c != chars]][:RECENT_MAX]
        self._fill_recent()

    @property
    def current_group(self) -> str:
        data = self.tabs.tabData(self.tabs.currentIndex())
        return str(data) if data is not None else ""

    def set_group(self, group: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabData(index) == group:
                self.tabs.setCurrentIndex(index)
                return

    def set_current(self, chars: str) -> None:
        """Highlight *chars* and open its category (a Change Emoji opens here)."""
        self._current = chars
        info = self._data.lookup(chars)
        if info is not None:
            self.set_group(info.group)
        self._refresh()

    def visible_chars(self) -> list[str]:
        return [
            str(self.grid.item(i).data(_CHAR_ROLE))  # type: ignore[union-attr]
            for i in range(self.grid.count())
        ]

    # --- the grid ---

    def _display_char(self, info: EmojiInfo) -> str:
        if info.skin_tones and self._tone is not SkinTone.DEFAULT:
            return self._data.toned(info.char, self._tone)
        return info.char

    def _make_item(self, chars: str, name: str) -> QListWidgetItem:
        item = QListWidgetItem(QIcon(emoji_pixmap(chars, GRID_ICON)), "")
        item.setData(_CHAR_ROLE, chars)
        item.setToolTip(name)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, name)
        return item

    def _refresh(self, *_args: object) -> None:
        query = self.search_edit.text().strip()
        searching = bool(query)
        self.tabs.setVisible(not searching)
        self.recent_label.setVisible(not searching and bool(self._recent))
        self.recent_list.setVisible(not searching and bool(self._recent))
        entries = (
            self._data.search(query) if searching else self._data.in_group(self.current_group)
        )
        scroll = self.grid.verticalScrollBar()
        position = scroll.value() if scroll is not None else 0
        self.grid.clear()
        current_base = self._data.lookup(self._current)
        for info in entries:
            item = self._make_item(self._display_char(info), info.name)
            self.grid.addItem(item)
            if current_base is not None and info.char == current_base.char:
                item.setSelected(True)
                self.grid.setCurrentItem(item)
        if entries:
            self.empty_label.setVisible(False)
            if scroll is not None and not searching and self.grid.currentItem() is None:
                scroll.setValue(position)
        else:
            self.empty_label.setText(NO_RESULTS_TEXT.format(query=query))
            self.empty_label.setVisible(True)
        self._fill_recent()

    def _fill_recent(self) -> None:
        self.recent_list.clear()
        for chars in self._recent:
            self.recent_list.addItem(self._make_item(chars, self._data.name_of(chars)))
        has_recent = bool(self._recent) and not self.search_edit.text().strip()
        self.recent_label.setVisible(has_recent)
        self.recent_list.setVisible(has_recent)

    def _on_item_clicked(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        chars = str(item.data(_CHAR_ROLE))
        self._current = chars
        self.emoji_chosen.emit(chars)
        self.hide()

    # --- the skin-tone palette (PRD 4.2) ---

    def show_skin_tone_palette(self, item: QListWidgetItem) -> SkinTonePalette | None:
        """The six tones beside *item* when its emoji takes one; None otherwise."""
        info = self._data.lookup(str(item.data(_CHAR_ROLE)))
        if info is None or not info.skin_tones:
            return None
        if self._palette is not None:
            self._palette.hide()
            self._palette.deleteLater()
        self._palette = SkinTonePalette(self._tone, self)
        self._palette_item = item
        self._palette.tone_chosen.connect(self._on_palette_tone)
        rect = self.grid.visualItemRect(item)
        anchor = self.grid.viewport().mapToGlobal(rect.bottomLeft())  # type: ignore[union-attr]
        self._palette.adjustSize()
        self._palette.move(anchor)
        self._palette.show()
        return self._palette

    def _on_palette_tone(self, tone: object) -> None:
        if not isinstance(tone, SkinTone):
            return
        self._tone = tone
        self.skin_tone_chosen.emit(tone)
        item = self._palette_item
        self._palette_item = None
        picked = str(item.data(_CHAR_ROLE)) if item is not None else ""
        self._refresh()  # the grid now shows the tone; the old items are gone
        base = self._data.lookup(picked) if picked else None
        if base is not None:
            chars = self._display_char(base)
            self._current = chars
            self.emoji_chosen.emit(chars)
            self.hide()

    # --- placement ---

    def open_beside(self, anchor: QWidget | None, fallback: QPoint | None = None) -> None:
        """Show below *anchor* (or at *fallback*), kept on the screen; the open category and
        scroll position are as they were left (PRD 4.2)."""
        self.search_edit.clear()
        self._refresh()
        self.adjustSize()
        size = self.sizeHint()
        if anchor is not None:
            point = anchor.mapToGlobal(QPoint(0, anchor.height() + 2))
        elif fallback is not None:
            point = QPoint(fallback)
        else:
            point = QPoint(100, 100)
        x, y = point.x(), point.y()
        screen = QApplication.screenAt(point)
        if screen is not None:
            available = screen.availableGeometry()
            if x + size.width() > available.right():
                x = max(available.left(), available.right() - size.width())
            if y + size.height() > available.bottom():
                above = (
                    anchor.mapToGlobal(QPoint(0, 0)).y() - size.height() - 2
                    if anchor is not None
                    else available.bottom() - size.height()
                )
                y = max(available.top(), above)
        self.move(x, y)
        self.show()
        self.search_edit.setFocus()

    def hideEvent(self, event: object) -> None:  # noqa: N802
        super().hideEvent(event)  # type: ignore[arg-type]
        self.closed.emit()
