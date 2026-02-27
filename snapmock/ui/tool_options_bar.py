"""ToolOptionsBar — context-sensitive per-tool options widget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QToolBar

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from snapmock.tools.tool_manager import ToolManager


class ToolOptionsBar(QToolBar):
    """Displays context-sensitive options for the active tool."""

    def __init__(self, tool_manager: ToolManager, parent: QWidget | None = None) -> None:
        super().__init__("Tool Options", parent)
        self._tool_manager = tool_manager
        self._label = QLabel("No tool selected")
        self.addWidget(self._label)
        self.setMovable(False)

        tool_manager.tool_changed.connect(self._on_tool_changed)
        self._on_tool_changed(tool_manager.active_tool_id)

    def _on_tool_changed(self, tool_id: str) -> None:
        # Remove all existing widgets
        self.clear()

        tool = self._tool_manager.tool(tool_id)
        if tool is not None:
            self._label = QLabel(f"{tool.display_name} options")
            self.addWidget(self._label)
            tool.build_options_widgets(self)
        else:
            self._label = QLabel("No tool selected")
            self.addWidget(self._label)
