"""MainWindow — primary application window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QKeyEvent,
    QKeySequence,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressDialog,
    QSystemTrayIcon,
    QToolButton,
)

if TYPE_CHECKING:
    from datetime import datetime

    from PyQt6.QtWidgets import QGraphicsItem

from snapmock.capture.manager import CaptureManager
from snapmock.capture.models import (
    HOTKEY_ACTION_FULL_SCREEN,
    HOTKEY_ACTION_REGION,
    HOTKEY_ACTION_WINDOW,
    ORIGIN_COMMAND_LINE,
    ORIGIN_MENU,
    ORIGIN_TOOLBAR,
    ORIGIN_TRAY,
    CaptureMetadata,
    CaptureMode,
    CaptureRequest,
    CaptureResult,
)
from snapmock.capture.tray import make_tray_icon
from snapmock.config.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    PROJECT_EXTENSION,
    SNAGIT_EXTENSION,
    ZOOM_MAX,
    ZOOM_MIN,
)
from snapmock.config.settings import AppSettings
from snapmock.config.shortcuts import SHORTCUTS
from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.document import Document
from snapmock.core.document_manager import DocumentManager
from snapmock.core.layer import Layer
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.io.exporter import export_jpg, export_pdf, export_png, export_svg
from snapmock.io.importer import import_image
from snapmock.io.project_serializer import (
    load_project,
    read_capture_metadata,
    read_library_metadata,
    save_project,
)
from snapmock.io.snagit_reader import load_snagx
from snapmock.io.snagit_writer import save_snagx
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.library.manager import LibraryManager
from snapmock.library.render import export_files_to_png
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
from snapmock.ui.document_tabs import DocumentTabs
from snapmock.ui.layer_panel import LayerPanel
from snapmock.ui.library_panel import LibraryPanel
from snapmock.ui.property_panel import PropertyPanel
from snapmock.ui.status_bar import SnapStatusBar
from snapmock.ui.toast import Toast
from snapmock.ui.tool_options_bar import ToolOptionsBar
from snapmock.ui.toolbar import SnapToolBar
from snapmock.ui.unmet_requirements import check_requirements, show_not_available

MAX_RECENT_FILES = 10
DELAY_CHOICES = (0, 3, 5, 10)
MODE_LABELS = {
    CaptureMode.REGION: "Capture &Region",
    CaptureMode.ACTIVE_WINDOW: "Capture Active &Window",
    CaptureMode.FULL_SCREEN: "Capture &Full Screen",
}
MODE_ACTIONS = {
    CaptureMode.REGION: HOTKEY_ACTION_REGION,
    CaptureMode.ACTIVE_WINDOW: HOTKEY_ACTION_WINDOW,
    CaptureMode.FULL_SCREEN: HOTKEY_ACTION_FULL_SCREEN,
}
TRAY_UNAVAILABLE_MESSAGE = (
    "This desktop does not provide a system tray. Global hotkeys and the Capture menu still work."
)


_extra_windows: list[MainWindow] = []


def create_capture_manager(settings: AppSettings) -> CaptureManager:
    """Build the process-wide CaptureManager from the platform backends (PRD 6.2)."""
    from snapmock.capture import select_backends

    backend, hotkeys = select_backends()
    return CaptureManager(backend, hotkeys, settings)


class MainWindow(QMainWindow):
    """Primary application window.

    Owns the DocumentManager (one Document per open tab, each with its own
    SnapScene, SnapView, SelectionManager and ClipboardManager), the shared
    ToolManager, and the UI panels.  ``_scene``, ``_view``,
    ``_selection_manager`` and ``_clipboard`` always refer to the active tab.
    """

    def __init__(
        self,
        *,
        restore_session: bool = False,
        capture_manager: CaptureManager | None = None,
        primary_capture: bool = True,
    ) -> None:
        super().__init__()
        self._settings = AppSettings()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        # Screen capture (Screen Capture PRD): one manager per process. Only the
        # primary window connects its results, owns the tray icon, and quits.
        self._capture = capture_manager or create_capture_manager(self._settings)
        self._primary_capture = primary_capture
        self._tray: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._hidden_in_tray = False
        self._quit_requested = False
        self._pending_capture_clipboard = False
        self._capture_mode_actions: dict[CaptureMode, QAction] = {}
        self._toolbar_mode_actions: dict[CaptureMode, QAction] = {}
        self._delay_groups: list[QActionGroup] = []
        self._capture_toggle_actions: list[tuple[str, QAction]] = []
        self._capture_button: QToolButton | None = None

        # Library: auto-saved capture workspace (Library PRD)
        self._library = LibraryManager(self._settings.library_directory(), parent=self)

        # Documents (tabs): each owns a scene, view, selection and clipboard.
        # There is always at least one document open.
        self._documents = DocumentManager(self)
        self._wired_docs: set[str] = set()
        first = Document(SnapScene(), parent=self)
        self._documents.add(first)

        # The tool manager is shared and rebound to the active document.
        self._tool_manager = ToolManager(first.scene, first.selection_manager, parent=self)
        self._register_tools()
        self._tool_manager.activate("select")

        self._tabs = DocumentTabs(self._documents, self)
        self.setCentralWidget(self._tabs)

        # UI panels
        self._toolbar = SnapToolBar(self._tool_manager, self)
        self.addToolBar(self._toolbar)

        self._tool_options = ToolOptionsBar(self._tool_manager, self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._tool_options)

        self._layer_panel = LayerPanel(self._scene.layer_manager, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._layer_panel)

        self._property_panel = PropertyPanel(self._selection_manager, self._scene, self)
        self._property_panel.set_tool_manager(self._tool_manager)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._property_panel)

        self._library_panel = LibraryPanel(self._library, self._settings, self)
        self._library_panel.set_is_open_provider(
            lambda p: self._documents.find_by_path(p) is not None
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._library_panel)
        self._library_panel.open_requested.connect(self._open_library_files)
        self._library_panel.open_in_new_window_requested.connect(self._open_in_new_window)
        self._library_panel.files_about_to_be_deleted.connect(self._close_documents_for_paths)
        self._library_panel.export_requested.connect(self._export_library_files)
        self._library_panel.export_quick_requested.connect(self._export_library_files_quick)
        self._library_panel.new_canvas_requested.connect(self._library_new_canvas)
        self._library.file_created.connect(self._on_library_file_created)
        self._documents.document_added.connect(lambda _d: self._library_panel.refresh_open_state())
        self._documents.document_removed.connect(
            lambda _d: self._library_panel.refresh_open_state()
        )
        self._toast = Toast(self)
        self._setup_capture_toolbar()

        # Style the dock splitter so it's easier to grab
        self.setStyleSheet(
            "QMainWindow::separator {"
            "  width: 6px;"
            "  height: 6px;"
            "  background: #c0c0c0;"
            "  border: 1px solid #a0a0a0;"
            "}"
            "QMainWindow::separator:hover {"
            "  background: #a0a0a0;"
            "}"
        )

        self._status_bar = SnapStatusBar(self._view)
        self.setStatusBar(self._status_bar)
        self._configure_view(first.view)

        # Wire tool hint to status bar
        self._tool_manager.tool_changed.connect(self._on_tool_changed_for_hint)

        # Document / tab signals
        self._documents.active_changed.connect(self._on_active_document_changed)
        self._documents.document_title_changed.connect(lambda _d: self._update_title())
        self._tabs.close_requested.connect(self._close_document)
        self._tabs.close_others_requested.connect(self._close_other_documents)
        self._tabs.close_all_requested.connect(self._close_all_documents)
        self._tabs.close_right_requested.connect(self._close_documents_to_right)
        self._tabs.reveal_in_file_manager_requested.connect(self._reveal_document_in_file_manager)
        self._tabs.reveal_in_library_requested.connect(self._reveal_document_in_library)

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
        self._flip_h_action: QAction | None = None
        self._flip_v_action: QAction | None = None
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

        # Per-document signal wiring (title, layer state, menu state)
        self._wire_document(first)

        # Restore window geometry
        geo = self._settings.window_geometry()
        if geo is not None:
            self.restoreGeometry(geo)
        state = self._settings.window_state()
        if state is not None:
            self.restoreState(state)
        self.resizeDocks([self._library_panel], [250], Qt.Orientation.Vertical)

        # Size the layer panel: auto-fit to the number of layers (capped at 10 rows).
        layer_h = self._layer_panel.preferred_height()
        self.resizeDocks(
            [self._layer_panel],
            [layer_h],
            Qt.Orientation.Vertical,
        )

        self._update_title()

        if self._primary_capture:
            self._capture.set_onboarding_gate(self._capture_onboarding_gate)
            self._capture.capture_completed.connect(self._on_capture_completed)
            self._capture.capture_failed.connect(self._on_capture_failed)
            self._capture.capture_refused.connect(self._on_capture_refused)
            self._capture.countdown_tick.connect(self._on_capture_countdown)
            self._capture.hotkeys_changed.connect(self._sync_capture_shortcuts)
            self._setup_tray()

        if restore_session:
            self._restore_session()

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
        self._setup_library_menu(menu_bar)
        self._setup_capture_menu(menu_bar)
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

        close_action = file_menu.addAction("&Close")
        if close_action is not None:
            close_action.setShortcut(QKeySequence(SHORTCUTS["file.close_tab"]))
            close_action.triggered.connect(self._file_close_tab)

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
            redo_action.triggered.connect(self._edit_redo)

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
            deselect_action.triggered.connect(self._edit_deselect)

    def _setup_view_menu(self, menu_bar: QMenuBar) -> None:
        view_menu = menu_bar.addMenu("&View")
        if view_menu is None:
            return

        zoom_in = view_menu.addAction("Zoom &In")
        if zoom_in is not None:
            zoom_in.setShortcut(QKeySequence(SHORTCUTS["view.zoom_in"]))
            zoom_in.triggered.connect(self._view_zoom_in)

        zoom_out = view_menu.addAction("Zoom &Out")
        if zoom_out is not None:
            zoom_out.setShortcut(QKeySequence(SHORTCUTS["view.zoom_out"]))
            zoom_out.triggered.connect(self._view_zoom_out)

        fit_action = view_menu.addAction("&Fit to Window")
        if fit_action is not None:
            fit_action.setShortcut(QKeySequence(SHORTCUTS["view.fit_window"]))
            fit_action.triggered.connect(lambda: self._view.fit_in_view_all())

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

        library_toggle = self._library_panel.toggleViewAction()
        if library_toggle is not None:
            view_menu.addAction(library_toggle)

        view_menu.addSeparator()

        next_tab = view_menu.addAction("&Next Tab")
        if next_tab is not None:
            next_tab.setShortcut(QKeySequence(SHORTCUTS["view.next_tab"]))
            next_tab.triggered.connect(self._documents.activate_next)

        prev_tab = view_menu.addAction("Pre&vious Tab")
        if prev_tab is not None:
            prev_tab.setShortcut(QKeySequence(SHORTCUTS["view.previous_tab"]))
            prev_tab.triggered.connect(self._documents.activate_previous)

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

        self._flip_h_action = QAction("Flip &Horizontal", self)
        self._flip_h_action.triggered.connect(self._arrange_flip_horizontal)
        arrange_menu.addAction(self._flip_h_action)

        self._flip_v_action = QAction("Flip &Vertical", self)
        self._flip_v_action.triggered.connect(self._arrange_flip_vertical)
        arrange_menu.addAction(self._flip_v_action)

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

    def _setup_library_menu(self, menu_bar: QMenuBar) -> None:
        """Library menu (Library PRD Section 5)."""
        library_menu = menu_bar.addMenu("Li&brary")
        if library_menu is None:
            return

        self._library_toggle_action = self._library_panel.toggleViewAction()
        if self._library_toggle_action is not None:
            self._library_toggle_action.setText("Show &Library Panel")
            self._library_toggle_action.setShortcut(
                QKeySequence(SHORTCUTS["library.toggle_panel"])
            )
            library_menu.addAction(self._library_toggle_action)

        library_menu.addSeparator()

        open_lib = library_menu.addAction("&Open Library...")
        if open_lib is not None:
            open_lib.triggered.connect(self._library_panel.choose_library_directory)

        move_lib = library_menu.addAction("&Move Library...")
        if move_lib is not None:
            move_lib.triggered.connect(self._library_move)

        library_menu.addSeparator()

        new_folder = library_menu.addAction("New &Folder")
        if new_folder is not None:
            new_folder.triggered.connect(self._library_panel.create_folder)

        new_canvas = library_menu.addAction("New &Canvas")
        if new_canvas is not None:
            new_canvas.triggered.connect(
                lambda: self._library_new_canvas(self._library_panel.current_path)
            )

        library_menu.addSeparator()

        reveal = library_menu.addAction("&Reveal in File Manager")
        if reveal is not None:
            reveal.triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._library.root)))
            )

        library_menu.addSeparator()

        prefs = library_menu.addAction("Library &Preferences...")
        if prefs is not None:
            prefs.triggered.connect(lambda: self._file_preferences(focus_library=True))

    # ---- capture (Screen Capture PRD 3.2 to 3.4, 7) ----

    def _setup_capture_menu(self, menu_bar: QMenuBar) -> None:
        """Capture menu after Library and before Help (PRD 3.4)."""
        capture_menu = menu_bar.addMenu("&Capture")
        if capture_menu is None:
            return
        self._capture_menu = capture_menu
        for mode in (CaptureMode.REGION, CaptureMode.ACTIVE_WINDOW, CaptureMode.FULL_SCREEN):
            action = QAction(MODE_LABELS[mode], self)
            action.triggered.connect(
                lambda _checked=False, m=mode: self._start_capture(m, ORIGIN_MENU)
            )
            capture_menu.addAction(action)
            self._capture_mode_actions[mode] = action
        capture_menu.addSeparator()
        capture_menu.addMenu(self._build_delay_menu(capture_menu))
        self._add_capture_toggle(
            capture_menu,
            "Include Mouse &Cursor",
            "include_cursor",
            self._settings.capture_include_cursor,
            self._settings.set_capture_include_cursor,
        )
        self._add_capture_toggle(
            capture_menu,
            "Copy to Clip&board",
            "copy_to_clipboard",
            self._settings.capture_copy_to_clipboard,
            self._settings.set_capture_copy_to_clipboard,
        )
        self._add_capture_toggle(
            capture_menu,
            "&Hide SnapMock During Capture",
            "hide_window",
            self._settings.capture_hide_window,
            self._settings.set_capture_hide_window,
        )
        capture_menu.addSeparator()
        prefs = capture_menu.addAction("Capture &Preferences...")
        if prefs is not None:
            prefs.triggered.connect(lambda: self._file_preferences(focus_capture=True))
        self._sync_capture_shortcuts()

    def _build_delay_menu(self, parent: QMenu) -> QMenu:
        """Delay: None / 3 s / 5 s / 10 s radio submenu bound to the preference (PRD 3.2)."""
        menu = QMenu("&Delay", parent)
        group = QActionGroup(menu)
        group.setExclusive(True)
        current = self._settings.capture_delay_seconds()
        for seconds in DELAY_CHOICES:
            label = "&None" if seconds == 0 else f"&{seconds} seconds"
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setData(seconds)
            action.setChecked(seconds == current)
            action.triggered.connect(lambda _c=False, s=seconds: self._set_capture_delay(s))
            group.addAction(action)
            menu.addAction(action)
        self._delay_groups.append(group)
        return menu

    def _set_capture_delay(self, seconds: int) -> None:
        self._settings.set_capture_delay_seconds(seconds)
        self._sync_capture_toggles()

    def _add_capture_toggle(
        self,
        menu: QMenu,
        label: str,
        key: str,
        getter: Callable[[], bool],
        setter: Callable[[bool], None],
    ) -> QAction:
        action = QAction(label, menu)
        action.setCheckable(True)
        action.setChecked(getter())
        action.toggled.connect(lambda checked: self._on_capture_toggle(setter, checked))
        menu.addAction(action)
        self._capture_toggle_actions.append((key, action))
        return action

    def _on_capture_toggle(self, setter: Callable[[bool], None], checked: bool) -> None:
        setter(checked)
        self._sync_capture_toggles()

    def _sync_capture_toggles(self) -> None:
        """Reflect the delay and checkbox preferences in every menu that shows them."""
        getters: dict[str, Callable[[], bool]] = {
            "include_cursor": self._settings.capture_include_cursor,
            "copy_to_clipboard": self._settings.capture_copy_to_clipboard,
            "hide_window": self._settings.capture_hide_window,
        }
        for key, action in self._capture_toggle_actions:
            value = getters[key]()
            if action.isChecked() != value:
                action.blockSignals(True)
                action.setChecked(value)
                action.blockSignals(False)
        delay = self._settings.capture_delay_seconds()
        for group in self._delay_groups:
            for action in group.actions():
                action.setChecked(action.data() == delay)

    def _sync_capture_shortcuts(self) -> None:
        """Menu shortcuts and the toolbar tooltip follow the hotkey preferences (PRD 3.4)."""
        for mode, action in self._capture_mode_actions.items():
            binding = self._capture.binding(MODE_ACTIONS[mode])
            action.setShortcut(binding.key_sequence if binding else QKeySequence())
        for mode, action in self._toolbar_mode_actions.items():
            binding = self._capture.binding(MODE_ACTIONS[mode])
            action.setShortcut(QKeySequence())  # toolbar copies never own the shortcut
            action.setText(
                MODE_LABELS[mode].replace("&", "")
                + (f"\t{binding.display_text}" if binding and binding.is_bound else "")
            )
        if self._capture_button is not None:
            default_mode = CaptureMode.from_string(self._settings.capture_default_mode())
            binding = self._capture.binding(MODE_ACTIONS[default_mode])
            key = binding.display_text if binding and binding.is_bound else ""
            self._capture_button.setToolTip(f"Capture ({key})" if key else "Capture")

    def _setup_capture_toolbar(self) -> None:
        """Group 0 Capture: a menu-button control at the left end (PRD 3.3)."""
        button = QToolButton()
        button.setText("Capture")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        button.clicked.connect(lambda: self._start_capture(None, ORIGIN_TOOLBAR))
        menu = QMenu(button)
        for mode in (CaptureMode.REGION, CaptureMode.ACTIVE_WINDOW, CaptureMode.FULL_SCREEN):
            action = QAction(MODE_LABELS[mode], menu)
            action.triggered.connect(
                lambda _checked=False, m=mode: self._start_capture(m, ORIGIN_TOOLBAR)
            )
            menu.addAction(action)
            self._toolbar_mode_actions[mode] = action
        menu.addSeparator()
        menu.addMenu(self._build_delay_menu(menu))
        button.setMenu(menu)
        self._capture_button = button
        self._toolbar.set_capture_button(button)
        self._sync_capture_shortcuts()

    def _setup_tray(self) -> None:
        """The system tray icon and menu (PRD 3.2); created only when available."""
        if not self._settings.capture_tray_enabled():
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(make_tray_icon(), self)
        tray.setToolTip(APP_NAME)
        menu = QMenu(self)
        for mode in (CaptureMode.REGION, CaptureMode.ACTIVE_WINDOW, CaptureMode.FULL_SCREEN):
            action = QAction(MODE_LABELS[mode], menu)
            action.triggered.connect(
                lambda _checked=False, m=mode: self._start_capture(m, ORIGIN_TRAY)
            )
            menu.addAction(action)
        menu.addSeparator()
        menu.addMenu(self._build_delay_menu(menu))
        self._add_capture_toggle(
            menu,
            "Include Mouse &Cursor",
            "include_cursor",
            self._settings.capture_include_cursor,
            self._settings.set_capture_include_cursor,
        )
        self._add_capture_toggle(
            menu,
            "Copy to Clip&board",
            "copy_to_clipboard",
            self._settings.capture_copy_to_clipboard,
            self._settings.set_capture_copy_to_clipboard,
        )
        menu.addSeparator()
        show = menu.addAction("&Show SnapMock")
        if show is not None:
            show.triggered.connect(self.show_from_tray)
        prefs = menu.addAction("&Preferences...")
        if prefs is not None:
            prefs.triggered.connect(lambda: self._file_preferences(focus_capture=True))
        menu.addSeparator()
        quit_action = menu.addAction("&Quit SnapMock")
        if quit_action is not None:
            quit_action.triggered.connect(self.quit_application)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.messageClicked.connect(self.show_from_tray)
        tray.show()
        self._tray = tray
        self._tray_menu = menu
        self._apply_quit_policy()

    def _teardown_tray(self) -> None:
        if self._tray is not None:
            self._tray.hide()
            self._tray.deleteLater()
            self._tray = None
        if self._tray_menu is not None:
            self._capture_toggle_actions = [
                (k, a)
                for k, a in self._capture_toggle_actions
                if a.parent() is not self._tray_menu
            ]
            self._delay_groups = [
                g for g in self._delay_groups if g.parent() is not self._tray_menu
            ]
            self._tray_menu.deleteLater()
            self._tray_menu = None
        self._apply_quit_policy()

    def _apply_quit_policy(self) -> None:
        """Keep the process alive without windows only while the tray keeps it running."""
        keep = self._tray is not None and self._settings.capture_keep_running_in_tray()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setQuitOnLastWindowClosed(not keep)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and self._capture.platform != (
            "darwin"
        ):
            self.show_from_tray()

    def show_from_tray(self) -> None:
        """Show, restore, and activate the main window (tray: Show SnapMock)."""
        self._hidden_in_tray = False
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_application(self) -> None:
        """Quit from the tray, prompting for unsaved non-library documents."""
        self._quit_requested = True
        if not self.isVisible():
            self.show()
        self.close()
        if self.isVisible():
            self._quit_requested = False  # the user cancelled the close prompt

    @property
    def hidden_in_tray(self) -> bool:
        return self._hidden_in_tray

    @property
    def tray_icon(self) -> QSystemTrayIcon | None:
        return self._tray

    def _capture_onboarding_gate(self, request: CaptureRequest) -> bool:
        """First-run onboarding on platforms that need setup (PRD 9). Runs once."""
        backend = self._capture.backend
        if backend.name == "macos" and self._capture.capabilities.needs_permission:
            return self._macos_permission_gate()
        if self._settings.capture_onboarding_shown():
            return True
        if backend.name != "wayland_portal":
            return True
        from snapmock.capture.onboarding import WaylandOnboardingDialog

        dlg = WaylandOnboardingDialog(self if self.isVisible() else None)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        if dlg.dont_show.isChecked():
            self._settings.set_capture_onboarding_shown(True)
        dlg.deleteLater()
        return accepted

    def _macos_permission_gate(self) -> bool:
        """Screen Recording onboarding (PRD 9.1): preflight, then the dialog if not granted."""
        from snapmock.capture.models import PermissionState
        from snapmock.capture.onboarding import MacOSPermissionDialog

        backend = self._capture.backend
        if backend.request_permission() is PermissionState.GRANTED:
            return True
        if self._settings.capture_onboarding_shown():
            return True  # the capture then fails with the Section 6.5 message
        dlg = MacOSPermissionDialog(
            lambda: backend.request_permission() is PermissionState.GRANTED,
            settings_url=str(getattr(backend, "settings_url", "")),
            parent=self if self.isVisible() else None,
        )
        dlg.exec()
        if dlg.dont_show.isChecked():
            self._settings.set_capture_onboarding_shown(True)
        granted, quit_requested = dlg.granted, dlg.quit_requested
        dlg.deleteLater()
        if quit_requested:
            QTimer.singleShot(0, self.quit_application)
        return granted

    def _start_capture(self, mode: CaptureMode | None, origin: str) -> None:
        self._capture.start(self._capture.request_from_settings(mode, origin))

    def _on_capture_completed(self, result: CaptureResult) -> None:
        """Hand the image to the Library (PRD 7.1). The manager restores windows after this."""
        self._pending_capture_clipboard = self._settings.capture_copy_to_clipboard()
        try:
            self.add_to_library(
                result.image,
                source="capture",
                capture_metadata=result.metadata,
                when=result.taken_at,
            )
        finally:
            self._pending_capture_clipboard = False

    def _on_capture_failed(self, reason: str) -> None:
        self._notify("Capture failed", reason)

    def _on_capture_refused(self, reason: str, origin: str) -> None:
        self._notify(
            "Capture", reason, force_notification=origin in (ORIGIN_TRAY, ORIGIN_COMMAND_LINE)
        )

    def _on_capture_countdown(self, remaining: int) -> None:
        if self._tray is not None:
            self._tray.setToolTip(
                f"{APP_NAME}: capturing in {remaining} s" if remaining > 0 else APP_NAME
            )

    def _notify(self, title: str, text: str, *, force_notification: bool = False) -> None:
        """A toast in the window, or a system notification while it is in the tray (PRD 7.4).

        The window may be hidden for the grab when this runs; the manager
        restores it right after, so the toast is still the right channel then.
        """
        if not self._hidden_in_tray:
            self._toast.show_message(text)
        if self._tray is not None and (force_notification or self._hidden_in_tray):
            self._tray.showMessage(title, text)

    def report_hotkey_failures(self) -> None:
        """One toast naming every hotkey the desktop refused (PRD 9.3)."""
        failed = [b for b in self._capture.bindings if b.is_bound and not b.registered]
        if not failed or not self._capture.hotkey_backend.supported:
            return
        keys = ", ".join(b.display_text for b in failed)
        verb = "is" if len(failed) == 1 else "are"
        self._notify(
            "Capture hotkeys",
            f"{keys} {verb} in use by another application. Change it in Preferences > Capture.",
        )

    @property
    def capture_manager(self) -> CaptureManager:
        return self._capture

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

    # ---- never-disabled controls (General UI PRD 1.3) ----

    def _require(self, action: str, *requirements: tuple[bool, str]) -> bool:
        """Show the unmet-requirement message and return False unless every requirement holds."""
        return check_requirements(self, action, list(requirements))

    def _require_selection(self, action: str, minimum: int = 1) -> list[SnapGraphicsItem]:
        """The selected items, or an empty list after the message when fewer than *minimum*."""
        items = self._selected_snap_items()
        words = {1: "at least one item selected", 2: "at least two items selected"}
        need = words.get(minimum, f"at least {minimum} items selected")
        if not self._require(action, (len(items) >= minimum, need)):
            return []
        return items

    def _require_active_layer(self, action: str) -> Layer | None:
        active = self._scene.layer_manager.active_layer
        if not self._require(action, (active is not None, "an active layer")):
            return None
        return active

    def _clipboard_has_content(self) -> bool:
        if self._clipboard.has_internal or self._clipboard.has_raster:
            return True
        cb = QApplication.clipboard()
        if cb is None:
            return False
        mime = cb.mimeData()
        return mime is not None and (mime.hasImage() or bool(cb.text()))

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

    def _view_zoom_in(self) -> None:
        if self._require(
            "Zoom In", (self._view.zoom_percent < ZOOM_MAX, f"a zoom below {ZOOM_MAX}%")
        ):
            self._view.zoom_in()

    def _view_zoom_out(self) -> None:
        if self._require(
            "Zoom Out", (self._view.zoom_percent > ZOOM_MIN, f"a zoom above {ZOOM_MIN}%")
        ):
            self._view.zoom_out()

    def _view_zoom_to_selection(self) -> None:
        """Zoom to fit the current selection in the viewport."""
        items = self._require_selection("Zoom to Selection")
        if not items:
            return
        rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        pad = 20
        self._view.zoom_to_rect(rect.adjusted(-pad, -pad, pad, pad))

    # ---- file operations ----

    def _file_new(self) -> None:
        """Open a new, empty, unsaved document in a new tab."""
        self._add_document(Document(SnapScene(), parent=self))

    def _file_open(self) -> None:
        """Open an existing .smk or .snagx project in a new tab."""
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

    def _open_project(self, path: Path) -> Document | None:
        """Open *path* in a new tab, or activate its tab if already open."""
        existing = self._documents.find_by_path(path)
        if existing is not None:
            self._documents.set_active(existing)
            return existing
        try:
            if path.suffix.lower() == SNAGIT_EXTENSION:
                scene = load_snagx(path)
                metadata = None
                capture_metadata = None
            else:
                scene = load_project(path)
                metadata = read_library_metadata(path)
                capture_metadata = read_capture_metadata(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Open Error", f"Could not open project:\n{e}")
            return None
        is_library = self._library.is_library_path(path)
        doc = Document(
            scene,
            file_path=path,
            is_library_file=is_library,
            display_name=(metadata or {}).get("display_name"),
            library_metadata=metadata,
            capture_metadata=capture_metadata,
            parent=self,
        )
        self._add_document(doc)
        if is_library:
            self._library.attach_document(doc)
        else:
            self._add_recent_file(path)
        return doc

    def _file_save(self) -> None:
        """Save the current project (library files are written back immediately)."""
        doc = self._active_document
        if doc.is_library_file:
            self._library.write_back(doc)
            return
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
            f"SnapMock Projects (*{PROJECT_EXTENSION});;Snagit Files (*{SNAGIT_EXTENSION})",
        )
        if not path_str:
            return
        path = Path(path_str)
        if SNAGIT_EXTENSION in selected_filter or path.suffix.lower() == SNAGIT_EXTENSION:
            if path.suffix.lower() != SNAGIT_EXTENSION:
                path = path.with_suffix(SNAGIT_EXTENSION)
        elif path.suffix.lower() != PROJECT_EXTENSION:
            path = path.with_suffix(PROJECT_EXTENSION)
        doc = self._active_document
        if doc.is_library_file and not self._library.is_library_path(path):
            # Library files stay bound to the library; Save As writes a copy.
            self._save_copy_to(path)
            return
        self._save_to(path)

    def _save_copy_to(self, path: Path) -> None:
        try:
            if path.suffix.lower() == SNAGIT_EXTENSION:
                save_snagx(self._scene, path)
            else:
                save_project(self._scene, path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save Error", f"Could not save copy:\n{e}")
            return
        self._add_recent_file(path)
        self._status_bar.set_hint(f"Saved copy to {path.name}")

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
        doc = self._active_document
        doc.file_path = path
        doc.display_name = None
        if self._library.is_library_path(path):
            doc.is_library_file = True
            self._library.attach_document(doc)
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
        if self._current_file is not None and not self._active_document.is_library_file:
            path = self._current_file.with_suffix(".png")
        else:
            path_str, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG Image (*.png)")
            if not path_str:
                return
            path = Path(path_str)
        export_png(self._scene, path)

    def _file_print(self) -> None:
        QMessageBox.information(self, "Print", "Print support is coming soon.")

    def _file_preferences(
        self, *, focus_library: bool = False, focus_capture: bool = False
    ) -> None:
        from snapmock.ui.preferences_dialog import PreferencesDialog

        dlg = PreferencesDialog(self._settings, self, capture=self._capture)
        if focus_library:
            dlg.focus_library_section()
        if focus_capture:
            dlg.focus_capture_section()
        if dlg.exec() == PreferencesDialog.DialogCode.Accepted:
            self._apply_preference_changes(dlg.get_changes())

    def _apply_preference_changes(self, changes: dict[str, tuple[object, object]]) -> None:
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

        # Library preferences (Library PRD 8.1) take effect immediately
        if "library_directory" in changes:
            new_dir = Path(str(changes["library_directory"][1])).expanduser()
            self._library_panel.set_library_directory(new_dir)
        if "library_auto_open" in changes:
            self._settings.set_library_auto_open(bool(changes["library_auto_open"][1]))
        if "library_toast_enabled" in changes:
            self._settings.set_library_toast_enabled(bool(changes["library_toast_enabled"][1]))
        if "library_default_view_mode" in changes:
            mode = str(changes["library_default_view_mode"][1])
            self._settings.set_library_default_view_mode(mode)
            self._library_panel.set_view_mode(mode)
        if "library_default_thumbnail_size" in changes:
            size = _int(changes["library_default_thumbnail_size"][1])
            self._settings.set_library_default_thumbnail_size(size)
            self._settings.set_library_thumbnail_size(size)
            self._library_panel.set_view_mode(self._library_panel.view_mode)
        if "library_default_sort" in changes:
            sort_id = str(changes["library_default_sort"][1])
            self._settings.set_library_default_sort(sort_id)
            self._library_panel.set_sort_id(sort_id)

        self._apply_capture_preference_changes(changes)

    def _apply_capture_preference_changes(self, changes: dict[str, tuple[object, object]]) -> None:
        """Capture preferences (Screen Capture PRD 8.1) take effect immediately."""

        def _int(val: object) -> int:
            return val if isinstance(val, int) else int(str(val))

        s = self._settings
        if "capture_default_mode" in changes:
            s.set_capture_default_mode(str(changes["capture_default_mode"][1]))
        if "capture_delay_seconds" in changes:
            s.set_capture_delay_seconds(_int(changes["capture_delay_seconds"][1]))
        if "capture_include_cursor" in changes:
            s.set_capture_include_cursor(bool(changes["capture_include_cursor"][1]))
        if "capture_play_sound" in changes:
            s.set_capture_play_sound(bool(changes["capture_play_sound"][1]))
        if "capture_hide_window" in changes:
            s.set_capture_hide_window(bool(changes["capture_hide_window"][1]))
        if "capture_copy_to_clipboard" in changes:
            s.set_capture_copy_to_clipboard(bool(changes["capture_copy_to_clipboard"][1]))
        if "capture_full_screen_scope" in changes:
            s.set_capture_full_screen_scope(str(changes["capture_full_screen_scope"][1]))
        if "capture_show_magnifier" in changes:
            s.set_capture_show_magnifier(bool(changes["capture_show_magnifier"][1]))
        if "capture_keep_running_in_tray" in changes:
            s.set_capture_keep_running_in_tray(bool(changes["capture_keep_running_in_tray"][1]))
        if "capture_tray_enabled" in changes:
            enabled = bool(changes["capture_tray_enabled"][1])
            s.set_capture_tray_enabled(enabled)
            if self._primary_capture:
                if enabled and self._tray is None:
                    self._setup_tray()
                    if self._tray is None:
                        self._toast.show_message(TRAY_UNAVAILABLE_MESSAGE)
                elif not enabled and self._tray is not None:
                    self._teardown_tray()
        self._apply_quit_policy()
        self._sync_capture_toggles()
        self._sync_capture_shortcuts()

    # ---- library ----

    def _open_library_files(self, paths: list[Path]) -> None:
        for p in paths:
            self._open_project(p)

    def _open_in_new_window(self, path: Path) -> None:
        window = MainWindow(capture_manager=self._capture, primary_capture=False)
        window.show()
        window._open_project(path)  # noqa: SLF001
        _extra_windows.append(window)

    def _close_documents_for_paths(self, paths: list[Path]) -> None:
        """Close tabs for library files that are about to be deleted (no prompt)."""
        for p in paths:
            doc = self._documents.find_by_path(p)
            if doc is None:
                continue
            self._library.detach_document(doc)
            if self._documents.count == 1:
                self._documents.add(Document(SnapScene(), parent=self))
                self._configure_view(self._active_document.view)
                self._wire_document(self._active_document)
            self._documents.remove(doc)
            self._wired_docs.discard(doc.tab_id)
            doc.dispose()

    def _library_new_canvas(self, folder: Path) -> None:
        path = self._library.create_blank(
            DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT, folder=folder
        )
        self._open_project(path)

    def add_to_library(
        self,
        image: object,
        *,
        source: str = "capture",
        capture_metadata: CaptureMetadata | None = None,
        when: datetime | None = None,
    ) -> Path | None:
        """Store *image* (QImage or QPixmap) as a new library file (Library PRD 6.1).

        Opens it in a tab when the Auto-open preference is on. Screen capture
        passes *capture_metadata* (written to the manifest, Screen Capture PRD
        12.1) and *when*, the grab time, which becomes ``captured_at``.
        """
        from PyQt6.QtGui import QImage, QPixmap

        if not isinstance(image, (QImage, QPixmap)):
            return None
        path = self._library.create_from_image(
            image,
            source=source,
            folder=self._library_panel.current_path,
            when=when,
            capture_metadata=capture_metadata.to_dict() if capture_metadata else None,
        )
        if self._settings.library_auto_open():
            self._open_project(path)
        return path

    def _on_library_file_created(self, path: Path) -> None:
        if not self._settings.library_toast_enabled():
            return
        where = "Library and clipboard" if self._pending_capture_clipboard else "Library"
        text = f"Captured to {where}: {path.stem}"
        if self._hidden_in_tray and self._tray is not None:
            # No window to show a toast in: a system notification instead (PRD 7.2).
            self._tray.showMessage(APP_NAME, text)
            return
        self._toast.show_message(text, "Open", lambda: self._open_library_files([path]))

    def _export_library_files(self, paths: list[Path]) -> None:
        """Export one file via the Export dialog, or many into a directory."""
        if len(paths) == 1:
            doc = self._open_project(paths[0])
            if doc is not None:
                self._file_export()
            return
        out = QFileDialog.getExistingDirectory(self, "Export To Directory", str(Path.home()))
        if not out:
            return
        self._export_paths_as_png(paths, Path(out))

    def _export_library_files_quick(self, paths: list[Path]) -> None:
        out = QFileDialog.getExistingDirectory(self, "Export PNGs To", str(Path.home()))
        if not out:
            return
        self._export_paths_as_png(paths, Path(out))

    def _export_paths_as_png(self, paths: list[Path], out_dir: Path) -> None:
        progress = QProgressDialog("Exporting…", "Cancel", 0, len(paths), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)
        written: list[Path] = []
        errors: list[str] = []
        for i, p in enumerate(paths):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            QApplication.processEvents()
            ok, errs = export_files_to_png([p], out_dir)
            written.extend(ok)
            errors.extend(errs)
        progress.setValue(len(paths))
        summary = f"Exported {len(written)} of {len(paths)} file(s) to {out_dir}"
        if errors:
            summary += "\n\nErrors:\n" + "\n".join(errors)
            QMessageBox.warning(self, "Export", summary)
        else:
            self._status_bar.set_hint(summary)

    def _library_move(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Move Library To", str(self._library.root))
        if not chosen:
            return
        new_root = Path(chosen)
        if new_root.resolve() == self._library.root.resolve():
            return
        progress = QProgressDialog("Moving library…", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        def report(done: int, total: int) -> bool:
            progress.setMaximum(max(1, total))
            progress.setValue(done)
            QApplication.processEvents()
            return not progress.wasCanceled()

        old_root = self._library.root
        try:
            self._library.move_library(new_root, report)
        except OSError as e:
            QMessageBox.critical(self, "Move Library", f"Could not move library:\n{e}")
            return
        finally:
            progress.close()
        self._settings.set_library_directory(self._library.root)
        # Re-point open library tabs at their new locations
        for doc in self._documents.documents:
            if doc.is_library_file and doc.file_path is not None:
                try:
                    rel = doc.file_path.resolve().relative_to(old_root.resolve())
                except ValueError:
                    continue
                doc.file_path = self._library.root / rel

    def _reveal_document_in_library(self, doc: Document) -> None:
        if doc.file_path is None or not self._library.is_library_path(doc.file_path):
            QMessageBox.information(
                self, "Reveal in Library", "This document is not a library file."
            )
            return
        self._library_panel.show()
        self._library_panel.raise_()
        self._library_panel.select_path(doc.file_path)

    def _restore_session(self) -> None:
        """Reopen the tabs from the previous session (Library PRD 11.2)."""
        paths = [Path(p) for p in self._settings.session_open_files()]
        paths = [p for p in paths if p.is_file()]
        for p in paths:
            self._open_project(p)
        idx = self._settings.session_active_index()
        if paths and 0 <= idx < self._documents.count:
            self._documents.set_active_index(idx)

    def _save_session(self) -> None:
        open_files = [str(d.file_path) for d in self._documents.documents if d.file_path]
        self._settings.set_session_open_files(open_files)
        self._settings.set_session_active_index(max(0, self._documents.active_index))

    # ---- edit operations ----

    def _edit_undo(self) -> None:
        """Undo — first cancel any active tool operation, then undo."""
        active = self._tool_manager.active_tool
        if active is not None and active.is_active_operation:
            active.cancel()
            return  # first Ctrl+Z cancels active operation
        stack = self._scene.command_stack
        if self._require("Undo", (stack.can_undo, "something to undo")):
            stack.undo()

    def _edit_redo(self) -> None:
        stack = self._scene.command_stack
        if self._require("Redo", (stack.can_redo, "something to redo")):
            stack.redo()

    def _edit_deselect(self) -> None:
        if self._require_selection("Deselect"):
            self._selection_manager.deselect_all()

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
        if not self._require_selection("Cut"):
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
        items = self._require_selection("Copy")
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
        if not self._require("Paste", (self._clipboard_has_content(), "content on the clipboard")):
            return
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
        if not self._require(
            "Paste in Place", (self._clipboard_has_content(), "content on the clipboard")
        ):
            return
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
        items = self._require_selection("Delete")
        if not items:
            return
        from snapmock.commands.remove_item import RemoveItemCommand

        for item in items:
            self._scene.command_stack.push(RemoveItemCommand(self._scene, item))
        self._selection_manager.deselect_all()

    def _edit_duplicate(self) -> None:
        """Clone selected items with +10,+10 offset."""
        items = self._require_selection("Duplicate")
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
        """Select every unlocked item on the active layer (PRD 3.2)."""
        lm = self._scene.layer_manager
        active = lm.active_layer
        items: list[QGraphicsItem] = [
            i
            for i in self._scene.items()
            if isinstance(i, SnapGraphicsItem)
            and active is not None
            and i.layer_id == active.layer_id
            and not i.locked
        ]
        if self._require("Select All", (bool(items), "at least one item on the active layer")):
            self._selection_manager.select_items(items)

    def _edit_select_all_layers(self) -> None:
        """Select every unlocked item on every visible, unlocked layer."""
        lm = self._scene.layer_manager
        usable = {layer.layer_id for layer in lm.layers if layer.visible and not layer.locked}
        items: list[QGraphicsItem] = [
            i
            for i in self._scene.items()
            if isinstance(i, SnapGraphicsItem) and i.layer_id in usable and not i.locked
        ]
        if self._require("Select All Layers", (bool(items), "at least one item on the canvas")):
            self._selection_manager.select_items(items)

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
        active = self._require_active_layer("Duplicate Layer")
        if active is None:
            return
        from snapmock.commands.layer_commands import AddLayerCommand

        idx = lm.index_of(active.layer_id) + 1
        cmd = AddLayerCommand(lm, f"{active.name} copy", idx)
        self._scene.command_stack.push(cmd)

    def _layer_delete(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        if not self._require(
            "Delete Layer",
            (active is not None, "an active layer"),
            (lm.count > 1, "more than one layer"),
        ):
            return
        assert active is not None
        from snapmock.commands.layer_commands import RemoveLayerCommand

        cmd = RemoveLayerCommand(lm, active.layer_id)
        self._scene.command_stack.push(cmd)

    _MERGE_DEFERRAL = "Layer merging is scheduled for the raster operations follow-up."

    def _layer_merge_down(self) -> None:
        lm = self._scene.layer_manager
        active = lm.active_layer
        idx = lm.index_of(active.layer_id) if active is not None else -1
        if self._require("Merge Down", (idx > 0, "a layer below the active layer")):
            show_not_available(self, "Merge Down", self._MERGE_DEFERRAL)

    def _layer_merge_visible(self) -> None:
        visible = sum(1 for layer in self._scene.layer_manager.layers if layer.visible)
        if self._require("Merge Visible", (visible >= 2, "at least two visible layers")):
            show_not_available(self, "Merge Visible", self._MERGE_DEFERRAL)

    def _layer_flatten(self) -> None:
        count = self._scene.layer_manager.count
        if self._require("Flatten All", (count >= 2, "at least two layers")):
            show_not_available(self, "Flatten All", self._MERGE_DEFERRAL)

    def _layer_rename(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        lm = self._scene.layer_manager
        active = self._require_active_layer("Rename Layer")
        if active is None:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Layer", "New name:", text=active.name)
        if ok and new_name:
            from snapmock.commands.layer_commands import ChangeLayerPropertyCommand

            cmd = ChangeLayerPropertyCommand(lm, active.layer_id, "name", active.name, new_name)
            self._scene.command_stack.push(cmd)

    def _layer_properties(self) -> None:
        active = self._require_active_layer("Layer Properties")
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
        active = self._require_active_layer("Move Layer Up")
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if self._require("Move Layer Up", (idx < lm.count - 1, "a layer above the active layer")):
            from snapmock.commands.layer_commands import ReorderLayerCommand

            cmd = ReorderLayerCommand(lm, active.layer_id, idx + 1)
            self._scene.command_stack.push(cmd)

    def _layer_move_down(self) -> None:
        lm = self._scene.layer_manager
        active = self._require_active_layer("Move Layer Down")
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if self._require("Move Layer Down", (idx > 0, "a layer below the active layer")):
            from snapmock.commands.layer_commands import ReorderLayerCommand

            cmd = ReorderLayerCommand(lm, active.layer_id, idx - 1)
            self._scene.command_stack.push(cmd)

    def _layer_move_to_top(self) -> None:
        lm = self._scene.layer_manager
        active = self._require_active_layer("Move Layer to Top")
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if self._require(
            "Move Layer to Top", (idx < lm.count - 1, "a layer above the active layer")
        ):
            from snapmock.commands.layer_commands import ReorderLayerCommand

            cmd = ReorderLayerCommand(lm, active.layer_id, lm.count - 1)
            self._scene.command_stack.push(cmd)

    def _layer_move_to_bottom(self) -> None:
        lm = self._scene.layer_manager
        active = self._require_active_layer("Move Layer to Bottom")
        if active is None:
            return
        idx = lm.index_of(active.layer_id)
        if self._require("Move Layer to Bottom", (idx > 0, "a layer below the active layer")):
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
        items = self._require_selection("Lock Item")
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
        items = self._require_selection("Bring to Front")
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "front")
        self._scene.command_stack.push(cmd)

    def _arrange_bring_forward(self) -> None:
        items = self._require_selection("Bring Forward")
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "forward")
        self._scene.command_stack.push(cmd)

    def _arrange_send_backward(self) -> None:
        items = self._require_selection("Send Backward")
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "backward")
        self._scene.command_stack.push(cmd)

    def _arrange_send_to_back(self) -> None:
        items = self._require_selection("Send to Back")
        if not items:
            return
        from snapmock.commands.arrange_commands import ChangeZOrderCommand

        cmd = ChangeZOrderCommand(self._scene, items, "back")
        self._scene.command_stack.push(cmd)

    def _arrange_flip_horizontal(self) -> None:
        items = self._require_selection("Flip Horizontal")
        if not items:
            return
        from snapmock.commands.macro_command import MacroCommand
        from snapmock.commands.modify_property import ModifyPropertyCommand
        from snapmock.core.command_stack import BaseCommand

        cmds: list[BaseCommand] = [
            ModifyPropertyCommand(
                item, "flip_horizontal", item.flip_horizontal, not item.flip_horizontal
            )
            for item in items
        ]
        self._scene.command_stack.push(MacroCommand(cmds, "Flip Horizontal"))

    def _arrange_flip_vertical(self) -> None:
        items = self._require_selection("Flip Vertical")
        if not items:
            return
        from snapmock.commands.macro_command import MacroCommand
        from snapmock.commands.modify_property import ModifyPropertyCommand
        from snapmock.core.command_stack import BaseCommand

        cmds: list[BaseCommand] = [
            ModifyPropertyCommand(
                item, "flip_vertical", item.flip_vertical, not item.flip_vertical
            )
            for item in items
        ]
        self._scene.command_stack.push(MacroCommand(cmds, "Flip Vertical"))

    def _arrange_align(self, alignment: str) -> None:
        items = self._require_selection("Align", 2)
        if not items:
            return
        from snapmock.commands.arrange_commands import AlignItemsCommand

        cmd = AlignItemsCommand(items, alignment)
        self._scene.command_stack.push(cmd)

    def _arrange_distribute(self, direction: str) -> None:
        items = self._require_selection("Distribute", 3)
        if not items:
            return
        from snapmock.commands.arrange_commands import DistributeItemsCommand

        cmd = DistributeItemsCommand(items, direction)
        self._scene.command_stack.push(cmd)

    def _arrange_align_canvas_center(self) -> None:
        items = self._require_selection("Align to Canvas Center")
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
                no_action.triggered.connect(
                    lambda: self._require("Open Recent", (False, "a recently opened file"))
                )
            return
        for path_str in recent:
            action = self._recent_menu.addAction(Path(path_str).name)
            if action is not None:
                action.triggered.connect(
                    lambda _checked=False, p=path_str: self._open_project(Path(p))
                )

    # ---- autosave ----

    def _autosave(self) -> None:
        """Autosave every dirty non-library document that has a file."""
        for doc in self._documents.documents:
            if doc.is_library_file or doc.file_path is None or not doc.is_dirty:
                continue
            if doc.file_path.suffix.lower() != PROJECT_EXTENSION:
                continue
            try:
                save_project(doc.scene, doc.file_path)
            except Exception:  # noqa: BLE001
                pass  # Silent failure for autosave

    # ---- documents & tabs ----

    @property
    def _active_document(self) -> Document:
        doc = self._documents.active
        if doc is None:  # pragma: no cover - invariant: one document always open
            doc = Document(SnapScene(), parent=self)
            self._documents.add(doc)
        return doc

    @property
    def _scene(self) -> SnapScene:
        return self._active_document.scene

    @property
    def _view(self) -> SnapView:
        return self._active_document.view

    @property
    def _selection_manager(self) -> SelectionManager:
        return self._active_document.selection_manager

    @property
    def _clipboard(self) -> ClipboardManager:
        return self._active_document.clipboard

    @property
    def _current_file(self) -> Path | None:
        return self._active_document.file_path

    def _configure_view(self, view: SnapView) -> None:
        """Apply shared UI state to a document's view."""
        view.set_tool_manager(self._tool_manager)
        view.cursor_moved.connect(self._status_bar.update_cursor_pos)
        view.set_grid_visible(self._settings.grid_visible())
        view.set_grid_size(self._settings.grid_size())
        view.set_rulers_visible(self._settings.rulers_visible())

    def _wire_document(self, doc: Document) -> None:
        """Connect a document's signals to the window (once per document)."""
        if doc.tab_id in self._wired_docs:
            return
        self._wired_docs.add(doc.tab_id)
        doc.scene.command_stack.stack_changed.connect(self._update_title)
        lm = doc.scene.layer_manager
        lm.layer_lock_changed.connect(self._on_layer_lock_changed)
        lm.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        lm.active_layer_changed.connect(self._on_active_layer_changed)

    def _add_document(self, doc: Document, *, activate: bool = True) -> None:
        """Register a new document, replacing a pristine Untitled tab if present."""
        pristine = self._documents.active if self._is_pristine(self._documents.active) else None
        self._configure_view(doc.view)
        self._wire_document(doc)
        self._documents.add(doc, activate=activate)
        if pristine is not None and pristine is not doc and self._documents.count > 1:
            self._documents.remove(pristine)
            pristine.dispose()

    @staticmethod
    def _is_pristine(doc: Document | None) -> bool:
        """An unsaved, untouched Untitled document that can be replaced silently."""
        if doc is None:
            return False
        return (
            doc.file_path is None
            and not doc.is_library_file
            and doc.scene.command_stack.count == 0
            and not doc.scene.command_stack.is_dirty
        )

    def _on_active_document_changed(self, doc: Document | None) -> None:
        """Rebind the shared tool manager, panels and status bar to *doc*."""
        if doc is None:
            return
        prev_tool_id = self._tool_manager.active_tool_id or "select"
        active_tool = self._tool_manager.active_tool
        if active_tool is not None:
            active_tool.cancel()
            active_tool.deactivate()
        self._tool_manager._scene = doc.scene  # noqa: SLF001
        self._tool_manager._selection_manager = doc.selection_manager  # noqa: SLF001
        self._tool_manager.activate(prev_tool_id)
        # Panels are created after the first document; guard for construction order.
        if hasattr(self, "_layer_panel"):
            self._layer_panel.set_manager(doc.scene.layer_manager)
        if hasattr(self, "_property_panel"):
            self._property_panel.set_scene(doc.scene)
            self._property_panel.set_selection(doc.selection_manager)
        if hasattr(self, "_status_bar"):
            self._status_bar.set_view(doc.view)
        self._update_title()

    def _file_close_tab(self) -> None:
        self._close_document(self._active_document)

    def _close_document(self, doc: Document) -> bool:
        """Close *doc*, prompting to save if it has unsaved changes.

        Returns False if the user cancelled.
        """
        if not self._maybe_save_before_close(doc):
            return False
        self._library.detach_document(doc)
        if self._documents.count == 1:
            # Keep one document open at all times
            self._documents.add(Document(SnapScene(), parent=self))
            self._configure_view(self._active_document.view)
            self._wire_document(self._active_document)
        self._documents.remove(doc)
        self._wired_docs.discard(doc.tab_id)
        doc.dispose()
        return True

    def _close_other_documents(self, keep: Document) -> None:
        for doc in self._documents.documents:
            if doc is not keep and not self._close_document(doc):
                return

    def _close_all_documents(self) -> None:
        for doc in self._documents.documents:
            if not self._close_document(doc):
                return

    def _close_documents_to_right(self, doc: Document) -> None:
        docs = self._documents.documents
        idx = self._documents.index_of(doc)
        for other in docs[idx + 1 :]:
            if not self._close_document(other):
                return

    def _maybe_save_before_close(self, doc: Document) -> bool:
        """Prompt Save / Discard / Cancel for a dirty non-library document."""
        if not doc.is_dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            f'Save changes to "{doc.display_name}" before closing?',
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            self._documents.set_active(doc)
            self._file_save()
            return not doc.is_dirty
        return True

    def _reveal_document_in_file_manager(self, doc: Document) -> None:
        if doc.file_path is None:
            QMessageBox.information(self, "Reveal", "This document has not been saved yet.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(doc.file_path.parent)))

    # ---- helpers ----

    def _update_title(self) -> None:
        doc = self._active_document
        dirty = "*" if doc.is_dirty else ""
        self.setWindowTitle(f"{dirty}{doc.display_name} — {APP_NAME}")

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
        """Prompt for unsaved documents, then save window geometry and state.

        With Keep Running in Tray on and a tray icon present, closing hides the
        window instead and global hotkeys keep working (PRD 3.2).
        """
        keep_running = (
            self._primary_capture
            and self._tray is not None
            and self._settings.capture_keep_running_in_tray()
            and not self._quit_requested
        )
        if keep_running:
            self._settings.save_window_geometry(self.saveGeometry().data())
            self._settings.save_window_state(self.saveState().data())
            self._hidden_in_tray = True
            self.hide()
            if event is not None:
                event.ignore()
            return
        for doc in self._documents.documents:
            if doc.is_dirty:
                self._documents.set_active(doc)
                if not self._maybe_save_before_close(doc):
                    if event is not None:
                        event.ignore()
                    return
        self._library.flush()
        self._library.purge_session_trash()
        self._save_session()
        self._settings.save_window_geometry(self.saveGeometry().data())
        self._settings.save_window_state(self.saveState().data())
        if self._primary_capture:
            self._teardown_tray()
            self._capture.shutdown()
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

    @property
    def documents(self) -> DocumentManager:
        return self._documents

    @property
    def library(self) -> LibraryManager:
        return self._library

    @property
    def library_panel(self) -> LibraryPanel:
        return self._library_panel

    @property
    def active_document(self) -> Document:
        return self._active_document
