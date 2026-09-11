"""StampTool — choose a stamp from the library, click to place it, drag to size it (PRD 3.4).

Numbered Steps, Stamps & Emoji PRD Sections 3.4, 3.6, and 3.11: the active stamp shows in
the Tool Options Bar as a 32 px preview beside a Library button; a click places the stamp
centred on the click point at the configured size and a drag fits it inside the drag
rectangle (Shift for a square); with no stamp chosen a click opens the library panel; the
cursor carries a 24 px preview of the active stamp (kickoff silence 8).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QIcon, QMouseEvent, QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QLabel, QPushButton, QToolBar, QToolButton

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.stamp_library import (
    DEFAULT_STAMP_SIZE,
    STAMP_SIZE_MAX,
    STAMP_SIZE_MIN,
    StampInfo,
    StampLibrary,
    has_secondary_region,
    stamp_library,
)
from snapmock.items.stamp_item import (
    DEFAULT_STAMP_COLOR,
    DEFAULT_STAMP_SECONDARY_COLOR,
    StampItem,
)
from snapmock.tools import numbered_step_tool as _steps
from snapmock.tools.base_tool import BaseTool
from snapmock.ui.cursors import preview_cursor
from snapmock.ui.stamp_library_panel import StampLibraryPanel, stamp_pixmap
from snapmock.ui.unmet_requirements import check_requirements

MIN_DRAG_DISTANCE = 10.0
PREVIEW_SIZE = 32
"""The Tool Options Bar's active stamp preview (PRD 3.6)."""
CURSOR_PREVIEW_SIZE = 24
PLACEMENT_HINT_MS = 2000
NO_STAMP_HINT = "Select a stamp from the library, then click to place."


class StampTool(BaseTool):
    """Click to place the active stamp; drag to size it; the library panel chooses it."""

    # PRD 3.6 in order: the preview and library button ("tool"), size, the two colours, the
    # flips, opacity, shadow. Fill and stroke opacity are one opacity (kickoff silence 5).
    options_controls = (
        "tool",
        "stamp_size",
        "stamp_color",
        "stamp_secondary_color",
        "flip_horizontal",
        "flip_vertical",
        "opacity_pct",
        "shadow_enabled",
    )

    def __init__(self, library: StampLibrary | None = None) -> None:
        super().__init__()
        self._library = library
        self._creation_defaults = {
            "stamp_id": "",
            "stamp_size": DEFAULT_STAMP_SIZE,
            "stamp_color": QColor(DEFAULT_STAMP_COLOR),
            "stamp_secondary_color": QColor(DEFAULT_STAMP_SECONDARY_COLOR),
            "flip_horizontal": False,
            "flip_vertical": False,
            "opacity_pct": 100.0,
            "shadow_enabled": False,
        }
        self._panel: StampLibraryPanel | None = None
        self._panel_callback: Callable[[str], None] | None = None
        self._drag_start: QPointF | None = None
        self._drag_rect: QRectF | None = None
        self._drag_preview: QGraphicsRectItem | None = None
        self._placed_hint: str | None = None
        self._hint_timer: QTimer | None = None
        self._preview_button: QToolButton | None = None
        self._name_label: QLabel | None = None

    # ------------------------------------------------------------ identity

    @property
    def tool_id(self) -> str:
        return "stamp"

    @property
    def display_name(self) -> str:
        return "Stamp"

    def _lib(self) -> StampLibrary:
        return self._library if self._library is not None else stamp_library()

    @property
    def active_stamp(self) -> StampInfo | None:
        """The stamp the next click places, or None (PRD 3.4)."""
        stamp_id = str(self._creation_defaults.get("stamp_id", ""))
        return self._lib().stamp(stamp_id) if stamp_id else None

    @property
    def cursor(self) -> Qt.CursorShape | QCursor:
        info = self.active_stamp
        if info is None:
            return Qt.CursorShape.CrossCursor
        primary = self._color("stamp_color", DEFAULT_STAMP_COLOR)
        key = f"stamp:{info.id}:{primary.name()}"
        return preview_cursor(key, stamp_pixmap(self._lib(), info, CURSOR_PREVIEW_SIZE, primary))

    @property
    def status_hint(self) -> str:
        """PRD 3.11."""
        if self._placed_hint is not None:
            return self._placed_hint
        info = self.active_stamp
        if info is None:
            return NO_STAMP_HINT
        return f"Click to place {info.name}. Drag to set size."

    @property
    def is_active_operation(self) -> bool:
        return self._drag_start is not None

    # ------------------------------------------------------------ the active stamp

    def set_active_stamp(self, stamp_id: str) -> None:
        """Make *stamp_id* the stamp the next click places; the bar and cursor follow."""
        self._creation_defaults["stamp_id"] = stamp_id
        info = self.active_stamp
        if info is not None:
            self._creation_defaults["stamp_size"] = float(info.default_size)
        self._refresh_preview()
        self._push_hint()
        view = self._view
        if view is not None:
            apply = getattr(view, "_apply_tool_cursor", None)
            if callable(apply):
                apply()
        manager = self._tool_manager()
        if manager is not None:
            manager.tool_defaults_changed.emit(self.tool_id)

    def _tool_manager(self) -> Any:
        window = self._window()
        return getattr(window, "tool_manager", None)

    def _window(self) -> Any:
        view = self._view
        return view.window() if view is not None else None

    def on_option_changed(self, key: str, value: object) -> None:
        """A colour change on a stamp that cannot take it explains why (PRD 1.3)."""
        if key == "stamp_id":
            self._refresh_preview()
            self._push_hint()
            return
        info = self.active_stamp
        if key == "stamp_color" and info is not None and not info.colorizable:
            check_requirements(self._window(), "Stamp Color", [(False, "a colorizable stamp")])
        elif key == "stamp_secondary_color" and info is not None:
            svg = self._lib().svg_data(info.id) or ""
            check_requirements(
                self._window(),
                "Secondary Color",
                [
                    (info.colorizable, "a colorizable stamp"),
                    (has_secondary_region(svg), "a stamp with a secondary colour region"),
                ],
            )
        if key in ("stamp_color", "stamp_secondary_color", "stamp_id"):
            view = self._view
            if view is not None:
                apply = getattr(view, "_apply_tool_cursor", None)
                if callable(apply):
                    apply()

    # ------------------------------------------------------------ the library panel

    @property
    def panel(self) -> StampLibraryPanel | None:
        return self._panel

    def choose_stamp(
        self,
        anchor: Any = None,
        callback: Callable[[str], None] | None = None,
        current_id: str = "",
        fallback: Any = None,
    ) -> StampLibraryPanel:
        """Open the library panel beside *anchor*; *callback* takes the chosen id (the tool's
        own default when None)."""
        if self._panel is None:
            self._panel = StampLibraryPanel(self._lib())
            self._panel.stamp_chosen.connect(self._on_panel_chosen)
        self._panel_callback = callback
        self._panel.set_current(current_id or str(self._creation_defaults.get("stamp_id", "")))
        self._panel.open_beside(anchor, fallback)
        return self._panel

    def _on_panel_chosen(self, stamp_id: str) -> None:
        callback = self._panel_callback
        self._panel_callback = None
        if callback is not None:
            callback(stamp_id)
        else:
            self.set_active_stamp(stamp_id)

    # ------------------------------------------------------------ the bar

    def build_options_widgets(self, toolbar: QToolBar) -> None:
        """The 32 px preview (click opens the library) and the Library button (PRD 3.6)."""
        self._preview_button = QToolButton()
        self._preview_button.setFixedSize(PREVIEW_SIZE + 6, PREVIEW_SIZE + 6)
        self._preview_button.setIconSize(QSize(PREVIEW_SIZE, PREVIEW_SIZE))
        self._preview_button.setAccessibleName("Active stamp")
        self._preview_button.setToolTip("The active stamp; click to open the library")
        self._preview_button.clicked.connect(lambda: self.choose_stamp(self._preview_button))
        toolbar.addWidget(self._preview_button)
        self._name_label = QLabel("")
        self._name_label.setMinimumWidth(90)
        toolbar.addWidget(self._name_label)
        library_button = QPushButton("Library...")
        library_button.setAccessibleName("Stamp Library")
        library_button.setToolTip("Open the stamp library")
        library_button.setMaximumHeight(26)
        library_button.clicked.connect(lambda: self.choose_stamp(library_button))
        toolbar.addWidget(library_button)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        info = self.active_stamp
        if self._preview_button is not None:
            try:
                if info is None:
                    self._preview_button.setIcon(QIcon())
                    self._preview_button.setText("?")
                else:
                    self._preview_button.setText("")
                    self._preview_button.setIcon(
                        QIcon(
                            stamp_pixmap(
                                self._lib(),
                                info,
                                PREVIEW_SIZE,
                                self._color("stamp_color", DEFAULT_STAMP_COLOR),
                            )
                        )
                    )
            except RuntimeError:
                self._preview_button = None
        if self._name_label is not None:
            try:
                self._name_label.setText(info.name if info is not None else "No stamp selected")
            except RuntimeError:
                self._name_label = None

    def _color(self, key: str, default: str) -> QColor:
        value = self._creation_defaults.get(key)
        return QColor(value) if isinstance(value, QColor) else QColor(default)

    # ------------------------------------------------------------ lifecycle

    def deactivate(self) -> None:
        self._cleanup_drag()
        self._clear_placed_hint()
        self._preview_button = None
        self._name_label = None
        super().deactivate()

    def cancel(self) -> None:
        self._cleanup_drag()

    # ------------------------------------------------------------ placing

    def _layer_allows_placing(self) -> bool:
        if self._scene is None:
            return False
        layer = self._scene.layer_manager.active_layer
        if layer is None:
            return False
        return check_requirements(
            self._window(),
            "Stamp",
            [
                (not layer.locked, "an unlocked active layer"),
                (layer.visible, "a visible active layer"),
            ],
        )

    def _stamp_at(self, scene_pos: QPointF) -> StampItem | None:
        if self._scene is None:
            return None
        for gitem in self._scene.items(scene_pos):
            if isinstance(gitem, StampItem) and gitem.parentItem() is None:
                layer = self._scene.layer_manager.layer_by_id(gitem.layer_id)
                if layer is not None and (layer.locked or not layer.visible):
                    continue
                return gitem
        return None

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        view = self._view
        if view is None:
            return False
        scene_pos = view.mapToScene(event.pos())
        existing = self._stamp_at(scene_pos)
        if existing is not None:
            if self._selection_manager is not None:
                self._selection_manager.select(existing)
            return True
        if self.active_stamp is None:
            # No stamp selected: the library opens (PRD 3.4)
            self.choose_stamp(
                self._preview_button,
                fallback=view.viewport().mapToGlobal(event.pos()),  # type: ignore[union-attr]
            )
            return True
        if not self._layer_allows_placing():
            return True
        self._drag_start = self._snap_pos(scene_pos)
        self._drag_rect = None
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        view = self._view
        if view is None or self._scene is None or self._drag_start is None:
            return False
        current = view.mapToScene(event.pos())
        dx = current.x() - self._drag_start.x()
        dy = current.y() - self._drag_start.y()
        if abs(dx) < MIN_DRAG_DISTANCE and abs(dy) < MIN_DRAG_DISTANCE:
            self._drag_rect = None
            self._cleanup_drag_preview()
            return True
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            side = max(abs(dx), abs(dy))
            dx = side if dx >= 0 else -side
            dy = side if dy >= 0 else -side
            current = QPointF(self._drag_start.x() + dx, self._drag_start.y() + dy)
        self._drag_rect = QRectF(self._drag_start, current).normalized()
        if self._drag_preview is None:
            preview = QGraphicsRectItem()
            pen = QPen(QColor("#0078d7"), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            preview.setPen(pen)
            preview.setZValue(1e9)
            self._scene.addItem(preview)
            self._drag_preview = preview
        self._drag_preview.setRect(self._drag_rect)
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._scene is None or self._drag_start is None:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        start, rect = self._drag_start, self._drag_rect
        self._cleanup_drag()
        if rect is None:
            self.place(start)
        else:
            self.place(rect.center(), rect)
        return True

    def mouse_double_click(self, event: QMouseEvent) -> bool:
        """A double-click on a stamp opens the library to replace it (PRD 3.7)."""
        view = self._view
        if view is None or self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        stamp = self._stamp_at(view.mapToScene(event.pos()))
        if stamp is None:
            return False
        self._cleanup_drag()
        open_editor = getattr(self._window(), "open_marker_editor", None)
        if callable(open_editor):
            open_editor(stamp)
        return True

    def place(self, center: QPointF, fit: QRectF | None = None) -> StampItem | None:
        """Place the active stamp centred on *center*, fitted inside *fit* when given."""
        scene = self._scene
        info = self.active_stamp
        if scene is None or info is None:
            return None
        layer = scene.layer_manager.active_layer
        if layer is None:
            return None
        item = StampItem(library=self._library)
        item.set_stamp(info, self._lib().svg_data(info.id))
        self._apply_creation_defaults(item)
        if fit is not None:
            item.stamp_size = fitted_size(item, fit)
        item.setPos(center)
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
        _steps.animate_placement(
            item, _steps.PLACEMENT_START_SCALE, _steps.PLACEMENT_ANIMATION_MS, scene
        )
        self._show_placed_hint(info.name)
        return item

    def _apply_creation_defaults(self, item: StampItem) -> None:
        d = self._creation_defaults
        item.stamp_size = float(d.get("stamp_size", DEFAULT_STAMP_SIZE))
        item.stamp_color = self._color("stamp_color", DEFAULT_STAMP_COLOR)
        item.stamp_secondary_color = self._color(
            "stamp_secondary_color", DEFAULT_STAMP_SECONDARY_COLOR
        )
        item.flip_horizontal = bool(d.get("flip_horizontal", False))
        item.flip_vertical = bool(d.get("flip_vertical", False))
        item.opacity_pct = float(d.get("opacity_pct", 100.0))
        item.shadow_enabled = bool(d.get("shadow_enabled", False))

    # ------------------------------------------------------------ hints

    def _show_placed_hint(self, name: str) -> None:
        self._placed_hint = f"Placed {name}. Click to place another."
        self._push_hint()
        if self._hint_timer is None:
            self._hint_timer = QTimer()
            self._hint_timer.setSingleShot(True)
            self._hint_timer.timeout.connect(self._show_idle_hint)
        self._hint_timer.start(PLACEMENT_HINT_MS)

    def _show_idle_hint(self) -> None:
        self._clear_placed_hint()
        self._push_hint()

    def _clear_placed_hint(self) -> None:
        self._placed_hint = None
        if self._hint_timer is not None and self._hint_timer.isActive():
            self._hint_timer.stop()

    def _push_hint(self) -> None:
        window = self._window()
        show = getattr(window, "show_status_hint", None)
        manager = self._tool_manager()
        active = getattr(manager, "active_tool", None) if manager is not None else None
        if callable(show) and self._scene is not None and active is self:
            show(self.status_hint)

    # ------------------------------------------------------------ drag cleanup

    def _cleanup_drag_preview(self) -> None:
        if self._drag_preview is not None:
            if self._scene is not None and self._drag_preview.scene() is self._scene:
                self._scene.removeItem(self._drag_preview)
            self._drag_preview = None

    def _cleanup_drag(self) -> None:
        self._cleanup_drag_preview()
        self._drag_start = None
        self._drag_rect = None


def fitted_size(item: StampItem, fit: QRectF) -> float:
    """The ``stamp_size`` at which *item*'s aspect fits inside *fit* (PRD 3.4)."""
    rect = item.stamp_rect()
    if rect.width() <= 0 or rect.height() <= 0:
        return item.stamp_size
    scale = min(fit.width() / rect.width(), fit.height() / rect.height())
    return max(STAMP_SIZE_MIN, min(STAMP_SIZE_MAX, item.stamp_size * scale))
