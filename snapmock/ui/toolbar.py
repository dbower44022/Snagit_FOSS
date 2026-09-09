"""Toolbars: the Main Toolbar (General UI PRD 4), the tool palette (PRD 2), the zoom dropdown."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QComboBox, QToolBar, QToolButton

from snapmock.config.constants import ZOOM_MAX, ZOOM_MIN
from snapmock.core.theme_manager import theme_manager
from snapmock.ui.icons import (
    CAPTURE_ICON,
    TOOL_ICONS,
    apply_action_icons,
    plain_label,
    tool_tooltip,
)
from snapmock.ui.unmet_requirements import show_unmet_requirements

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from snapmock.core.selection_manager import SelectionManager
    from snapmock.core.view import SnapView
    from snapmock.tools.tool_manager import ToolManager

# The Main Toolbar's zoom presets (PRD 4.3). Zoom In and Zoom Out step through
# ZOOM_STEPS instead; the two lists serve different gestures (decision 09-08-26).
ZOOM_PRESETS: tuple[int, ...] = (10, 25, 50, 75, 100, 150, 200, 400, 800, 1600, 3200)

MAIN_TOOLBAR_HEIGHT = 40
MAIN_TOOLBAR_ICON_SIZE = 24
MAIN_TOOLBAR_BUTTON_SIZE = 32
PALETTE_WIDTH = 48
PALETTE_BUTTON_PADDING = 8


def action_tooltip(action: QAction) -> str:
    """``"Name (Shortcut)"`` for a toolbar button (PRD 4.3), or the name alone."""
    label = plain_label(action.text()).removesuffix("...")
    shortcut = action.shortcut()
    if shortcut.isEmpty():
        return label
    return f"{label} ({shortcut.toString(QKeySequence.SequenceFormat.NativeText)})"


class MainToolBar(QToolBar):
    """The horizontal toolbar below the menu bar: PRD 4.2's groups over the menu actions.

    Every button is a menu action's toolbar copy, so it carries the action's icon,
    tooltip shortcut, and never-disabled requirement check. Group 0 (Capture) is
    installed by :meth:`set_capture_button`; Group 5 (alignment) is shown while two
    or more items are selected (PRD 4.2); Group 6 holds the zoom dropdown.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self.setIconSize(QSize(MAIN_TOOLBAR_ICON_SIZE, MAIN_TOOLBAR_ICON_SIZE))
        self.setFixedHeight(MAIN_TOOLBAR_HEIGHT)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._groups = 0
        self._align_actions: list[QAction] = []
        self._align_separator: QAction | None = None
        self._zoom: ZoomDropdown | None = None
        self._capture_button: QToolButton | None = None
        self._selection: SelectionManager | None = None
        # Bound-method slots: Qt drops them when this toolbar is destroyed.
        theme_manager().theme_changed.connect(self._on_theme_changed)

    # ---- building ----

    def _begin_group(self) -> QAction | None:
        separator = self.addSeparator() if self._groups else None
        self._groups += 1
        return separator

    def _add_action(self, action: QAction) -> None:
        action.setToolTip(action_tooltip(action))
        self.addAction(action)
        button = self.widgetForAction(action)
        if isinstance(button, QToolButton):
            button.setFixedSize(MAIN_TOOLBAR_BUTTON_SIZE, MAIN_TOOLBAR_BUTTON_SIZE)

    def add_group(self, actions: Sequence[QAction]) -> None:
        """Append a group of buttons, preceded by a divider unless it is the first."""
        self._begin_group()
        for action in actions:
            self._add_action(action)

    def add_alignment_group(self, actions: Sequence[QAction]) -> None:
        """Group 5: the six Align actions, visible while two or more items are selected.

        The buttons are toolbar copies that trigger the menu actions: hiding a
        QAction also disables it, which would take the Arrange menu rows with it.
        """
        self._align_separator = self._begin_group()
        for action in actions:
            copy = QAction(action.text(), self)
            copy.setShortcut(action.shortcut())
            copy.triggered.connect(action.trigger)
            copy.setShortcut(QKeySequence())  # the toolbar copy never owns the shortcut
            self._add_action(copy)
            self._align_actions.append(copy)
        apply_action_icons(self._align_actions)
        self._update_alignment_visibility()

    def add_zoom_group(
        self, zoom_out: QAction, zoom_in: QAction, fit: QAction, view: SnapView
    ) -> ZoomDropdown:
        """Group 6: Zoom Out, the zoom dropdown, Zoom In, Fit to Window."""
        self._begin_group()
        self._add_action(zoom_out)
        self._zoom = ZoomDropdown(view, self)
        self.addWidget(self._zoom)
        self._add_action(zoom_in)
        self._add_action(fit)
        return self._zoom

    def set_capture_button(self, button: QToolButton) -> None:
        """Install the Group 0 Capture control at the left end (Screen Capture PRD 3.3)."""
        actions = self.actions()
        first = actions[0] if actions else None
        button.setParent(self)
        button.setFixedHeight(MAIN_TOOLBAR_BUTTON_SIZE)
        self.insertWidget(first, button)
        self.insertSeparator(first)
        self._capture_button = button
        self._apply_capture_icon()

    # ---- binding ----

    @property
    def zoom_dropdown(self) -> ZoomDropdown | None:
        return self._zoom

    @property
    def alignment_actions(self) -> list[QAction]:
        return list(self._align_actions)

    def set_view(self, view: SnapView) -> None:
        """Follow another document's view (tab switch)."""
        if self._zoom is not None:
            self._zoom.set_view(view)

    def set_selection_manager(self, selection: SelectionManager) -> None:
        """Follow another document's selection for Group 5's visibility."""
        if self._selection is selection:
            return
        if self._selection is not None:
            try:
                self._selection.selection_changed.disconnect(self._on_selection_changed)
            except (TypeError, RuntimeError):
                pass
        self._selection = selection
        selection.selection_changed.connect(self._on_selection_changed)
        self._update_alignment_visibility()

    def _on_selection_changed(self, _items: list[object]) -> None:
        self._update_alignment_visibility()

    def _update_alignment_visibility(self) -> None:
        visible = self._selection is not None and self._selection.count >= 2
        for action in self._align_actions:
            action.setVisible(visible)
        if self._align_separator is not None:
            self._align_separator.setVisible(visible)

    def _on_theme_changed(self, _name: str) -> None:
        apply_action_icons(self._align_actions)
        self._apply_capture_icon()

    def _apply_capture_icon(self) -> None:
        if self._capture_button is not None:
            self._capture_button.setIcon(theme_manager().icon(CAPTURE_ICON))
            self._capture_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)


class SnapToolBar(QToolBar):
    """The Left Tool Palette (PRD 2.1, 2.2): one column of tool buttons, synced with the tools.

    The window docks it in the left toolbar area, which makes it vertical. It is 48 px
    wide at the default icon size: 32 px buttons with 8 px of padding around them.
    """

    def __init__(self, tool_manager: ToolManager, parent: QWidget | None = None) -> None:
        super().__init__("Tool Palette", parent)
        self._tool_manager = tool_manager
        self._buttons: dict[str, QToolButton] = {}
        self.setMovable(False)
        self.setFloatable(False)
        self.setAllowedAreas(Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea)
        self.setIconSize(theme_manager().icon_qsize())

        for tid in tool_manager.tool_ids:
            tool = tool_manager.tool(tid)
            if tool is None:
                continue
            btn = QToolButton(self)
            btn.setText(tool.display_name)
            btn.setToolTip(tool_tooltip(tid, tool.display_name))
            btn.setCheckable(True)
            btn.clicked.connect(self._make_activator(tid))
            self.addWidget(btn)
            self._buttons[tid] = btn

        tool_manager.tool_changed.connect(self._on_tool_changed)
        self._on_tool_changed(tool_manager.active_tool_id)
        self.apply_theme()
        # Bound-method slots: Qt drops them when this toolbar is destroyed.
        theme_manager().theme_changed.connect(self._on_theme_changed)
        theme_manager().icon_size_changed.connect(self._on_icon_size_changed)

    def _on_theme_changed(self, _name: str) -> None:
        self.apply_theme()

    def _on_icon_size_changed(self, _size: int) -> None:
        self.apply_theme()

    def apply_theme(self) -> None:
        """Themed icons at the preferred size on every button (General UI PRD 13.4)."""
        manager = theme_manager()
        self.setIconSize(manager.icon_qsize())
        button_size = manager.icon_size + PALETTE_BUTTON_PADDING
        self.setFixedWidth(max(PALETTE_WIDTH, button_size + 2 * PALETTE_BUTTON_PADDING))
        for tid, btn in self._buttons.items():
            btn.setFixedSize(button_size, button_size)
            name = TOOL_ICONS.get(tid)
            icon = manager.icon(name) if name is not None else None
            if icon is not None and not icon.isNull():
                btn.setIcon(icon)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            else:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

    def _make_activator(self, tool_id: str):  # type: ignore[no-untyped-def]
        def _activate() -> None:
            self._tool_manager.activate(tool_id)

        return _activate

    def _on_tool_changed(self, tool_id: str) -> None:
        for tid, btn in self._buttons.items():
            btn.setChecked(tid == tool_id)


class ZoomDropdown(QComboBox):
    """The editable zoom combo box of PRD 4.3, synced with a SnapView."""

    def __init__(self, view: SnapView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = view
        self._updating = False

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaximumWidth(100)
        self.setToolTip("Zoom")

        for step in ZOOM_PRESETS:
            self.addItem(f"{step}%", step)

        self._sync_from_view(view.zoom_percent)
        view.zoom_changed.connect(self._sync_from_view)
        self.currentIndexChanged.connect(self._on_index_changed)
        self.lineEdit().returnPressed.connect(self._on_custom_entry)  # type: ignore[union-attr]

    @property
    def snap_view(self) -> SnapView:
        return self._view

    def set_view(self, view: SnapView) -> None:
        """Track a different SnapView (tab switch)."""
        if view is self._view:
            return
        try:
            self._view.zoom_changed.disconnect(self._sync_from_view)
        except (TypeError, RuntimeError):
            pass
        self._view = view
        view.zoom_changed.connect(self._sync_from_view)
        self._sync_from_view(view.zoom_percent)

    def _sync_from_view(self, percent: int) -> None:
        self._updating = True
        text = f"{percent}%"
        idx = self.findText(text)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
            self.setCurrentIndex(-1)
            self.setEditText(text)
        self._updating = False

    def _on_index_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        data = self.itemData(index)
        if data is not None:
            self._view.set_zoom(int(data))

    def _on_custom_entry(self) -> None:
        text = self.currentText().replace("%", "").strip()
        try:
            value = int(text)
        except ValueError:
            value = -1
        if ZOOM_MIN <= value <= ZOOM_MAX:
            self._view.set_zoom(value)
            self._sync_from_view(self._view.zoom_percent)
            return
        show_unmet_requirements(
            self, "Zoom", [f"a whole number between {ZOOM_MIN}% and {ZOOM_MAX}%"]
        )
        self._sync_from_view(self._view.zoom_percent)
