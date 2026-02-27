"""SelectTool — click-select, drag-move, rubber-band multi-select, nudge, transform."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QLabel, QToolBar

from snapmock.commands.move_items import MoveItemsCommand
from snapmock.config.constants import DRAG_THRESHOLD
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.tools.base_tool import BaseTool
from snapmock.ui.transform_handles import TransformHandles

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager


class _State(Enum):
    IDLE = auto()
    RUBBER_BAND = auto()
    DRAGGING = auto()
    HANDLE_DRAG = auto()


class SelectTool(BaseTool):
    """The default selection and move tool with rubber-band, nudge, and transform handles."""

    def __init__(self) -> None:
        super().__init__()
        self._state: _State = _State.IDLE
        self._press_pos: QPointF = QPointF()
        self._drag_start: QPointF = QPointF()
        self._drag_items: list[SnapGraphicsItem] = []
        self._drag_total: QPointF = QPointF()
        self._constrain_axis: str | None = None  # "x" or "y" when Shift is held

        # Rubber-band
        self._rubber_band: QGraphicsRectItem | None = None

        # Transform handles
        self._handles: TransformHandles | None = None

        # Selection info label
        self._info_label: QLabel | None = None

    @property
    def tool_id(self) -> str:
        return "select"

    @property
    def display_name(self) -> str:
        return "Select"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.ArrowCursor

    @property
    def is_active_operation(self) -> bool:
        return self._state in (_State.DRAGGING, _State.RUBBER_BAND, _State.HANDLE_DRAG)

    def activate(self, scene: SnapScene, selection_manager: SelectionManager) -> None:
        super().activate(scene, selection_manager)
        self._handles = TransformHandles(scene)
        self._update_handles()
        if selection_manager is not None:
            selection_manager.selection_changed.connect(self._on_selection_changed)

    def deactivate(self) -> None:
        self.cancel()
        if self._selection_manager is not None:
            try:
                self._selection_manager.selection_changed.disconnect(self._on_selection_changed)
            except (TypeError, RuntimeError):
                pass
        if self._handles is not None:
            self._handles.remove_from_scene()
            self._handles = None
        super().deactivate()

    def cancel(self) -> None:
        if self._rubber_band is not None and self._scene is not None:
            self._scene.removeItem(self._rubber_band)
            self._rubber_band = None
        self._state = _State.IDLE
        self._drag_items = []
        self._constrain_axis = None

    def _on_selection_changed(self, _items: list[object]) -> None:
        self._update_handles()

    def _update_handles(self) -> None:
        if self._handles is None or self._selection_manager is None:
            return
        items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
        if not items:
            self._handles.remove_from_scene()
            return
        self._handles.add_to_scene()
        rect = self._selection_bounding_rect(items)
        self._handles.update_rect(rect)

    def _selection_bounding_rect(self, items: list[SnapGraphicsItem]) -> QRectF:
        if not items:
            return QRectF()
        rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        return rect

    def _scene_pos(self, event: QMouseEvent) -> QPointF | None:
        view = self._view
        if view is not None:
            return view.mapToScene(event.pos())
        return None

    def _item_at(self, scene_pos: QPointF) -> SnapGraphicsItem | None:
        if self._scene is None:
            return None
        view = self._view
        if view is None:
            return None
        for gitem in self._scene.items(scene_pos):
            if isinstance(gitem, SnapGraphicsItem):
                # Skip items on locked/hidden layers
                layer = self._scene.layer_manager.layer_by_id(gitem.layer_id)
                if layer is not None and (layer.locked or not layer.visible):
                    continue
                return gitem
        return None

    # --- mouse events ---

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or self._selection_manager is None:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        scene_pos = self._scene_pos(event)
        if scene_pos is None:
            return False

        self._press_pos = scene_pos
        self._drag_total = QPointF(0, 0)
        self._constrain_axis = None

        # Check if clicking on a transform handle
        if self._handles is not None:
            handle = self._handles.handle_at(scene_pos)
            if handle is not None:
                self._state = _State.HANDLE_DRAG
                self._drag_start = scene_pos
                return True

        # Check for item under cursor
        item = self._item_at(scene_pos)

        if item is not None:
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            if ctrl:
                self._selection_manager.toggle(item)
            elif shift:
                self._selection_manager.select(item, add=True)
            elif item not in self._selection_manager.items:
                self._selection_manager.select(item)
            # Prepare for drag
            self._drag_start = scene_pos
            self._drag_items = [
                i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)
            ]
            self._state = _State.DRAGGING
        else:
            # No item — start rubber-band or deselect
            if not (
                event.modifiers()
                & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier)
            ):
                self._selection_manager.deselect_all()
            self._drag_start = scene_pos
            self._state = _State.RUBBER_BAND
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._scene is None:
            return False
        scene_pos = self._scene_pos(event)
        if scene_pos is None:
            return False

        if self._state == _State.DRAGGING:
            return self._handle_drag_move(scene_pos, event)
        elif self._state == _State.RUBBER_BAND:
            return self._handle_rubber_band_move(scene_pos)
        elif self._state == _State.HANDLE_DRAG:
            # Handle resize drag is a placeholder for future implementation
            return True
        return False

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._scene is None:
            return False
        scene_pos = self._scene_pos(event)
        if scene_pos is None:
            self._state = _State.IDLE
            return False

        if self._state == _State.DRAGGING:
            return self._handle_drag_release()
        elif self._state == _State.RUBBER_BAND:
            return self._handle_rubber_band_release(scene_pos, event)
        elif self._state == _State.HANDLE_DRAG:
            self._state = _State.IDLE
            return True

        self._state = _State.IDLE
        return True

    def mouse_double_click(self, event: QMouseEvent) -> bool:
        if self._scene is None or self._selection_manager is None:
            return False
        scene_pos = self._scene_pos(event)
        if scene_pos is None:
            return False
        # Double-click on an item could open property editing
        # For now, just select the item under cursor
        item = self._item_at(scene_pos)
        if item is not None:
            self._selection_manager.select(item)
            return True
        return False

    # --- drag movement ---

    def _handle_drag_move(self, scene_pos: QPointF, event: QMouseEvent) -> bool:
        raw_delta = scene_pos - self._drag_start

        # Check if we've passed the drag threshold
        total = self._drag_total + raw_delta
        if abs(total.x()) < DRAG_THRESHOLD and abs(total.y()) < DRAG_THRESHOLD:
            return True

        # Shift constrains to dominant axis
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if shift:
            if self._constrain_axis is None and (abs(total.x()) > 10 or abs(total.y()) > 10):
                self._constrain_axis = "x" if abs(total.x()) >= abs(total.y()) else "y"
            if self._constrain_axis == "x":
                raw_delta = QPointF(raw_delta.x(), 0)
            elif self._constrain_axis == "y":
                raw_delta = QPointF(0, raw_delta.y())
        else:
            self._constrain_axis = None

        for item in self._drag_items:
            item.moveBy(raw_delta.x(), raw_delta.y())
        self._drag_start = scene_pos
        self._drag_total = QPointF(
            self._drag_total.x() + raw_delta.x(),
            self._drag_total.y() + raw_delta.y(),
        )
        self._update_handles()
        return True

    def _handle_drag_release(self) -> bool:
        total = self._drag_total
        if self._drag_items and (
            abs(total.x()) >= DRAG_THRESHOLD or abs(total.y()) >= DRAG_THRESHOLD
        ):
            # We already moved items visually. Undo that, then push command.
            for item in self._drag_items:
                item.moveBy(-total.x(), -total.y())
            cmd = MoveItemsCommand(self._drag_items, total)
            if self._scene is not None:
                self._scene.command_stack.push(cmd)
        self._state = _State.IDLE
        self._drag_items = []
        self._constrain_axis = None
        self._update_handles()
        return True

    # --- rubber-band ---

    def _handle_rubber_band_move(self, scene_pos: QPointF) -> bool:
        delta = scene_pos - self._drag_start
        if abs(delta.x()) < DRAG_THRESHOLD and abs(delta.y()) < DRAG_THRESHOLD:
            return True

        rect = QRectF(self._drag_start, scene_pos).normalized()
        if self._rubber_band is None and self._scene is not None:
            self._rubber_band = QGraphicsRectItem(rect)
            self._rubber_band.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.DashLine))
            self._rubber_band.setBrush(QBrush(QColor(0, 120, 215, 30)))
            self._rubber_band.setZValue(999999)
            self._scene.addItem(self._rubber_band)
        elif self._rubber_band is not None:
            self._rubber_band.setRect(rect)
        return True

    def _handle_rubber_band_release(self, scene_pos: QPointF, event: QMouseEvent) -> bool:
        rect = QRectF(self._drag_start, scene_pos).normalized()

        # Remove rubber band visual
        if self._rubber_band is not None and self._scene is not None:
            self._scene.removeItem(self._rubber_band)
            self._rubber_band = None

        if self._selection_manager is None or self._scene is None:
            self._state = _State.IDLE
            return True

        # If the rect is too small, treat as a click (deselect already happened)
        if rect.width() < DRAG_THRESHOLD and rect.height() < DRAG_THRESHOLD:
            self._state = _State.IDLE
            return True

        # Find items in the rubber-band rectangle
        items_in_rect: list[SnapGraphicsItem] = []
        for gitem in self._scene.items(rect, Qt.ItemSelectionMode.IntersectsItemShape):
            if isinstance(gitem, SnapGraphicsItem):
                layer = self._scene.layer_manager.layer_by_id(gitem.layer_id)
                if layer is not None and (layer.locked or not layer.visible):
                    continue
                items_in_rect.append(gitem)

        # Modifier logic
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        if ctrl:
            # Toggle (XOR)
            for item in items_in_rect:
                self._selection_manager.toggle(item)
        elif shift:
            # Additive (union)
            for item in items_in_rect:
                if item not in self._selection_manager.items:
                    self._selection_manager.select(item, add=True)
        else:
            # Replace selection
            from PyQt6.QtWidgets import QGraphicsItem

            gi_items: list[QGraphicsItem] = list(items_in_rect)
            self._selection_manager.select_items(gi_items)

        self._state = _State.IDLE
        self._update_handles()
        return True

    # --- key events ---

    def key_press(self, event: QKeyEvent) -> bool:
        if self._selection_manager is None or self._scene is None:
            return False

        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        # Arrow key nudge
        nudge = 10 if shift else 1
        delta: QPointF | None = None

        if key == Qt.Key.Key_Left:
            delta = QPointF(-nudge, 0)
        elif key == Qt.Key.Key_Right:
            delta = QPointF(nudge, 0)
        elif key == Qt.Key.Key_Up:
            delta = QPointF(0, -nudge)
        elif key == Qt.Key.Key_Down:
            delta = QPointF(0, nudge)

        if delta is not None:
            items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
            if items:
                cmd = MoveItemsCommand(items, delta)
                self._scene.command_stack.push(cmd)
                self._update_handles()
            return True

        # Delete / Backspace
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
            if items:
                self._delete_items(items)
            return True

        return False

    def _delete_items(self, items: list[SnapGraphicsItem]) -> None:
        if self._scene is None or self._selection_manager is None:
            return
        from snapmock.commands.remove_item import RemoveItemCommand

        # Skip items on locked layers
        deletable = []
        for item in items:
            layer = self._scene.layer_manager.layer_by_id(item.layer_id)
            if layer is not None and layer.locked:
                continue
            deletable.append(item)

        for item in deletable:
            self._scene.command_stack.push(RemoveItemCommand(self._scene, item))
        self._selection_manager.deselect_all()

    # --- tool options ---

    def build_options_widgets(self, toolbar: QToolBar) -> None:
        self._info_label = QLabel("No selection")
        toolbar.addWidget(self._info_label)
        self._update_info_label()

    def _update_info_label(self) -> None:
        if self._info_label is None or self._selection_manager is None:
            return
        count = self._selection_manager.count
        if count == 0:
            self._info_label.setText("No selection")
        elif count == 1:
            items = [i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)]
            if items:
                r = items[0].sceneBoundingRect()
                self._info_label.setText(f"1 item — {r.width():.0f} × {r.height():.0f}")
            else:
                self._info_label.setText("1 item")
        else:
            self._info_label.setText(f"{count} items selected")
