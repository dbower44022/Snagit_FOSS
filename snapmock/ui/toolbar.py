"""SnapToolBar — main toolbar synced with ToolManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QToolBar, QToolButton

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

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
