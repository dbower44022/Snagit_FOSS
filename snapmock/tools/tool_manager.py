"""ToolManager — registry and active-tool switching."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QMouseEvent

from snapmock.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager


class ToolManager(QObject):
    """Manages the tool registry and delegates events to the active tool.

    Signals
    -------
    tool_changed(str)
        Emitted with the tool_id of the newly activated tool.
    """

    tool_changed = pyqtSignal(str)

    def __init__(
        self,
        scene: SnapScene,
        selection_manager: SelectionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._scene = scene
        self._selection_manager = selection_manager
        self._tools: dict[str, BaseTool] = {}
        self._active_tool: BaseTool | None = None

    # --- registration ---

    def register(self, tool: BaseTool) -> None:
        """Register a tool by its tool_id."""
        self._tools[tool.tool_id] = tool

    def tool(self, tool_id: str) -> BaseTool | None:
        return self._tools.get(tool_id)

    @property
    def tool_ids(self) -> list[str]:
        return list(self._tools.keys())

    # --- activation ---

    @property
    def active_tool(self) -> BaseTool | None:
        return self._active_tool

    @property
    def active_tool_id(self) -> str:
        if self._active_tool is not None:
            return self._active_tool.tool_id
        return ""

    def activate(self, tool_id: str) -> None:
        """Switch to the tool identified by *tool_id*."""
        tool = self._tools.get(tool_id)
        if tool is None:
            return
        if self._active_tool is not None:
            self._active_tool.deactivate()
        self._active_tool = tool
        tool.activate(self._scene, self._selection_manager)
        self.tool_changed.emit(tool_id)

    # --- event delegation ---

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        if self._active_tool is not None:
            return self._active_tool.mouse_press(event)
        return False

    def handle_mouse_move(self, event: QMouseEvent) -> bool:
        if self._active_tool is not None:
            return self._active_tool.mouse_move(event)
        return False

    def handle_mouse_release(self, event: QMouseEvent) -> bool:
        if self._active_tool is not None:
            return self._active_tool.mouse_release(event)
        return False

    def handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        if self._active_tool is not None:
            return self._active_tool.mouse_double_click(event)
        return False
