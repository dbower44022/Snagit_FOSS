"""Manage Presets dialog: rename, duplicate, and delete one tool's presets (General UI PRD 11.9).

Opened from the preset dropdown's Manage Presets... row. Every row shows the preset's
name and a compact summary of its values; Rename edits the name in place; Duplicate
copies with the " Copy" suffix; Delete confirms first. Changes apply to the preset files
immediately. Presets are not document state, so they are not on any command stack and
the changes here are not undoable (a recorded departure from Section 11.9).
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from snapmock.ui.tool_options_bar import SHARED_CONTROLS
from snapmock.ui.unmet_requirements import check_requirements

if TYPE_CHECKING:
    from snapmock.core.tool_themes import ToolThemeManager, ToolValues

_KEY_LABELS: dict[str, str] = {
    "text_color": "Text",
    "bg_color": "Background",
    "border_color": "Border",
    "border_width": "Border width",
    "border_radius": "Radius",
    "padding": "Padding",
    "bold": "Bold",
    "italic": "Italic",
    "underline": "Underline",
    "auto_size": "Auto size",
    "horizontal_align": "Align",
    "vertical_align": "Vertical",
    "bubble_shape": "Bubble",
    "tail_style": "Tail",
    "tail_width": "Tail width",
    "opacity_pct": "Opacity",
    "smoothing": "Smoothing",
    "start_number": "Start at",
}

_ALIGN_NAMES: dict[int, str] = {
    int(Qt.AlignmentFlag.AlignLeft.value): "left",
    int(Qt.AlignmentFlag.AlignHCenter.value): "centre",
    int(Qt.AlignmentFlag.AlignRight.value): "right",
    int(Qt.AlignmentFlag.AlignJustify.value): "justify",
}


def _label(key: str) -> str:
    spec = SHARED_CONTROLS.get(key)
    if spec is not None and spec.label:
        return spec.label
    return _KEY_LABELS.get(key, key.replace("_", " ").capitalize())


def _swatch(color: QColor) -> str:
    if color.alpha() == 0:
        return "transparent"
    hex_text = color.name(QColor.NameFormat.HexRgb).upper()
    return f'<span style="color:{hex_text}">&#9632;</span> {hex_text}'


def _fragment(key: str, value: object) -> str | None:
    """One "Label value" fragment for the summary, or None to leave the key out."""
    label = escape(_label(key))
    if isinstance(value, QColor):
        return f"{label} {_swatch(value)}"
    if isinstance(value, bool):
        return label if value else None
    if isinstance(value, int | float):
        spec = SHARED_CONTROLS.get(key)
        suffix = spec.suffix.strip() if spec is not None else ""
        scale = spec.scale if spec is not None else 1.0
        number = f"{round(value * scale, 6):g}"
        return f"{label} {number}{' ' + suffix if suffix else ''}"
    if isinstance(value, Qt.AlignmentFlag):
        return f"{label} {_ALIGN_NAMES.get(int(value.value), 'left')}"
    if hasattr(value, "value") and isinstance(getattr(value, "value", None), str):
        return f"{label} {escape(str(value.value).replace('_', ' '))}"
    if isinstance(value, str):
        return f"{label} {escape(value)}"
    return None


def summarise_values(values: ToolValues, order: tuple[str, ...] = ()) -> str:
    """A compact rich-text summary of *values*: colour swatches, widths, fonts (PRD 11.9).

    Keys named in *order* come first, then the rest in their own order.
    """
    keys = [k for k in order if k in values and k != "tool"]
    keys += [k for k in values if k not in keys]
    parts = [f for f in (_fragment(k, values[k]) for k in keys) if f]
    return " &middot; ".join(parts)


class ManagePresetsDialog(QDialog):
    """Rename, duplicate, and delete the presets of one tool (PRD 11.9)."""

    def __init__(
        self,
        themes: ToolThemeManager,
        tool_id: str,
        tool_name: str,
        order: tuple[str, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._themes = themes
        self._tool_id = tool_id
        self._order = order
        self._updating = False
        self.setWindowTitle(f"Manage {tool_name} Presets")
        self.setObjectName("ManagePresetsDialog")
        self.setMinimumSize(560, 320)

        outer = QVBoxLayout(self)
        self._list = QTreeWidget()
        self._list.setAccessibleName(f"{tool_name} presets")
        self._list.setObjectName("PresetList")
        self._list.setColumnCount(2)
        self._list.setHeaderLabels(["Preset", "Summary"])
        self._list.setRootIsDecorated(False)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._list.itemChanged.connect(self._on_item_changed)
        outer.addWidget(self._list, 1)

        actions = QHBoxLayout()
        self._rename_button = QPushButton("Rename")
        self._rename_button.setAccessibleName("Rename preset")
        self._rename_button.clicked.connect(self._rename)
        actions.addWidget(self._rename_button)
        self._duplicate_button = QPushButton("Duplicate")
        self._duplicate_button.setAccessibleName("Duplicate preset")
        self._duplicate_button.clicked.connect(self._duplicate)
        actions.addWidget(self._duplicate_button)
        self._delete_button = QPushButton("Delete")
        self._delete_button.setAccessibleName("Delete preset")
        self._delete_button.clicked.connect(self._delete)
        actions.addWidget(self._delete_button)
        actions.addStretch(1)
        outer.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        themes.presets_changed.connect(self._on_presets_changed)
        self._reload()

    # ---- the list ----

    def preset_names(self) -> list[str]:
        """The names shown, top to bottom."""
        names = []
        for row in range(self._list.topLevelItemCount()):
            item = self._list.topLevelItem(row)
            if item is not None:
                names.append(item.text(0))
        return names

    def summary_text(self, row: int) -> str:
        """The rich-text summary shown beside the preset in *row*."""
        item = self._list.topLevelItem(row)
        widget = self._list.itemWidget(item, 1) if item is not None else None
        return widget.text() if isinstance(widget, QLabel) else ""

    def select(self, name: str) -> None:
        for row in range(self._list.topLevelItemCount()):
            item = self._list.topLevelItem(row)
            if item is not None and item.text(0) == name:
                self._list.setCurrentItem(item)
                return

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        return item.text(0) if item is not None else None

    def _reload(self) -> None:
        selected = self._selected_name()
        self._updating = True
        try:
            self._list.clear()
            for preset in self._themes.presets(self._tool_id):
                item = QTreeWidgetItem([preset.name, ""])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self._list.addTopLevelItem(item)
                summary = QLabel(summarise_values(preset.values, self._order))
                summary.setTextFormat(Qt.TextFormat.RichText)
                summary.setAccessibleName(f"{preset.name} summary")
                self._list.setItemWidget(item, 1, summary)
        finally:
            self._updating = False
        self._list.resizeColumnToContents(0)
        if selected is not None:
            self.select(selected)
        if self._list.currentItem() is None and self._list.topLevelItemCount():
            self._list.setCurrentItem(self._list.topLevelItem(0))

    def _on_presets_changed(self, tool_id: str) -> None:
        if tool_id == self._tool_id and not self._updating:
            self._reload()

    # ---- the actions ----

    def _require_selection(self, action: str) -> str | None:
        name = self._selected_name()
        if check_requirements(self, action, [(name is not None, "a preset selected")]):
            return name
        return None

    def _rename(self) -> None:
        """Rename: edit the selected name in place (PRD 11.9)."""
        if self._require_selection("Rename") is None:
            return
        item = self._list.currentItem()
        if item is not None:
            self._list.editItem(item, 0)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """An inline edit finished: apply the rename, or revert an empty or taken name."""
        if self._updating or column != 0:
            return
        row = self._list.indexOfTopLevelItem(item)
        names = self._themes.preset_names(self._tool_id)
        old = names[row] if 0 <= row < len(names) else None
        new = item.text(0).strip()
        if old is None or new == old:
            self._reload()
            return
        taken = new in names
        if not check_requirements(
            self,
            "Rename",
            [(bool(new), "a name"), (not taken, f'a name not already used ("{new}" is)')],
        ):
            self._reload()
            return
        self._updating = True
        try:
            self._themes.rename_preset(self._tool_id, old, new)
        finally:
            self._updating = False
        self._reload()
        self.select(new)

    def _duplicate(self) -> None:
        name = self._require_selection("Duplicate")
        if name is None:
            return
        copy = self._themes.duplicate_preset(self._tool_id, name)
        if copy is not None:
            self.select(copy.name)

    def _confirm_delete(self, name: str) -> bool:
        answer = QMessageBox.question(
            self, "Delete Preset", f'Delete the preset "{name}"? This cannot be undone.'
        )
        return answer == QMessageBox.StandardButton.Yes

    def _delete(self) -> None:
        name = self._require_selection("Delete")
        if name is None:
            return
        if self._confirm_delete(name):
            self._themes.delete_preset(self._tool_id, name)
