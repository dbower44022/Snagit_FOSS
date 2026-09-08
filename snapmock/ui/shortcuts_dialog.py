"""KeyboardShortcutsDialog — the searchable shortcut reference (General UI PRD 3.8, 12).

The rows come from ``config/shortcuts.py`` (the global shortcuts of PRD 12.1),
the live capture hotkeys, and the fixed navigation and modifier conventions of
PRD 12.2 and 12.3.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from snapmock.config.shortcuts import ALTERNATE_SHORTCUTS, SHORTCUTS

CATEGORY_NAMES: dict[str, str] = {
    "file": "File",
    "edit": "Edit",
    "view": "View",
    "layer": "Layer",
    "image": "Image",
    "arrange": "Arrange",
    "tool": "Tools",
    "library": "Library",
    "capture": "Capture",
}

# Menu wording for the action ids whose derived name would differ from the menu.
ACTION_LABELS: dict[str, str] = {
    "file.open": "Open...",
    "file.save_as": "Save As...",
    "file.export": "Export...",
    "file.import_image": "Import Image...",
    "file.export_quick_png": "Export Quick (PNG)",
    "file.print": "Print...",
    "file.preferences": "Preferences...",
    "file.close_tab": "Close",
    "edit.delete": "Delete",
    "edit.select_all_text": "Select All Text",
    "view.fit_window": "Fit to Window",
    "view.actual_size": "Zoom to 100%",
    "view.toggle_grid": "Show Grid",
    "view.toggle_rulers": "Show Rulers",
    "view.zoom_to_selection": "Zoom to Selection",
    "view.snap_to_grid": "Snap to Grid",
    "image.crop_to_canvas": "Crop to Canvas",
    "layer.new": "New Layer",
    "layer.delete": "Delete Layer",
    "layer.merge_down": "Merge Down",
    "layer.flatten": "Flatten All",
    "layer.rename": "Rename Layer",
    "layer.move_up": "Move Layer Up",
    "layer.move_down": "Move Layer Down",
    "layer.move_to_top": "Move Layer to Top",
    "layer.move_to_bottom": "Move Layer to Bottom",
    "tool.select": "Select / Move",
    "tool.raster_select": "Raster Selection (Rectangle)",
    "tool.lasso_select": "Raster Selection (Freeform)",
    "tool.crop": "Crop Canvas",
    "tool.freehand": "Freehand / Pen",
    "tool.text": "Text Box",
    "tool.callout": "Callout Bubble",
    "tool.blur": "Blur / Pixelate",
    "tool.highlight": "Highlighter",
    "tool.numbered_step": "Numbered Step",
    "tool.stamp": "Stamp / Sticker",
    "tool.pan": "Pan / Hand",
    "tool.zoom": "Zoom",
    "library.toggle_panel": "Show Library Panel",
    "capture.region": "Capture Region",
    "capture.window": "Capture Active Window",
    "capture.full_screen": "Capture Full Screen",
    "capture.preferences": "Capture Preferences...",
}

# Fixed conventions (PRD 12.2 and 12.3) that are not QAction shortcuts.
NAVIGATION_ROWS: list[tuple[str, str, str]] = [
    ("Navigation", "Zoom in / out centred on the cursor", "Ctrl + Mouse Wheel"),
    ("Navigation", "Pan the canvas", "Middle Mouse Button + Drag"),
    ("Navigation", "Pan the canvas (temporary hand tool)", "Space + Left Mouse Drag"),
    ("Navigation", "Pan to canvas origin", "Home"),
    ("Navigation", "Pan to bottom-right corner of canvas", "End"),
    ("Navigation", "Nudge selected items 1 px", "Arrow Keys"),
    ("Navigation", "Nudge selected items 10 px", "Shift + Arrow Keys"),
    ("Navigation", "Cycle selection to next item on active layer", "Tab"),
    ("Navigation", "Cycle selection to previous item on active layer", "Shift + Tab"),
    ("Modifiers", "Constrain proportions or angles while drawing", "Shift"),
    ("Modifiers", "Draw from centre", "Alt"),
    ("Modifiers", "Add to selection", "Shift + Click"),
    ("Modifiers", "Toggle item in selection", "Ctrl + Click"),
    ("Modifiers", "Temporary pan tool", "Space (held)"),
    ("Modifiers", "Temporary eyedropper", "Alt (held)"),
]


@dataclass(frozen=True)
class ShortcutRow:
    category: str
    action: str
    keys: str


def action_label(action_id: str) -> str:
    """The menu wording for *action_id*, or a title-cased form of its last segment."""
    label = ACTION_LABELS.get(action_id)
    if label is not None:
        return label
    return action_id.split(".", 1)[1].replace("_", " ").title()


def _native(text: str) -> str:
    return QKeySequence(text).toString(QKeySequence.SequenceFormat.NativeText)


def shortcut_rows(capture_bindings: dict[str, str] | None = None) -> list[ShortcutRow]:
    """Every row the dialog shows, in category order then map order.

    *capture_bindings* maps the capture action ids to their live key text; when
    given they replace the defaults in the map (PRD 3.4 of the Screen Capture PRD).
    """
    rows: list[ShortcutRow] = []
    for action_id, text in SHORTCUTS.items():
        prefix = action_id.split(".", 1)[0]
        if capture_bindings is not None and action_id in capture_bindings:
            text = capture_bindings[action_id]
        keys = [text] + ALTERNATE_SHORTCUTS.get(action_id, [])
        shown = " / ".join(_native(k) for k in keys if k)
        if action_id == "tool.pan":
            shown = "Space (hold)"
        if not shown:
            continue
        rows.append(
            ShortcutRow(CATEGORY_NAMES.get(prefix, prefix.title()), action_label(action_id), shown)
        )
    rows.extend(ShortcutRow(c, a, k) for c, a, k in NAVIGATION_ROWS)
    order = list(CATEGORY_NAMES.values()) + ["Navigation", "Modifiers"]
    rows.sort(key=lambda r: order.index(r.category) if r.category in order else len(order))
    return rows


class KeyboardShortcutsDialog(QDialog):
    """Searchable reference of every shortcut (Help > Keyboard Shortcuts)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        capture_bindings: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(560, 620)
        self._rows = shortcut_rows(capture_bindings)

        layout = QVBoxLayout(self)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search actions or keys…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._table = QTableWidget(len(self._rows), 3)
        self._table.setHorizontalHeaderLabels(["Category", "Action", "Shortcut"])
        self._table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setShowGrid(False)
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for r, row in enumerate(self._rows):
            for c, text in enumerate((row.category, row.action, row.keys)):
                cell = QTableWidgetItem(text)
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(r, c, cell)
        layout.addWidget(self._table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self._search.setFocus()

    @property
    def rows(self) -> list[ShortcutRow]:
        return list(self._rows)

    def visible_rows(self) -> list[ShortcutRow]:
        return [row for r, row in enumerate(self._rows) if not self._table.isRowHidden(r)]

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for r, row in enumerate(self._rows):
            haystack = f"{row.category} {row.action} {row.keys}".lower()
            self._table.setRowHidden(r, bool(needle) and needle not in haystack)
