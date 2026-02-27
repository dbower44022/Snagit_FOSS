"""MainWindow — primary application window."""

from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow

from snapmock.config.constants import APP_NAME
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.tools.arrow_tool import ArrowTool
from snapmock.tools.ellipse_tool import EllipseTool
from snapmock.tools.rectangle_tool import RectangleTool
from snapmock.tools.select_tool import SelectTool
from snapmock.tools.tool_manager import ToolManager


class MainWindow(QMainWindow):
    """Primary application window.

    Owns the SnapScene, SnapView, SelectionManager, and ToolManager.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(800, 600)

        self._scene = SnapScene(parent=self)
        self._view = SnapView(self._scene)
        self._selection_manager = SelectionManager(self._scene, parent=self)
        self._tool_manager = ToolManager(self._scene, self._selection_manager, parent=self)

        self.setCentralWidget(self._view)

        self._register_tools()
        self._tool_manager.activate("select")

    def _register_tools(self) -> None:
        """Register all built-in tools with the ToolManager."""
        self._tool_manager.register(SelectTool())
        self._tool_manager.register(RectangleTool())
        self._tool_manager.register(EllipseTool())
        self._tool_manager.register(ArrowTool())

    @property
    def scene(self) -> SnapScene:
        return self._scene

    @property
    def view(self) -> SnapView:
        return self._view

    @property
    def selection_manager(self) -> SelectionManager:
        return self._selection_manager

    @property
    def tool_manager(self) -> ToolManager:
        return self._tool_manager
