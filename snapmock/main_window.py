"""MainWindow — primary application window."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QFileDialog, QMainWindow, QMenu, QMenuBar, QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsItem

from snapmock.config.constants import (
    APP_NAME,
    AUTOSAVE_INTERVAL_MS,
    PROJECT_EXTENSION,
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

        self._property_panel = PropertyPanel(self._selection_manager, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._property_panel)

        self._status_bar = SnapStatusBar(self._view)
        self.setStatusBar(self._status_bar)

        # Wire cursor position tracking
        self._view.cursor_moved.connect(self._status_bar.update_cursor_pos)

        # Menu bar
        self._recent_menu: QMenu | None = None
        self._setup_menus()
        self._setup_tool_shortcuts()

        # Autosave timer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        if self._settings.autosave_enabled():
            self._autosave_timer.start(AUTOSAVE_INTERVAL_MS)

        # Track dirty state for window title
        self._scene.command_stack.stack_changed.connect(self._update_title)

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
            import_action.triggered.connect(self._file_import_image)

        export_action = file_menu.addAction("&Export...")
        if export_action is not None:
            export_action.setShortcut(QKeySequence(SHORTCUTS["file.export"]))
            export_action.triggered.connect(self._file_export)

        file_menu.addSeparator()

        self._recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_files_menu()

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
            undo_action.triggered.connect(self._scene.command_stack.undo)

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

    # ---- tool shortcuts ----

    def _setup_tool_shortcuts(self) -> None:
        """Bind single-key shortcuts from SHORTCUTS to activate tools."""
        tool_shortcut_map = {
            "tool.select": "select",
            "tool.rectangle": "rectangle",
            "tool.ellipse": "ellipse",
            "tool.line": "line",
            "tool.arrow": "arrow",
            "tool.freehand": "freehand",
            "tool.text": "text",
            "tool.callout": "callout",
            "tool.highlight": "highlight",
            "tool.blur": "blur",
            "tool.numbered_step": "numbered_step",
            "tool.stamp": "stamp",
            "tool.crop": "crop",
            "tool.raster_select": "raster_select",
            "tool.eyedropper": "eyedropper",
            "tool.pan": "pan",
            "tool.zoom": "zoom",
            "tool.lasso_select": "lasso_select",
        }
        for shortcut_key, tool_id in tool_shortcut_map.items():
            key_seq = SHORTCUTS.get(shortcut_key, "")
            if not key_seq:
                continue
            action = QAction(self)
            action.setShortcut(QKeySequence(key_seq))
            # Capture tool_id by default arg
            action.triggered.connect(
                lambda _checked=False, tid=tool_id: self._tool_manager.activate(tid)
            )
            self.addAction(action)

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
        self._property_panel.set_selection(self._selection_manager)
        self._scene.command_stack.stack_changed.connect(self._update_title)
        self._current_file = None
        self._update_title()
        old_scene.deleteLater()

    def _file_open(self) -> None:
        """Open an existing .smk project."""
        if not self._confirm_discard():
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", f"SnapMock Projects (*{PROJECT_EXTENSION});;All Files (*)"
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
        self._property_panel.set_selection(self._selection_manager)
        self._scene.command_stack.stack_changed.connect(self._update_title)
        self._current_file = path
        self._add_recent_file(path)
        self._update_title()
        old_scene.deleteLater()

    def _file_save(self) -> None:
        """Save the current project."""
        if self._current_file is None:
            self._file_save_as()
            return
        self._save_to(self._current_file)

    def _file_save_as(self) -> None:
        """Save the current project to a new path."""
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", f"SnapMock Projects (*{PROJECT_EXTENSION})"
        )
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix != PROJECT_EXTENSION:
            path = path.with_suffix(PROJECT_EXTENSION)
        self._save_to(path)

    def _save_to(self, path: Path) -> None:
        try:
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

    # ---- edit operations ----

    def _edit_cut(self) -> None:
        self._edit_copy()
        self._edit_delete()

    def _edit_copy(self) -> None:
        items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
        if items:
            self._clipboard.copy_items(items)

    def _edit_paste(self) -> None:
        # Smart paste routing: internal items → system image → system text
        data = self._clipboard.paste_items()
        if data:
            self._paste_internal_items(data, offset=True)
            return
        # Try system clipboard image
        sys_image = self._clipboard.paste_image_from_system()
        if sys_image is not None:
            self._paste_system_image(sys_image)
            return

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

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
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
