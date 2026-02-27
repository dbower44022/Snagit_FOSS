"""MainWindow — primary application window."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow

from snapmock.config.constants import APP_NAME
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.tools.arrow_tool import ArrowTool
from snapmock.tools.ellipse_tool import EllipseTool
from snapmock.tools.freehand_tool import FreehandTool
from snapmock.tools.line_tool import LineTool
from snapmock.tools.rectangle_tool import RectangleTool
from snapmock.tools.select_tool import SelectTool
from snapmock.tools.text_tool import TextTool
from snapmock.tools.tool_manager import ToolManager
from snapmock.ui.layer_panel import LayerPanel
from snapmock.ui.property_panel import PropertyPanel
from snapmock.ui.status_bar import SnapStatusBar
from snapmock.ui.tool_options_bar import ToolOptionsBar
from snapmock.ui.toolbar import SnapToolBar


class MainWindow(QMainWindow):
    """Primary application window.

    Owns the SnapScene, SnapView, SelectionManager, ToolManager, and UI panels.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        # Core subsystems
        self._scene = SnapScene(parent=self)
        self._view = SnapView(self._scene)
        self._selection_manager = SelectionManager(self._scene, parent=self)
        self._tool_manager = ToolManager(self._scene, self._selection_manager, parent=self)

        self.setCentralWidget(self._view)

        # Register tools
        self._register_tools()
        self._tool_manager.activate("select")

        # UI panels
        self._toolbar = SnapToolBar(self._tool_manager, self)
        self.addToolBar(self._toolbar)

        self._tool_options = ToolOptionsBar(self._tool_manager, self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._tool_options)

        self._layer_panel = LayerPanel(self._scene.layer_manager, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._layer_panel)

        self._property_panel = PropertyPanel(self._selection_manager, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._property_panel)

        self._status_bar = SnapStatusBar(self._view)
        self.setStatusBar(self._status_bar)

        # Menu bar
        self._setup_menus()

    def _register_tools(self) -> None:
        """Register all built-in tools with the ToolManager."""
        self._tool_manager.register(SelectTool())
        self._tool_manager.register(RectangleTool())
        self._tool_manager.register(EllipseTool())
        self._tool_manager.register(ArrowTool())
        self._tool_manager.register(LineTool())
        self._tool_manager.register(TextTool())
        self._tool_manager.register(FreehandTool())

    def _setup_menus(self) -> None:
        """Create menu bar actions."""
        menu_bar = self.menuBar()
        if menu_bar is None:
            return

        # File menu
        file_menu = menu_bar.addMenu("&File")
        if file_menu is not None:
            file_menu.addAction("&New")
            file_menu.addAction("&Open...")
            file_menu.addSeparator()
            file_menu.addAction("&Save")
            file_menu.addAction("Save &As...")
            file_menu.addSeparator()
            file_menu.addAction("&Export...")
            file_menu.addSeparator()
            quit_action = file_menu.addAction("&Quit")
            if quit_action is not None:
                quit_action.triggered.connect(self.close)

        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")
        if edit_menu is not None:
            undo_action = edit_menu.addAction("&Undo")
            if undo_action is not None:
                undo_action.setShortcut("Ctrl+Z")
                undo_action.triggered.connect(self._scene.command_stack.undo)
            redo_action = edit_menu.addAction("&Redo")
            if redo_action is not None:
                redo_action.setShortcut("Ctrl+Shift+Z")
                redo_action.triggered.connect(self._scene.command_stack.redo)

        # View menu
        view_menu = menu_bar.addMenu("&View")
        if view_menu is not None:
            zoom_in = view_menu.addAction("Zoom &In")
            if zoom_in is not None:
                zoom_in.setShortcut("Ctrl+=")
                zoom_in.triggered.connect(self._view.zoom_in)
            zoom_out = view_menu.addAction("Zoom &Out")
            if zoom_out is not None:
                zoom_out.setShortcut("Ctrl+-")
                zoom_out.triggered.connect(self._view.zoom_out)
            fit_action = view_menu.addAction("&Fit to Window")
            if fit_action is not None:
                fit_action.setShortcut("Ctrl+0")
                fit_action.triggered.connect(self._view.fit_in_view_all)

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
