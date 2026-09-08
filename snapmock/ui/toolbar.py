"""SnapToolBar — main toolbar synced with ToolManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QToolBar, QToolButton

from snapmock.config.constants import ZOOM_STEPS
from snapmock.core.theme_manager import theme_manager
from snapmock.ui.icons import CAPTURE_ICON, TOOL_ICONS, tool_tooltip

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from snapmock.core.view import SnapView
    from snapmock.tools.tool_manager import ToolManager


class SnapToolBar(QToolBar):
    """Main toolbar that reflects the ToolManager's registered tools."""

    def __init__(self, tool_manager: ToolManager, parent: QWidget | None = None) -> None:
        super().__init__("Tools", parent)
        self._tool_manager = tool_manager
        self._buttons: dict[str, QToolButton] = {}
        self._capture_button: QToolButton | None = None
        self.setMovable(False)
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
        for tid, btn in self._buttons.items():
            name = TOOL_ICONS.get(tid)
            icon = manager.icon(name) if name is not None else None
            if icon is not None and not icon.isNull():
                btn.setIcon(icon)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            else:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        if self._capture_button is not None:
            self._capture_button.setIcon(manager.icon(CAPTURE_ICON))
            self._capture_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def set_capture_button(self, button: QToolButton) -> None:
        """Install the Group 0 Capture control at the left end (Screen Capture PRD 3.3)."""
        actions = self.actions()
        first = actions[0] if actions else None
        button.setParent(self)
        self.insertWidget(first, button)
        self.insertSeparator(first)
        self._capture_button = button
        self.apply_theme()

    def _make_activator(self, tool_id: str):  # type: ignore[no-untyped-def]
        def _activate() -> None:
            self._tool_manager.activate(tool_id)

        return _activate

    def _on_tool_changed(self, tool_id: str) -> None:
        for tid, btn in self._buttons.items():
            btn.setChecked(tid == tool_id)


class ZoomDropdown(QComboBox):
    """Zoom level dropdown that syncs with a SnapView."""

    def __init__(self, view: SnapView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = view
        self._updating = False

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaximumWidth(100)

        for step in ZOOM_STEPS:
            self.addItem(f"{step}%", step)

        # Set initial value
        self._sync_from_view(view.zoom_percent)

        # Connect signals
        view.zoom_changed.connect(self._sync_from_view)
        self.currentIndexChanged.connect(self._on_index_changed)
        self.lineEdit().returnPressed.connect(self._on_custom_entry)  # type: ignore[union-attr]

    def _sync_from_view(self, percent: int) -> None:
        self._updating = True
        text = f"{percent}%"
        idx = self.findText(text)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
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
            self._view.set_zoom(value)
        except ValueError:
            pass
