"""MainWindow — primary application window."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMenu, QMenuBar, QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsItem

from snapmock.config.constants import (
    APP_NAME,
    APP_VERSION,
    PROJECT_EXTENSION,
    SNAGIT_EXTENSION,
)
from snapmock.config.settings import AppSettings
from snapmock.config.shortcuts import SHORTCUTS
from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.io.exporter import export_jpg, export_pdf, export_png, export_svg
from snapmock.io.importer import import_image
from snapmock.io.project_serializer import load_project, save_project
from snapmock.io.snagit_reader import load_snagx
from snapmock.io.snagit_writer import save_snagx
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.tools.arrow_tool import ArrowTool
from snapmock.tools.blur_tool import BlurTool
from snapmock.tools.callout_tool import CalloutTool
from snapmock.tools.crop_tool import CropTool
from snapmock.tools.ellipse_tool import EllipseTool
from snapmock.tools.eyedropper_tool import EyedropperTool
from snapmock.tools.freehand_tool import FreehandTool
from snapmock.tools.highlight_tool import HighlightTool
from snapmock.tools.lasso_select_tool import LassoSelectTool
from snapmock.tools.line_tool import LineTool
from snapmock.tools.numbered_step_tool import NumberedStepTool
from snapmock.tools.pan_tool import PanTool
from snapmock.tools.raster_select_tool import RasterSelectTool
from snapmock.tools.rectangle_tool import RectangleTool
from snapmock.tools.select_tool import SelectTool
from snapmock.tools.stamp_tool import StampTool
from snapmock.tools.text_tool import TextTool
from snapmock.tools.tool_manager import ToolManager
from snapmock.tools.zoom_tool import ZoomTool
from snapmock.ui.layer_panel import LayerPanel
from snapmock.ui.property_panel import PropertyPanel
from snapmock.ui.status_bar import SnapStatusBar
from snapmock.ui.tool_options_bar import ToolOptionsBar
from snapmock.ui.toolbar import SnapToolBar

MAX_RECENT_FILES = 10


class MainWindow(QMainWindow):
    """Primary application window.

    Owns the SnapScene, SnapView, SelectionManager, ToolManager,
    ClipboardManager, and UI panels.
    """

    def __init__(self) -> None:
        super().__init__()
        self._settings = AppSettings()
        self._current_file: Path | None = None
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        # Core subsystems
        self._scene = SnapScene(parent=self)
        self._view = SnapView(self._scene)
        self._selection_manager = SelectionManager(self._scene, parent=self)
        self._tool_manager = ToolManager(self._scene, self._selection_manager, parent=self)
        self._clipboard = ClipboardManager(self._scene, parent=self)

        # Wire tool manager to view for mouse event delegation
        self._view.set_tool_manager(self._tool_manager)

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

        self._property_panel = PropertyPanel(self._selection_manager, self._scene, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._property_panel)

        self._status_bar = SnapStatusBar(self._view)
        self.setStatusBar(self._status_bar)

        # Wire cursor position tracking
        self._view.cursor_moved.connect(self._status_bar.update_cursor_pos)

        # Wire tool hint to status bar
        self._tool_manager.tool_changed.connect(self._on_tool_changed_for_hint)

        # Menu bar
        self._recent_menu: QMenu | None = None
        # Arrange action references (populated in _setup_arrange_menu)
        self._bring_front_action: QAction | None = None
        self._bring_forward_action: QAction | None = None
        self._send_backward_action: QAction | None = None
        self._send_to_back_action: QAction | None = None
        self._align_menu: QMenu | None = None
        self._distribute_menu: QMenu | None = None
        self._align_canvas_action: QAction | None = None
        # Layer action references (populated in _setup_layer_menu)
        self._layer_move_up_action: QAction | None = None
        self._layer_move_down_action: QAction | None = None
        self._layer_move_top_action: QAction | None = None
        self._layer_move_bottom_action: QAction | None = None
        self._layer_delete_action: QAction | None = None
        self._layer_merge_down_action: QAction | None = None
        # Tools menu action map
        self._tool_actions: dict[str, QAction] = {}
        self._setup_menus()

        # Autosave timer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        if self._settings.autosave_enabled():
            self._autosave_timer.start(self._settings.autosave_interval_minutes() * 60_000)

        # Track dirty state for window title
        self._scene.command_stack.stack_changed.connect(self._update_title)

        # Layer state → deselect/cancel on lock/hide/switch
        self._connect_layer_signals()
        self._connect_menu_state_signals()
        self._update_menu_states()

        # Restore window geometry
        geo = self._settings.window_geometry()
        if geo is not None:
            self.restoreGeometry(geo)
        state = self._settings.window_state()
        if state is not None:
            self.restoreState(state)

        self._update_title()

    def _register_tools(self) -> None:
        """Register all built-in tools with the ToolManager."""
        self._tool_manager.register(SelectTool())
        self._tool_manager.register(RectangleTool())
        self._tool_manager.register(EllipseTool())
        self._tool_manager.register(ArrowTool())
        self._tool_manager.register(LineTool())
        self._tool_manager.register(TextTool())
        self._tool_manager.register(FreehandTool())
        self._tool_manager.register(BlurTool())
        self._tool_manager.register(HighlightTool())
        self._tool_manager.register(CalloutTool())
        self._tool_manager.register(NumberedStepTool())
        self._tool_manager.register(StampTool())
        self._tool_manager.register(CropTool())
        self._tool_manager.register(RasterSelectTool())
        self._tool_manager.register(EyedropperTool())
        self._tool_manager.register(PanTool())
        self._tool_manager.register(ZoomTool())
        self._tool_manager.register(LassoSelectTool())

    # ---- menus ----

    def _setup_menus(self) -> None:
        """Create menu bar actions."""
        menu_bar = self.menuBar()
        if menu_bar is None:
            return

        self._setup_file_menu(menu_bar)
        self._setup_edit_menu(menu_bar)
        self._setup_view_menu(menu_bar)
        self._setup_image_menu(menu_bar)
        self._setup_layer_menu(menu_bar)
        self._setup_arrange_menu(menu_bar)
        self._setup_tools_menu(menu_bar)
        self._setup_help_menu(menu_bar)

    def _setup_file_menu(self, menu_bar: QMenuBar) -> None:  # noqa: C901
        file_menu = menu_bar.addMenu("&File")
        if file_menu is None:
            return

        new_action = file_menu.addAction("&New")
        if new_action is not None:
            new_action.setShortcut(QKeySequence(SHORTCUTS["file.new"]))
            new_action.triggered.connect(self._file_new)

        open_action = file_menu.addAction("&Open...")
        if open_action is not None:
            open_action.setShortcut(QKeySequence(SHORTCUTS["file.open"]))
            open_action.triggered.connect(self._file_open)

        file_menu.addSeparator()

        save_action = file_menu.addAction("&Save")
        if save_action is not None:
            save_action.setShortcut(QKeySequence(SHORTCUTS["file.save"]))
            save_action.triggered.connect(self._file_save)

        save_as_action = file_menu.addAction("Save &As...")
        if save_as_action is not None:
            save_as_action.setShortcut(QKeySequence(SHORTCUTS["file.save_as"]))
            save_as_action.triggered.connect(self._file_save_as)

        file_menu.addSeparator()

        import_action = file_menu.addAction("&Import Image...")
        if import_action is not None:
            import_action.setShortcut(QKeySequence(SHORTCUTS["file.import_image"]))
            import_action.triggered.connect(self._file_import_image)

        export_action = file_menu.addAction("&Export...")
        if export_action is not None:
            export_action.setShortcut(QKeySequence(SHORTCUTS["file.export"]))
            export_action.triggered.connect(self._file_export)

        export_png_action = file_menu.addAction("Export Quick &PNG")
        if export_png_action is not None:
            export_png_action.setShortcut(QKeySequence(SHORTCUTS["file.export_quick_png"]))
            export_png_action.triggered.connect(self._file_export_quick_png)

        file_menu.addSeparator()

        print_action = file_menu.addAction("&Print...")
        if print_action is not None:
            print_action.setShortcut(QKeySequence(SHORTCUTS["file.print"]))
            print_action.triggered.connect(self._file_print)

        file_menu.addSeparator()

        self._recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_files_menu()

        file_menu.addSeparator()

        prefs_action = file_menu.addAction("Pre&ferences...")
        if prefs_action is not None:
            prefs_action.setShortcut(QKeySequence(SHORTCUTS["file.preferences"]))
            prefs_action.triggered.connect(self._file_preferences)

        file_menu.addSeparator()

        quit_action = file_menu.addAction("&Quit")
        if quit_action is not None:
            quit_action.setShortcut(QKeySequence("Ctrl+Q"))
            quit_action.triggered.connect(self.close)

    def _setup_edit_menu(self, menu_bar: QMenuBar) -> None:
        edit_menu = menu_bar.addMenu("&Edit")
        if edit_menu is None:
            return

        undo_action = edit_menu.addAction("&Undo")
        if undo_action is not None:
            undo_action.setShortcut(QKeySequence(SHORTCUTS["edit.undo"]))
            undo_action.triggered.connect(self._edit_undo)

        redo_action = edit_menu.addAction("&Redo")
        if redo_action is not None:
            redo_action.setShortcut(QKeySequence(SHORTCUTS["edit.redo"]))
            redo_action.triggered.connect(self._scene.command_stack.redo)

        edit_menu.addSeparator()

        cut_action = edit_menu.addAction("Cu&t")
        if cut_action is not None:
            cut_action.setShortcut(QKeySequence(SHORTCUTS["edit.cut"]))
            cut_action.triggered.connect(self._edit_cut)

        copy_action = edit_menu.addAction("&Copy")
        if copy_action is not None:
            copy_action.setShortcut(QKeySequence(SHORTCUTS["edit.copy"]))
            copy_action.triggered.connect(self._edit_copy)

        paste_action = edit_menu.addAction("&Paste")
        if paste_action is not None:
            paste_action.setShortcut(QKeySequence(SHORTCUTS["edit.paste"]))
            paste_action.triggered.connect(self._edit_paste)

        paste_in_place_action = edit_menu.addAction("Paste in &Place")
        if paste_in_place_action is not None:
            paste_in_place_action.setShortcut(QKeySequence(SHORTCUTS["edit.paste_in_place"]))
            paste_in_place_action.triggered.connect(self._edit_paste_in_place)

        delete_action = edit_menu.addAction("&Delete")
        if delete_action is not None:
            delete_action.setShortcut(QKeySequence(SHORTCUTS["edit.delete"]))
            delete_action.triggered.connect(self._edit_delete)

        edit_menu.addSeparator()

        duplicate_action = edit_menu.addAction("D&uplicate")
        if duplicate_action is not None:
            duplicate_action.setShortcut(QKeySequence(SHORTCUTS["edit.duplicate"]))
            duplicate_action.triggered.connect(self._edit_duplicate)

        edit_menu.addSeparator()

        select_all_action = edit_menu.addAction("Select &All")
        if select_all_action is not None:
            select_all_action.setShortcut(QKeySequence(SHORTCUTS["edit.select_all"]))
            select_all_action.triggered.connect(self._edit_select_all)

        select_all_layers_action = edit_menu.addAction("Select All La&yers")
        if select_all_layers_action is not None:
            select_all_layers_action.setShortcut(QKeySequence(SHORTCUTS["edit.select_all_layers"]))
            select_all_layers_action.triggered.connect(self._edit_select_all_layers)

        deselect_action = edit_menu.addAction("D&eselect")
        if deselect_action is not None:
            deselect_action.setShortcut(QKeySequence(SHORTCUTS["edit.deselect"]))
            deselect_action.triggered.connect(self._selection_manager.deselect_all)

    def _setup_view_menu(self, menu_bar: QMenuBar) -> None:
        view_menu = menu_bar.addMenu("&View")
        if view_menu is None:
            return

        zoom_in = view_menu.addAction("Zoom &In")
        if zoom_in is not None:
            zoom_in.setShortcut(QKeySequence(SHORTCUTS["view.zoom_in"]))
            zoom_in.triggered.connect(self._view.zoom_in)

        zoom_out = view_menu.addAction("Zoom &Out")
        if zoom_out is not None:
            zoom_out.setShortcut(QKeySequence(SHORTCUTS["view.zoom_out"]))
            zoom_out.triggered.connect(self._view.zoom_out)

        fit_action = view_menu.addAction("&Fit to Window")
        if fit_action is not None:
            fit_action.setShortcut(QKeySequence(SHORTCUTS["view.fit_window"]))
            fit_action.triggered.connect(self._view.fit_in_view_all)

        actual_action = view_menu.addAction("&Actual Size")
        if actual_action is not None:
            actual_action.setShortcut(QKeySequence(SHORTCUTS["view.actual_size"]))
            actual_action.triggered.connect(lambda: self._view.set_zoom(100))

        zoom_sel_action = view_menu.addAction("Zoom to &Selection")
        if zoom_sel_action is not None:
            zoom_sel_action.setShortcut(QKeySequence(SHORTCUTS["view.zoom_to_selection"]))
            zoom_sel_action.triggered.connect(self._view_zoom_to_selection)

        view_menu.addSeparator()

        self._grid_action = QAction("Show &Grid", self)
        self._grid_action.setCheckable(True)
        self._grid_action.setShortcut(QKeySequence(SHORTCUTS["view.toggle_grid"]))
        grid_vis = self._settings.grid_visible()
        self._grid_action.setChecked(grid_vis)
        self._view.set_grid_visible(grid_vis)
        self._grid_action.toggled.connect(self._toggle_grid)
        view_menu.addAction(self._grid_action)

        self._rulers_action = QAction("Show &Rulers", self)
        self._rulers_action.setCheckable(True)
        self._rulers_action.setShortcut(QKeySequence(SHORTCUTS["view.toggle_rulers"]))
        rulers_vis = self._settings.rulers_visible()
        self._rulers_action.setChecked(rulers_vis)
        self._view.set_rulers_visible(rulers_vis)
        self._rulers_action.toggled.connect(self._toggle_rulers)
        view_menu.addAction(self._rulers_action)

        self._snap_grid_action = QAction("&Snap to Grid", self)
        self._snap_grid_action.setCheckable(True)
        self._snap_grid_action.setShortcut(QKeySequence(SHORTCUTS["view.snap_to_grid"]))
        self._snap_grid_action.setChecked(self._settings.snap_to_grid())
        self._snap_grid_action.toggled.connect(self._toggle_snap_to_grid)
        view_menu.addAction(self._snap_grid_action)

        view_menu.addSeparator()

        # Panel visibility toggles
        toolbar_toggle = self._toolbar.toggleViewAction()
        if toolbar_toggle is not None:
            toolbar_toggle.setText("Show Tool&bar")
            view_menu.addAction(toolbar_toggle)

        options_toggle = self._tool_options.toggleViewAction()
        if options_toggle is not None:
            options_toggle.setText("Show &Options Bar")
            view_menu.addAction(options_toggle)

        layer_toggle = self._layer_panel.toggleViewAction()
        if layer_toggle is not None:
            layer_toggle.setText("Show &Layers Panel")
            view_menu.addAction(layer_toggle)

        property_toggle = self._property_panel.toggleViewAction()
        if property_toggle is not None:
            property_toggle.setText("Show &Properties Panel")
            view_menu.addAction(property_toggle)

    def _setup_image_menu(self, menu_bar: QMenuBar) -> None:
        image_menu = menu_bar.addMenu("&Image")
        if image_menu is None:
            return

        resize_canvas_action = image_menu.addAction("Resize &Canvas...")
        if resize_canvas_action is not None:
            resize_canvas_action.triggered.connect(self._image_resize_canvas)

        resize_image_action = image_menu.addAction("Resize &Image...")
        if resize_image_action is not None:
            resize_image_action.triggered.connect(self._image_resize_image)

        crop_canvas_action = image_menu.addAction("Crop to C&anvas")
        if crop_canvas_action is not None:
            crop_canvas_action.setShortcut(QKeySequence(SHORTCUTS["image.crop_to_canvas"]))
            crop_canvas_action.triggered.connect(self._image_crop_to_canvas)

        image_menu.addSeparator()

        rotate_cw_action = image_menu.addAction("Rotate 90° C&W")
        if rotate_cw_action is not None:
            rotate_cw_action.triggered.connect(self._image_rotate_cw)

        rotate_ccw_action = image_menu.addAction("Rotate 90° CC&W")
        if rotate_ccw_action is not None:
            rotate_ccw_action.triggered.connect(self._image_rotate_ccw)

        image_menu.addSeparator()

        flip_h_action = image_menu.addAction("Flip &Horizontal")
        if flip_h_action is not None:
            flip_h_action.triggered.connect(self._image_flip_h)

        flip_v_action = image_menu.addAction("Flip &Vertical")
        if flip_v_action is not None:
            flip_v_action.triggered.connect(self._image_flip_v)

        image_menu.addSeparator()

        auto_trim_action = image_menu.addAction("Auto-&Trim")
        if auto_trim_action is not None:
            auto_trim_action.triggered.connect(self._image_auto_trim)

    # ---- new menus ----

    def _setup_layer_menu(self, menu_bar: QMenuBar) -> None:  # noqa: C901
        layer_menu = menu_bar.addMenu("&Layer")
        if layer_menu is None:
            return

        new_layer_action = layer_menu.addAction("&New Layer")
        if new_layer_action is not None:
            new_layer_action.setShortcut(QKeySequence(SHORTCUTS["layer.new"]))
            new_layer_action.triggered.connect(self._layer_new)

        dup_layer_action = layer_menu.addAction("&Duplicate Layer")
        if dup_layer_action is not None:
            dup_layer_action.triggered.connect(self._layer_duplicate)

        self._layer_delete_action = QAction("De&lete Layer", self)
        self._layer_delete_action.setShortcut(QKeySequence(SHORTCUTS["layer.delete"]))
        self._layer_delete_action.triggered.connect(self._layer_delete)
        layer_menu.addAction(self._layer_delete_action)

        layer_menu.addSeparator()

        self._layer_merge_down_action = QAction("&Merge Down", self)
        self._layer_merge_down_action.setShortcut(QKeySequence(SHORTCUTS["layer.merge_down"]))
        self._layer_merge_down_action.triggered.connect(self._layer_merge_down)
        layer_menu.addAction(self._layer_merge_down_action)

        merge_visible_action = layer_menu.addAction("Merge &Visible")
        if merge_visible_action is not None:
            merge_visible_action.triggered.connect(self._layer_merge_visible)

        flatten_action = layer_menu.addAction("&Flatten All")
        if flatten_action is not None:
            flatten_action.setShortcut(QKeySequence(SHORTCUTS["layer.flatten"]))
            flatten_action.triggered.connect(self._layer_flatten)

        layer_menu.addSeparator()

        rename_action = layer_menu.addAction("&Rename Layer")
        if rename_action is not None:
            rename_action.setShortcut(QKeySequence(SHORTCUTS["layer.rename"]))
            rename_action.triggered.connect(self._layer_rename)

        props_action = layer_menu.addAction("Layer &Properties...")
        if props_action is not None:
            props_action.triggered.connect(self._layer_properties)

        layer_menu.addSeparator()

        self._layer_move_up_action = QAction("Move &Up", self)
        self._layer_move_up_action.setShortcut(QKeySequence(SHORTCUTS["layer.move_up"]))
        self._layer_move_up_action.triggered.connect(self._layer_move_up)
        layer_menu.addAction(self._layer_move_up_action)

        self._layer_move_down_action = QAction("Move &Down", self)
        self._layer_move_down_action.setShortcut(QKeySequence(SHORTCUTS["layer.move_down"]))
        self._layer_move_down_action.triggered.connect(self._layer_move_down)
        layer_menu.addAction(self._layer_move_down_action)

        self._layer_move_top_action = QAction("Move to &Top", self)
        self._layer_move_top_action.setShortcut(QKeySequence(SHORTCUTS["layer.move_to_top"]))
        self._layer_move_top_action.triggered.connect(self._layer_move_to_top)
        layer_menu.addAction(self._layer_move_top_action)

        self._layer_move_bottom_action = QAction("Move to &Bottom", self)
        self._layer_move_bottom_action.setShortcut(QKeySequence(SHORTCUTS["layer.move_to_bottom"]))
        self._layer_move_bottom_action.triggered.connect(self._layer_move_to_bottom)
        layer_menu.addAction(self._layer_move_bottom_action)

    def _setup_arrange_menu(self, menu_bar: QMenuBar) -> None:
        arrange_menu = menu_bar.addMenu("&Arrange")
        if arrange_menu is None:
            return

        self._bring_front_action = QAction("Bring to &Front", self)
        self._bring_front_action.setShortcut(QKeySequence(SHORTCUTS["arrange.bring_to_front"]))
        self._bring_front_action.triggered.connect(self._arrange_bring_to_front)
        arrange_menu.addAction(self._bring_front_action)

        self._bring_forward_action = QAction("Bring For&ward", self)
        self._bring_forward_action.setShortcut(QKeySequence(SHORTCUTS["arrange.bring_forward"]))
        self._bring_forward_action.triggered.connect(self._arrange_bring_forward)
        arrange_menu.addAction(self._bring_forward_action)

        self._send_backward_action = QAction("Send &Backward", self)
        self._send_backward_action.setShortcut(QKeySequence(SHORTCUTS["arrange.send_backward"]))
        self._send_backward_action.triggered.connect(self._arrange_send_backward)
        arrange_menu.addAction(self._send_backward_action)

        self._send_to_back_action = QAction("Send to Bac&k", self)
        self._send_to_back_action.setShortcut(QKeySequence(SHORTCUTS["arrange.send_to_back"]))
        self._send_to_back_action.triggered.connect(self._arrange_send_to_back)
        arrange_menu.addAction(self._send_to_back_action)

        arrange_menu.addSeparator()

        # Align submenu
        self._align_menu = arrange_menu.addMenu("Ali&gn")
        if self._align_menu is not None:
            for label, alignment in [
                ("Align &Left", "left"),
                ("Align Center &Horizontal", "center_h"),
                ("Align &Right", "right"),
                ("Align &Top", "top"),
                ("Align &Middle Vertical", "middle_v"),
                ("Align &Bottom", "bottom"),
            ]:
                action = self._align_menu.addAction(label)
                if action is not None:
                    action.triggered.connect(
                        lambda _checked=False, a=alignment: self._arrange_align(a)
                    )

        # Distribute submenu
        self._distribute_menu = arrange_menu.addMenu("&Distribute")
        if self._distribute_menu is not None:
            dist_h = self._distribute_menu.addAction("Distribute &Horizontally")
            if dist_h is not None:
                dist_h.triggered.connect(
                    lambda _checked=False: self._arrange_distribute("horizontal")
                )
            dist_v = self._distribute_menu.addAction("Distribute &Vertically")
            if dist_v is not None:
                dist_v.triggered.connect(
                    lambda _checked=False: self._arrange_distribute("vertical")
                )

        arrange_menu.addSeparator()

        self._align_canvas_action = QAction("Align to Canvas &Center", self)
        self._align_canvas_action.triggered.connect(self._arrange_align_canvas_center)
        arrange_menu.addAction(self._align_canvas_action)

    def _setup_tools_menu(self, menu_bar: QMenuBar) -> None:
        tools_menu = menu_bar.addMenu("&Tools")
        if tools_menu is None:
            return

        # Tool groups for separator placement
        tool_groups: list[list[tuple[str, str]]] = [
            # Selection tools
            [("tool.select", "select"), ("tool.lasso_select", "lasso_select")],
            # Shape tools
            [
                ("tool.rectangle", "rectangle"),
                ("tool.ellipse", "ellipse"),
                ("tool.line", "line"),
                ("tool.arrow", "arrow"),
                ("tool.freehand", "freehand"),
            ],
            # Text & annotation
            [
                ("tool.text", "text"),
                ("tool.callout", "callout"),
                ("tool.numbered_step", "numbered_step"),
                ("tool.stamp", "stamp"),
            ],
            # Effects
            [("tool.highlight", "highlight"), ("tool.blur", "blur")],
            # Region tools
            [
                ("tool.crop", "crop"),
                ("tool.raster_select", "raster_select"),
                ("tool.eyedropper", "eyedropper"),
            ],
            # Navigation
            [("tool.pan", "pan"), ("tool.zoom", "zoom")],
        ]

        first_group = True
        for group in tool_groups:
            if not first_group:
                tools_menu.addSeparator()
            first_group = False
            for shortcut_key, tool_id in group:
                tool = self._tool_manager.tool(tool_id)
                if tool is None:
                    continue
                key_seq = SHORTCUTS.get(shortcut_key, "")
                action = QAction(tool.display_name, self)
                action.setCheckable(True)
                if key_seq:
                    action.setShortcut(QKeySequence(key_seq))
                action.triggered.connect(
                    lambda _checked=False, tid=tool_id: self._tool_manager.activate(tid)
                )
                tools_menu.addAction(action)
                self._tool_actions[tool_id] = action

        # Wire tool_changed signal to update checkmarks
        self._tool_manager.tool_changed.connect(self._update_tools_menu_check)
        # Set initial checkmark
        self._update_tools_menu_check(self._tool_manager.active_tool_id)

    def _setup_help_menu(self, menu_bar: QMenuBar) -> None:
        help_menu = menu_bar.addMenu("&Help")
        if help_menu is None:
            return

        welcome_action = help_menu.addAction("&Welcome")
        if welcome_action is not None:
            welcome_action.triggered.connect(self._help_welcome)

        docs_action = help_menu.addAction("&Documentation")
        if docs_action is not None:
            docs_action.triggered.connect(self._help_docs)

        shortcuts_action = help_menu.addAction("&Keyboard Shortcuts")
        if shortcuts_action is not None:
            shortcuts_action.triggered.connect(self._help_shortcuts)

        help_menu.addSeparator()

        bug_action = help_menu.addAction("Report a &Bug")
        if bug_action is not None:
            bug_action.triggered.connect(self._help_report_bug)

        updates_action = help_menu.addAction("Check for &Updates")
        if updates_action is not None:
            updates_action.triggered.connect(self._help_check_updates)

        help_menu.addSeparator()

        about_action = help_menu.addAction("&About SnapMock")
        if about_action is not None:
            about_action.triggered.connect(self._help_about)

    # ---- view toggles ----

    def _toggle_grid(self, checked: bool) -> None:
        self._view.set_grid_visible(checked)
        self._settings.set_grid_visible(checked)

    def _toggle_rulers(self, checked: bool) -> None:
        self._view.set_rulers_visible(checked)
        self._settings.set_rulers_visible(checked)

    def _toggle_snap_to_grid(self, checked: bool) -> None:
        self._settings.set_snap_to_grid(checked)

    def _on_tool_changed_for_hint(self, _tool_id: str) -> None:
        tool = self._tool_manager.active_tool
        if tool is not None:
            self._status_bar.set_hint(tool.status_hint)
        else:
            self._status_bar.set_hint("")

    def _update_tools_menu_check(self, tool_id: str) -> None:
        """Update checkmarks in the Tools menu to reflect the active tool."""
        for tid, action in self._tool_actions.items():
            action.setChecked(tid == tool_id)

    # ---- signals ----

    def _connect_layer_signals(self) -> None:
        lm = self._scene.layer_manager
        lm.layer_lock_changed.connect(self._on_layer_lock_changed)
        lm.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        lm.active_layer_changed.connect(self._on_active_layer_changed)

    def _connect_menu_state_signals(self) -> None:
        """Wire selection/layer signals to menu state updates."""
        self._selection_manager.selection_changed.connect(
            lambda _items: self._update_menu_states()
        )
        self._selection_manager.selection_cleared.connect(self._update_menu_states)
        lm = self._scene.layer_manager
        lm.active_layer_changed.connect(lambda _lid: self._update_menu_states())
        lm.layers_reordered.connect(self._update_menu_states)
        lm.layer_added.connect(lambda _l: self._update_menu_states())
        lm.layer_removed.connect(lambda _lid: self._update_menu_states())

    def _update_menu_states(self) -> None:
        """Enable/disable arrange and layer actions based on current state."""
        sel_count = self._selection_manager.count
        has_selection = sel_count > 0
        multi_selection = sel_count >= 2
        triple_selection = sel_count >= 3

        # Arrange z-order actions need at least 1 selected item
        for action in (
            self._bring_front_action,
            self._bring_forward_action,
            self._send_backward_action,
            self._send_to_back_action,
            self._align_canvas_action,
        ):
            if action is not None:
                action.setEnabled(has_selection)

        # Align needs 2+, distribute needs 3+
        if self._align_menu is not None:
            self._align_menu.setEnabled(multi_selection)
        if self._distribute_menu is not None:
            self._distribute_menu.setEnabled(triple_selection)

        # Layer reorder actions based on active layer position
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is not None:
            idx = lm.index_of(active.layer_id)
            count = lm.count
            can_up = idx < count - 1
            can_down = idx > 0
            for action in (self._layer_move_up_action, self._layer_move_top_action):
                if action is not None:
                    action.setEnabled(can_up)
            for action in (self._layer_move_down_action, self._layer_move_bottom_action):
                if action is not None:
                    action.setEnabled(can_down)
            # Can't delete the last layer
            if self._layer_delete_action is not None:
                self._layer_delete_action.setEnabled(count > 1)
            # Merge down requires a layer below
            if self._layer_merge_down_action is not None:
                self._layer_merge_down_action.setEnabled(idx > 0)

    def _on_layer_lock_changed(self, layer_id: str, locked: bool) -> None:
        if locked:
            self._deselect_items_on_layer(layer_id)

    def _on_layer_visibility_changed(self, layer_id: str, visible: bool) -> None:
        if not visible:
            self._deselect_items_on_layer(layer_id)

    def _on_active_layer_changed(self, _layer_id: str) -> None:
        # Cancel active raster/lasso selection when layer changes
        active = self._tool_manager.active_tool
        if active is not None and active.is_active_operation:
            if isinstance(active, (RasterSelectTool, LassoSelectTool)):
                active.cancel()

    def _deselect_items_on_layer(self, layer_id: str) -> None:
        """Deselect any selected items on the given layer."""
        affected = [
            i
            for i in self._selection_manager.items
            if isinstance(i, SnapGraphicsItem) and i.layer_id == layer_id
        ]
        if affected:
            for item in affected:
                self._selection_manager.toggle(item)

    def _view_zoom_to_selection(self) -> None:
        """Zoom to fit the current selection in the viewport."""
        items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
        if not items:
            return
        rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        pad = 20
        self._view.zoom_to_rect(rect.adjusted(-pad, -pad, pad, pad))

    # ---- file operations ----

    def _file_new(self) -> None:
        """Create a new empty project."""
        if not self._confirm_discard():
            return
        # Deactivate current tool while old scene is still alive
        prev_tool_id = self._tool_manager.active_tool_id or "select"
        if self._tool_manager.active_tool is not None:
            self._tool_manager.active_tool.cancel()
            self._tool_manager.active_tool.deactivate()
        old_scene = self._scene
        self._scene = SnapScene(parent=self)
        self._view.setScene(self._scene)
        self._selection_manager = SelectionManager(self._scene, parent=self)
        self._tool_manager._scene = self._scene  # noqa: SLF001
        self._tool_manager._selection_manager = self._selection_manager  # noqa: SLF001
        self._tool_manager.activate(prev_tool_id)
        self._clipboard = ClipboardManager(self._scene, parent=self)
        self._layer_panel.set_manager(self._scene.layer_manager)
        self._property_panel.set_scene(self._scene)
        self._property_panel.set_selection(self._selection_manager)
        self._scene.command_stack.stack_changed.connect(self._update_title)
        self._connect_layer_signals()
        self._connect_menu_state_signals()
        self._current_file = None
        self._update_title()
        self._update_menu_states()
        old_scene.deleteLater()

    def _file_open(self) -> None:
        """Open an existing .smk or .snagx project."""
        if not self._confirm_discard():
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            f"All Supported (*{PROJECT_EXTENSION} *{SNAGIT_EXTENSION})"
            f";;SnapMock Projects (*{PROJECT_EXTENSION})"
            f";;Snagit Files (*{SNAGIT_EXTENSION})"
            ";;All Files (*)",
        )
        if not path_str:
            return
        self._open_project(Path(path_str))

    def _open_project(self, path: Path) -> None:
        """Load a project from *path* and replace the current scene."""
        # Deactivate current tool while old scene is still alive
        prev_tool_id = self._tool_manager.active_tool_id or "select"
        if self._tool_manager.active_tool is not None:
            self._tool_manager.active_tool.cancel()
            self._tool_manager.active_tool.deactivate()
        old_scene = self._scene
        try:
            if path.suffix.lower() == SNAGIT_EXTENSION:
                self._scene = load_snagx(path)
            else:
                self._scene = load_project(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Open Error", f"Could not open project:\n{e}")
            # Re-activate tool on old scene since load failed
            self._tool_manager.activate(prev_tool_id)
            return
        self._scene.setParent(self)
        self._view.setScene(self._scene)
        self._selection_manager = SelectionManager(self._scene, parent=self)
        self._tool_manager._scene = self._scene  # noqa: SLF001
        self._tool_manager._selection_manager = self._selection_manager  # noqa: SLF001
        self._tool_manager.activate(prev_tool_id)
        self._clipboard = ClipboardManager(self._scene, parent=self)
        self._layer_panel.set_manager(self._scene.layer_manager)
        self._property_panel.set_scene(self._scene)
        self._property_panel.set_selection(self._selection_manager)
        self._scene.command_stack.stack_changed.connect(self._update_title)
        self._connect_layer_signals()
        self._connect_menu_state_signals()
        self._current_file = path
        self._add_recent_file(path)
        self._update_title()
        self._update_menu_states()
        old_scene.deleteLater()

    def _file_save(self) -> None:
        """Save the current project."""
        if self._current_file is None:
            self._file_save_as()
            return
        self._save_to(self._current_file)

    def _file_save_as(self) -> None:
        """Save the current project to a new path."""
        path_str, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            "",
            f"SnapMock Projects (*{PROJECT_EXTENSION})"
            f";;Snagit Files (*{SNAGIT_EXTENSION})",
        )
        if not path_str:
            return
        path = Path(path_str)
        if SNAGIT_EXTENSION in selected_filter or path.suffix.lower() == SNAGIT_EXTENSION:
            if path.suffix.lower() != SNAGIT_EXTENSION:
                path = path.with_suffix(SNAGIT_EXTENSION)
        elif path.suffix.lower() != PROJECT_EXTENSION:
            path = path.with_suffix(PROJECT_EXTENSION)
        self._save_to(path)

    def _save_to(self, path: Path) -> None:
        try:
            if path.suffix.lower() == SNAGIT_EXTENSION:
                warnings = save_snagx(self._scene, path)
                if warnings:
                    QMessageBox.warning(
                        self,
                        "Snagit Export Warnings",
                        "Some items could not be saved:\n\n" + "\n".join(warnings),
                    )
            else:
                save_project(self._scene, path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save Error", f"Could not save project:\n{e}")
            return
        self._current_file = path
        self._scene.command_stack.mark_clean()
        self._add_recent_file(path)
        self._update_title()

    def _file_import_image(self) -> None:
        """Import an image file into the scene."""
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Import Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if not path_str:
            return
        import_image(self._scene, Path(path_str))

    def _file_export(self) -> None:
        """Export the scene to an image or document format."""
        path_str, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export",
            "",
            "PNG Image (*.png);;JPEG Image (*.jpg);;SVG Image (*.svg);;PDF Document (*.pdf)",
        )
        if not path_str:
            return
        path = Path(path_str)
        suffix = path.suffix.lower()
        if suffix == ".png" or "PNG" in selected_filter:
            export_png(self._scene, path)
        elif suffix in (".jpg", ".jpeg") or "JPEG" in selected_filter:
            export_jpg(self._scene, path)
        elif suffix == ".svg" or "SVG" in selected_filter:
            export_svg(self._scene, path)
        elif suffix == ".pdf" or "PDF" in selected_filter:
            export_pdf(self._scene, path)

    def _file_export_quick_png(self) -> None:
        """Quick-export the scene as PNG next to the current file."""
        if self._current_file is not None:
            path = self._current_file.with_suffix(".png")
        else:
            path_str, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG Image (*.png)")
            if not path_str:
                return
            path = Path(path_str)
        export_png(self._scene, path)

    def _file_print(self) -> None:
        QMessageBox.information(self, "Print", "Print support is coming soon.")

    def _file_preferences(self) -> None:
        from snapmock.ui.preferences_dialog import PreferencesDialog

        dlg = PreferencesDialog(self._settings, self)
        if dlg.exec() == PreferencesDialog.DialogCode.Accepted:
            self._apply_preference_changes(dlg.get_changes())

    def _apply_preference_changes(
        self, changes: dict[str, tuple[object, object]]
    ) -> None:
        """Write changed preferences to settings and sync live UI state."""
        if not changes:
            return

        def _int(val: object) -> int:
            return val if isinstance(val, int) else int(str(val))

        if "grid_visible" in changes:
            visible = bool(changes["grid_visible"][1])
            self._settings.set_grid_visible(visible)
            self._grid_action.blockSignals(True)
            self._grid_action.setChecked(visible)
            self._grid_action.blockSignals(False)
            self._view.set_grid_visible(visible)

        if "grid_size" in changes:
            size = _int(changes["grid_size"][1])
            self._settings.set_grid_size(size)
            self._view.set_grid_size(size)

        if "rulers_visible" in changes:
            visible = bool(changes["rulers_visible"][1])
            self._settings.set_rulers_visible(visible)
            self._rulers_action.blockSignals(True)
            self._rulers_action.setChecked(visible)
            self._rulers_action.blockSignals(False)
            self._view.set_rulers_visible(visible)

        if "snap_to_grid" in changes:
            enabled = bool(changes["snap_to_grid"][1])
            self._settings.set_snap_to_grid(enabled)
            self._snap_grid_action.blockSignals(True)
            self._snap_grid_action.setChecked(enabled)
            self._snap_grid_action.blockSignals(False)

        if "autosave_interval" in changes:
            minutes = _int(changes["autosave_interval"][1])
            self._settings.set_autosave_interval_minutes(minutes)

        if "autosave_enabled" in changes:
            enabled = bool(changes["autosave_enabled"][1])
            self._settings.set_autosave_enabled(enabled)

        # Restart or stop autosave timer based on current settings
        if "autosave_enabled" in changes or "autosave_interval" in changes:
            self._autosave_timer.stop()
            if self._settings.autosave_enabled():
                ms = self._settings.autosave_interval_minutes() * 60_000
                self._autosave_timer.start(ms)

    # ---- edit operations ----

    def _edit_undo(self) -> None:
        """Undo — first cancel any active tool operation, then undo."""
        active = self._tool_manager.active_tool
        if active is not None and active.is_active_operation:
            active.cancel()
            return  # first Ctrl+Z cancels active operation
        self._scene.command_stack.undo()

    def _edit_cut(self) -> None:
        active = self._tool_manager.active_tool
        if (
            isinstance(active, (RasterSelectTool, LassoSelectTool))
            and hasattr(active, "has_active_selection")
            and active.has_active_selection
        ):
            self._copy_raster_selection(active)
            self._cut_raster_selection(active)
            return
        self._edit_copy()
        self._edit_delete()

    def _edit_copy(self) -> None:
        active = self._tool_manager.active_tool
        if (
            isinstance(active, (RasterSelectTool, LassoSelectTool))
            and hasattr(active, "has_active_selection")
            and active.has_active_selection
        ):
            self._copy_raster_selection(active)
            return
        items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
        if items:
            self._clipboard.copy_items(items)

    def _copy_raster_selection(self, tool: RasterSelectTool | LassoSelectTool) -> None:
        """Copy pixels from a raster/lasso selection to the clipboard."""
        from snapmock.core.render_engine import RenderEngine

        rect = tool.selection_rect
        if rect.isEmpty():
            return
        engine = RenderEngine(self._scene)
        image = engine.render_region(rect)
        self._clipboard.copy_raster_region(image, rect)

    def _cut_raster_selection(self, tool: RasterSelectTool | LassoSelectTool) -> None:
        """Cut pixels from a raster/lasso selection (erase after copy)."""
        from PyQt6.QtGui import QImage

        from snapmock.commands.raster_commands import RasterCutCommand

        rect = tool.selection_rect
        layer = self._scene.layer_manager.active_layer
        if layer is not None and not rect.isEmpty():
            cmd = RasterCutCommand(self._scene, rect, QImage(), layer.layer_id)
            self._scene.command_stack.push(cmd)
        tool.cancel()

    def _edit_paste(self) -> None:
        # Smart paste routing: internal items → internal raster → system image → system text
        # 1. Internal vector items
        data = self._clipboard.paste_items()
        if data:
            self._paste_internal_items(data, offset=True)
            return
        # 2. Internal raster data
        raster, source_rect = self._clipboard.paste_raster()
        if raster is not None:
            self._paste_raster_image(raster, source_rect)
            return
        # 3. System clipboard image
        sys_image = self._clipboard.paste_image_from_system()
        if sys_image is not None:
            self._paste_system_image(sys_image)
            return
        # 4. System clipboard text
        clipboard = QApplication.clipboard()
        if clipboard and clipboard.text():
            self._paste_system_text(clipboard.text())

    def _paste_internal_items(self, data: list[dict], *, offset: bool) -> None:  # type: ignore[type-arg]
        from snapmock.commands.add_item import AddItemCommand
        from snapmock.io.project_serializer import ITEM_REGISTRY

        layer = self._scene.layer_manager.active_layer
        if layer is None:
            return
        for item_data in data:
            item_type = item_data.get("type", "")
            cls = ITEM_REGISTRY.get(item_type)
            if cls is not None:
                item = cls.deserialize(item_data)
                if offset:
                    item.setPos(item.pos().x() + 10, item.pos().y() + 10)
                self._scene.command_stack.push(AddItemCommand(self._scene, item, layer.layer_id))

    def _paste_raster_image(self, image: object, source_rect: object | None) -> None:
        """Paste a raster image at its source position."""
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QImage, QPixmap

        from snapmock.commands.add_item import AddItemCommand
        from snapmock.items.raster_region_item import RasterRegionItem

        if not isinstance(image, QImage):
            return
        pixmap = QPixmap.fromImage(image)
        item = RasterRegionItem(pixmap=pixmap)
        # Place at source position if available, else viewport center
        if isinstance(source_rect, QRectF) and not source_rect.isEmpty():
            item.setPos(source_rect.topLeft())
        else:
            view = self._view
            viewport = view.viewport()
            if viewport is not None:
                center = view.mapToScene(viewport.rect().center())
                item.setPos(
                    center.x() - pixmap.width() / 2,
                    center.y() - pixmap.height() / 2,
                )
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            self._scene.command_stack.push(AddItemCommand(self._scene, item, layer.layer_id))
            # Switch to select tool and select the new item
            self._tool_manager.activate("select")
            self._selection_manager.select(item)

    def _paste_system_text(self, text: str) -> None:
        """Paste system clipboard text as a TextItem."""
        from snapmock.commands.add_item import AddItemCommand
        from snapmock.items.text_item import TextItem

        item = TextItem(text=text)
        # Place at viewport center
        view = self._view
        viewport = view.viewport()
        if viewport is not None:
            center = view.mapToScene(viewport.rect().center())
            item.setPos(center.x() - 100, center.y() - 20)
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            self._scene.command_stack.push(AddItemCommand(self._scene, item, layer.layer_id))
            self._tool_manager.activate("select")
            self._selection_manager.select(item)

    def _paste_system_image(self, image: object) -> None:
        from PyQt6.QtGui import QPixmap

        from snapmock.commands.add_item import AddItemCommand
        from snapmock.items.raster_region_item import RasterRegionItem

        pixmap = QPixmap.fromImage(image)  # type: ignore[arg-type]
        item = RasterRegionItem(pixmap=pixmap)
        # Place at viewport center
        view = self._view
        viewport = view.viewport()
        if viewport is None:
            return
        center = view.mapToScene(viewport.rect().center())
        item.setPos(center.x() - pixmap.width() / 2, center.y() - pixmap.height() / 2)
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            self._scene.command_stack.push(AddItemCommand(self._scene, item, layer.layer_id))

    def _edit_paste_in_place(self) -> None:
        """Paste items at their original positions (no offset)."""
        data = self._clipboard.paste_items()
        if data:
            self._paste_internal_items(data, offset=False)
            return
        raster, source_rect = self._clipboard.paste_raster()
        if raster is not None:
            self._paste_raster_image(raster, source_rect)
            return
        sys_image = self._clipboard.paste_image_from_system()
        if sys_image is not None:
            self._paste_system_image(sys_image)

    def _edit_delete(self) -> None:
        items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
        if not items:
            return
        from snapmock.commands.remove_item import RemoveItemCommand

        for item in items:
            self._scene.command_stack.push(RemoveItemCommand(self._scene, item))
        self._selection_manager.deselect_all()

    def _edit_duplicate(self) -> None:
        """Clone selected items with +10,+10 offset."""
        items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
        if not items:
            return
        from snapmock.commands.add_item import AddItemCommand

        layer = self._scene.layer_manager.active_layer
        if layer is None:
            return
        clones: list[QGraphicsItem] = []
        for item in items:
            clone = item.clone()
            clone.setPos(clone.pos().x() + 10, clone.pos().y() + 10)
            self._scene.command_stack.push(AddItemCommand(self._scene, clone, layer.layer_id))
            clones.append(clone)
        self._selection_manager.select_items(clones)

    def _edit_select_all(self) -> None:
        all_items: list[QGraphicsItem] = [
            i for i in self._scene.items() if isinstance(i, SnapGraphicsItem)
        ]
        self._selection_manager.select_items(all_items)

    def _edit_select_all_layers(self) -> None:
        """Select all items across all layers."""
        all_items: list[QGraphicsItem] = [
            i for i in self._scene.items() if isinstance(i, SnapGraphicsItem)
        ]
        self._selection_manager.select_items(all_items)

    # ---- image operations ----

    def _image_resize_canvas(self) -> None:
        from snapmock.commands.raster_commands import ResizeCanvasCommand
        from snapmock.ui.resize_canvas_dialog import ResizeCanvasDialog

        dlg = ResizeCanvasDialog(self._scene.canvas_size, self)
        if dlg.exec():
            cmd = ResizeCanvasCommand(
                self._scene,
                dlg.new_size(),
                dlg.anchor(),
                dlg.fill_color(),
            )
            self._scene.command_stack.push(cmd)

    def _image_resize_image(self) -> None:
        from snapmock.commands.raster_commands import ResizeImageCommand
        from snapmock.ui.resize_image_dialog import ResizeImageDialog

        dlg = ResizeImageDialog(self._scene.canvas_size, self)
        if dlg.exec():
            cmd = ResizeImageCommand(self._scene, dlg.new_size())
            self._scene.command_stack.push(cmd)

    def _image_crop_to_canvas(self) -> None:
        """Remove items outside the canvas bounds."""
        from snapmock.commands.remove_item import RemoveItemCommand

        for scene_item in list(self._scene.items()):
            if isinstance(scene_item, SnapGraphicsItem):
                if not scene_item.sceneBoundingRect().intersects(self._scene.canvas_rect):
                    self._scene.command_stack.push(RemoveItemCommand(self._scene, scene_item))

    def _image_rotate_cw(self) -> None:
        from snapmock.commands.canvas_transform_commands import RotateCanvasCommand

        cmd = RotateCanvasCommand(self._scene, clockwise=True)
        self._scene.command_stack.push(cmd)

    def _image_rotate_ccw(self) -> None:
        from snapmock.commands.canvas_transform_commands import RotateCanvasCommand

        cmd = RotateCanvasCommand(self._scene, clockwise=False)
        self._scene.command_stack.push(cmd)

    def _image_flip_h(self) -> None:
        from snapmock.commands.canvas_transform_commands import FlipCanvasCommand

        cmd = FlipCanvasCommand(self._scene, horizontal=True)
        self._scene.command_stack.push(cmd)

    def _image_flip_v(self) -> None:
        from snapmock.commands.canvas_transform_commands import FlipCanvasCommand

        cmd = FlipCanvasCommand(self._scene, horizontal=False)
        self._scene.command_stack.push(cmd)

    def _image_auto_trim(self) -> None:
        QMessageBox.information(self, "Auto-Trim", "Auto-trim is coming soon.")

    # ---- layer operations ----

    def _layer_new(self) -> None:
        from snapmock.commands.layer_commands import AddLayerCommand

        lm = self._scene.layer_manager
        name = f"Layer {lm.count + 1}"
        cmd = AddLayerCommand(lm, name)
        self._scene.command_stack.push(cmd)

    def _layer_duplicate(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is None:
            return
        from snapmock.commands.layer_commands import AddLayerCommand

        idx = lm.index_of(active.layer_id) + 1
        cmd = AddLayerCommand(lm, f"{active.name} copy", idx)
        self._scene.command_stack.push(cmd)

    def _layer_delete(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is None or lm.count <= 1:
            return
        from snapmock.commands.layer_commands import RemoveLayerCommand

        cmd = RemoveLayerCommand(lm, active.layer_id)
        self._scene.command_stack.push(cmd)

    def _layer_merge_down(self) -> None:
        QMessageBox.information(self, "Merge Down", "Merge down is coming soon.")

    def _layer_merge_visible(self) -> None:
        QMessageBox.information(self, "Merge Visible", "Merge visible is coming soon.")

    def _layer_flatten(self) -> None:
        QMessageBox.information(self, "Flatten All", "Flatten all is coming soon.")

    def _layer_rename(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is None:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Layer", "New name:", text=active.name)
        if ok and new_name:
            from snapmock.commands.layer_commands import ChangeLayerPropertyCommand

            cmd = ChangeLayerPropertyCommand(lm, active.layer_id, "name", active.name, new_name)
            self._scene.command_stack.push(cmd)

    def _layer_properties(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is not None:
            self._show_layer_properties(active.layer_id)

    def _show_item_properties(self) -> None:
        """Show the item properties dialog for the first selected item."""
        items = self._selected_snap_items()
        if not items:
            return
        item = items[0]

        from snapmock.ui.item_properties_dialog import ItemPropertiesDialog

        dlg = ItemPropertiesDialog(item, self._scene, self)
        if dlg.exec() == ItemPropertiesDialog.DialogCode.Accepted:
            from snapmock.commands.modify_property import ModifyPropertyCommand

            for prop_name, (old_val, new_val) in dlg.get_changes().items():
                cmd = ModifyPropertyCommand(item, prop_name, old_val, new_val)
                self._scene.command_stack.push(cmd)

    def _show_layer_properties(self, layer_id: str) -> None:
        """Show the layer properties dialog for the given layer."""
        lm = self._scene.layer_manager
        layer = lm.layer_by_id(layer_id)
        if layer is None:
            return

        from snapmock.ui.layer_properties_dialog import LayerPropertiesDialog

        dlg = LayerPropertiesDialog(layer, self)
        if dlg.exec() == LayerPropertiesDialog.DialogCode.Accepted:
            from snapmock.commands.layer_commands import ChangeLayerPropertyCommand

            for prop_name, (old_val, new_val) in dlg.get_changes().items():
                cmd = ChangeLayerPropertyCommand(lm, layer_id, prop_name, old_val, new_val)
                self._scene.command_stack.push(cmd)

    def _layer_move_up(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if idx < lm.count - 1:
            from snapmock.commands.layer_commands import ReorderLayerCommand

            cmd = ReorderLayerCommand(lm, active.layer_id, idx + 1)
            self._scene.command_stack.push(cmd)

    def _layer_move_down(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if idx > 0:
            from snapmock.commands.layer_commands import ReorderLayerCommand

            cmd = ReorderLayerCommand(lm, active.layer_id, idx - 1)
            self._scene.command_stack.push(cmd)

    def _layer_move_to_top(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if idx < lm.count - 1:
            from snapmock.commands.layer_commands import ReorderLayerCommand

            cmd = ReorderLayerCommand(lm, active.layer_id, lm.count - 1)
            self._scene.command_stack.push(cmd)

    def _layer_move_to_bottom(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if idx > 0:
            from snapmock.commands.layer_commands import ReorderLayerCommand

            cmd = ReorderLayerCommand(lm, active.layer_id, 0)
            self._scene.command_stack.push(cmd)

    # ---- context menu helpers ----

    def _move_items_to_layer(self, target_layer_id: str) -> None:
        """Move selected items to the specified layer."""
        items = self._selected_snap_items()
        if not items:
            return
        from snapmock.commands.move_item_layer import MoveItemToLayerCommand

        cmd = MoveItemToLayerCommand(self._scene, items, target_layer_id)
        self._scene.command_stack.push(cmd)

    def _toggle_item_lock(self) -> None:
        """Toggle the locked flag on all selected items."""
        items = self._selected_snap_items()
        if not items:
            return
        # Use the first item's state to determine the toggle direction
        new_locked = not items[0].locked
        for item in items:
            item.locked = new_locked

    def _layer_new_relative(self, reference_layer_id: str, *, above: bool) -> None:
        """Add a new layer above or below the referenced layer."""
        from snapmock.commands.layer_commands import AddLayerCommand

        lm = self._scene.layer_manager
        idx = lm.index_of(reference_layer_id)
        if idx < 0:
            return
        insert_idx = idx + 1 if above else idx
        name = f"Layer {lm.count + 1}"
        cmd = AddLayerCommand(lm, name, insert_idx)
        self._scene.command_stack.push(cmd)

    def _toggle_layer_lock(self, layer_id: str) -> None:
        """Toggle lock on a layer via undoable command."""
        from snapmock.commands.layer_commands import ChangeLayerPropertyCommand

        lm = self._scene.layer_manager
        layer = lm.layer_by_id(layer_id)
        if layer is None:
            return
        cmd = ChangeLayerPropertyCommand(lm, layer_id, "locked", layer.locked, not layer.locked)
        self._scene.command_stack.push(cmd)

    def _toggle_layer_visibility(self, layer_id: str) -> None:
        """Toggle visibility on a layer via undoable command."""
        from snapmock.commands.layer_commands import ChangeLayerPropertyCommand

        lm = self._scene.layer_manager
        layer = lm.layer_by_id(layer_id)
        if layer is None:
            return
        cmd = ChangeLayerPropertyCommand(lm, layer_id, "visible", layer.visible, not layer.visible)
        self._scene.command_stack.push(cmd)

    # ---- arrange operations ----

    def _selected_snap_items(self) -> list[SnapGraphicsItem]:
        return [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]

    def _arrange_bring_to_front(self) -> None:
        items = self._selected_snap_items()
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "front")
        self._scene.command_stack.push(cmd)

    def _arrange_bring_forward(self) -> None:
        items = self._selected_snap_items()
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "forward")
        self._scene.command_stack.push(cmd)

    def _arrange_send_backward(self) -> None:
        items = self._selected_snap_items()
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "backward")
        self._scene.command_stack.push(cmd)

    def _arrange_send_to_back(self) -> None:
        items = self._selected_snap_items()
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "back")
        self._scene.command_stack.push(cmd)

    def _arrange_align(self, alignment: str) -> None:
        items = self._selected_snap_items()
        if len(items) < 2:
            return
        from snapmock.commands.arrange_commands import AlignItemsCommand

        cmd = AlignItemsCommand(items, alignment)
        self._scene.command_stack.push(cmd)

    def _arrange_distribute(self, direction: str) -> None:
        items = self._selected_snap_items()
        if len(items) < 3:
            return
        from snapmock.commands.arrange_commands import DistributeItemsCommand

        cmd = DistributeItemsCommand(items, direction)
        self._scene.command_stack.push(cmd)

    def _arrange_align_canvas_center(self) -> None:
        items = self._selected_snap_items()
        if not items:
            return
        from snapmock.commands.arrange_commands import AlignToCanvasCommand

        cmd = AlignToCanvasCommand(self._scene, items)
        self._scene.command_stack.push(cmd)

    # ---- help operations ----

    def _help_welcome(self) -> None:
        QMessageBox.information(self, "Welcome", "Welcome dialog is coming soon.")

    def _help_docs(self) -> None:
        QDesktopServices.openUrl(QUrl("https://snapmock.org/docs"))

    def _help_shortcuts(self) -> None:
        QMessageBox.information(
            self, "Keyboard Shortcuts", "Keyboard shortcuts reference is coming soon."
        )

    def _help_report_bug(self) -> None:
        QDesktopServices.openUrl(QUrl("https://github.com/snapmock/snapmock/issues"))

    def _help_check_updates(self) -> None:
        QMessageBox.information(self, "Check for Updates", "Update checking is coming soon.")

    def _help_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
            "<p>An open-source multi-platform screenshot annotation &amp; UI mockup tool.</p>"
            "<p>Built with Python and PyQt6.</p>",
        )

    # ---- recent files ----

    def _add_recent_file(self, path: Path) -> None:
        recent = self._settings.recent_files()
        path_str = str(path.resolve())
        if path_str in recent:
            recent.remove(path_str)
        recent.insert(0, path_str)
        self._settings.set_recent_files(recent[:MAX_RECENT_FILES])
        self._update_recent_files_menu()

    def _update_recent_files_menu(self) -> None:
        if self._recent_menu is None:
            return
        self._recent_menu.clear()
        recent = self._settings.recent_files()
        if not recent:
            no_action = self._recent_menu.addAction("(No recent files)")
            if no_action is not None:
                no_action.setEnabled(False)
            return
        for path_str in recent:
            action = self._recent_menu.addAction(Path(path_str).name)
            if action is not None:
                action.triggered.connect(
                    lambda _checked=False, p=path_str: self._open_project(Path(p))
                )

    # ---- autosave ----

    def _autosave(self) -> None:
        """Autosave the current project if it has a file and is dirty."""
        if self._current_file is not None and self._scene.command_stack.is_dirty:
            try:
                save_project(self._scene, self._current_file)
            except Exception:  # noqa: BLE001
                pass  # Silent failure for autosave

    # ---- helpers ----

    def _confirm_discard(self) -> bool:
        """If the project has unsaved changes, ask the user to confirm discarding."""
        if not self._scene.command_stack.is_dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Do you want to discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Discard

    def _update_title(self) -> None:
        dirty = "*" if self._scene.command_stack.is_dirty else ""
        name = self._current_file.name if self._current_file else "Untitled"
        self.setWindowTitle(f"{dirty}{name} — {APP_NAME}")

    # ---- key event routing ----

    def _space_held(self) -> bool:
        """Whether Space is currently held for temporary pan."""
        return self._tool_manager._previous_tool_id is not None  # noqa: SLF001

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # noqa: N802
        if event is None:
            super().keyPressEvent(event)
            return
        # Space-bar temporary pan override
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat() and not self._space_held():
            active = self._tool_manager.active_tool
            if active is None or not active.is_active_operation:
                self._tool_manager.activate_temporary("pan")
                event.accept()
                return

        # Delegate to active tool
        if self._tool_manager.handle_key_press(event):
            event.accept()
            return

        # Arrow key viewport pan when no selection
        key = event.key()
        if key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            step = 100 if shift else 20
            h_bar = self._view.horizontalScrollBar()
            v_bar = self._view.verticalScrollBar()
            if key == Qt.Key.Key_Left and h_bar is not None:
                h_bar.setValue(h_bar.value() - step)
            elif key == Qt.Key.Key_Right and h_bar is not None:
                h_bar.setValue(h_bar.value() + step)
            elif key == Qt.Key.Key_Up and v_bar is not None:
                v_bar.setValue(v_bar.value() - step)
            elif key == Qt.Key.Key_Down and v_bar is not None:
                v_bar.setValue(v_bar.value() + step)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            super().keyReleaseEvent(event)
            return
        # Space-bar release → restore previous tool
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat() and self._space_held():
            self._tool_manager.restore_previous()
            event.accept()
            return

        # Delegate to active tool
        if self._tool_manager.handle_key_release(event):
            event.accept()
            return

        super().keyReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Save window geometry and state on close."""
        self._settings.save_window_geometry(self.saveGeometry().data())
        self._settings.save_window_state(self.saveState().data())
        super().closeEvent(event)

    # ---- properties ----

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

    @property
    def clipboard(self) -> ClipboardManager:
        return self._clipboard
