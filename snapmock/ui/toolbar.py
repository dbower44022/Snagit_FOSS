"""SnapToolBar — main toolbar synced with ToolManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QComboBox, QToolBar, QToolButton

from snapmock.config.constants import ZOOM_STEPS

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
        self.setMovable(False)

        for tid in tool_manager.tool_ids:
            tool = tool_manager.tool(tid)
            if tool is None:
                continue
            btn = QToolButton(self)
            btn.setText(tool.display_name)
            btn.setCheckable(True)
            btn.clicked.connect(self._make_activator(tid))
            self.addWidget(btn)
            self._buttons[tid] = btn

        tool_manager.tool_changed.connect(self._on_tool_changed)
        self._on_tool_changed(tool_manager.active_tool_id)

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
