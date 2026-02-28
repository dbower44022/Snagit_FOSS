"""SelectTool — click-select, drag-move, rubber-band multi-select, nudge, transform."""

from __future__ import annotations

import math
from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPen, QTransform
from PyQt6.QtWidgets import QGraphicsRectItem, QLabel, QToolBar, QToolTip

from snapmock.commands.move_items import MoveItemsCommand
from snapmock.config.constants import DRAG_THRESHOLD
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.tools.base_tool import BaseTool
from snapmock.ui.transform_handles import (
    CORNER_HANDLES,
    EDGE_HANDLES,
    HandlePosition,
    TransformHandles,
)

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

        # Handle-drag state
        self._handle_pos: HandlePosition | None = None
        self._handle_origin_rect: QRectF = QRectF()
        self._handle_anchor: QPointF = QPointF()
        self._handle_item_originals: list[
            tuple[SnapGraphicsItem, QPointF, QTransform]
        ] = []

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
                self._handle_pos = handle
                self._handle_origin_rect = QRectF(self._handles.current_rect)
                self._handle_anchor = self._handles.anchor_for_handle(handle)
                # Save original pos/transform for each selected item
                items = [
                    i
                    for i in self._selection_manager.items
                    if isinstance(i, SnapGraphicsItem)
                ]
                self._handle_item_originals = [
                    (item, QPointF(item.pos()), QTransform(item.transform()))
                    for item in items
                ]
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
            return self._handle_transform_move(scene_pos, event)
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
            return self._handle_transform_release()

        self._state = _State.IDLE
        return True

    def mouse_double_click(self, event: QMouseEvent) -> bool:
        if self._scene is None or self._selection_manager is None:
            return False
        scene_pos = self._scene_pos(event)
        if scene_pos is None:
            return False

        item = self._item_at(scene_pos)
        if item is not None:
            from snapmock.items.callout_item import CalloutItem
            from snapmock.items.text_item import TextItem

            self._selection_manager.select(item)
            # Double-click on text/callout: switch to text tool
            if isinstance(item, (TextItem, CalloutItem)):
                view = self._view
                if view is not None:
                    parent = view.parentWidget()
                    if parent is not None and hasattr(parent, "tool_manager"):
                        parent.tool_manager.activate("text")
            return True

        # Double-click on empty canvas: toggle fit/100%
        view = self._view
        if view is not None:
            if view.zoom_percent == 100:
                view.fit_in_view_all()
            else:
                view.set_zoom(100)
        return True

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

        # Snap to grid if visible
        view = self._view
        if view is not None and view._grid_visible:  # noqa: SLF001
            grid = view._grid_size  # noqa: SLF001
            # Snap the new total movement to grid
            new_total_x = self._drag_total.x() + raw_delta.x()
            new_total_y = self._drag_total.y() + raw_delta.y()
            snapped_x = round(new_total_x / grid) * grid
            snapped_y = round(new_total_y / grid) * grid
            raw_delta = QPointF(
                snapped_x - self._drag_total.x(),
                snapped_y - self._drag_total.y(),
            )

        for item in self._drag_items:
            item.moveBy(raw_delta.x(), raw_delta.y())
        self._drag_start = scene_pos
        self._drag_total = QPointF(
            self._drag_total.x() + raw_delta.x(),
            self._drag_total.y() + raw_delta.y(),
        )
        self._update_handles()

        # Move delta tooltip
        if view is not None:
            vp = view.viewport()
            if vp is not None:
                global_pos = vp.mapToGlobal(view.mapFromScene(scene_pos))
                dx = self._drag_total.x()
                dy = self._drag_total.y()
                QToolTip.showText(
                    global_pos, f"\u0394X: {dx:+.0f}  \u0394Y: {dy:+.0f}"
                )
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

    # --- handle transform ---

    def _handle_transform_move(
        self, scene_pos: QPointF, event: QMouseEvent
    ) -> bool:
        if self._handle_pos is None or not self._handle_item_originals:
            return True

        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        if self._handle_pos == HandlePosition.ROTATE:
            self._apply_rotation(scene_pos, shift)
        elif self._handle_pos in CORNER_HANDLES:
            self._apply_corner_resize(scene_pos, shift, alt)
        elif self._handle_pos in EDGE_HANDLES:
            self._apply_edge_resize(scene_pos, ctrl)

        self._update_handles()
        return True

    def _apply_rotation(self, cursor: QPointF, snap: bool) -> None:
        """Rotate all selected items around the selection center."""
        center = self._handle_origin_rect.center()
        angle = math.degrees(
            math.atan2(cursor.y() - center.y(), cursor.x() - center.x())
        ) - math.degrees(
            math.atan2(
                self._drag_start.y() - center.y(),
                self._drag_start.x() - center.x(),
            )
        )
        if snap:
            angle = round(angle / 15.0) * 15.0

        for item, orig_pos, orig_xform in self._handle_item_originals:
            # Rotate position around center
            offset = orig_pos - center
            rad = math.radians(angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            new_offset = QPointF(
                offset.x() * cos_a - offset.y() * sin_a,
                offset.x() * sin_a + offset.y() * cos_a,
            )
            item.setPos(center + new_offset)
            # Apply rotation transform
            xform = QTransform(orig_xform)
            xform.rotate(angle)
            item.setTransform(xform)

        # Tooltip
        view = self._view
        if view is not None:
            vp = view.viewport()
            if vp is not None:
                global_pos = vp.mapToGlobal(
                    view.mapFromScene(cursor)
                )
                QToolTip.showText(global_pos, f"{angle:+.1f}°")

    def _apply_corner_resize(
        self, cursor: QPointF, proportional: bool, from_center: bool
    ) -> None:
        """Resize from a corner handle."""
        anchor = (
            self._handle_origin_rect.center()
            if from_center
            else self._handle_anchor
        )
        orig_rect = self._handle_origin_rect

        # Compute scale factors relative to anchor
        orig_w = abs(self._drag_start.x() - anchor.x())
        orig_h = abs(self._drag_start.y() - anchor.y())
        new_w = abs(cursor.x() - anchor.x())
        new_h = abs(cursor.y() - anchor.y())

        sx = new_w / max(orig_w, 1.0)
        sy = new_h / max(orig_h, 1.0)

        if proportional:
            s = min(sx, sy)
            sx = sy = s

        # Clamp minimum
        sx = max(sx, 0.01)
        sy = max(sy, 0.01)

        for item, orig_pos, orig_xform in self._handle_item_originals:
            offset = orig_pos - anchor
            item.setPos(anchor + QPointF(offset.x() * sx, offset.y() * sy))
            xform = QTransform(orig_xform)
            xform.scale(sx, sy)
            item.setTransform(xform)

        # Tooltip
        new_rect_w = orig_rect.width() * sx
        new_rect_h = orig_rect.height() * sy
        view = self._view
        if view is not None:
            vp = view.viewport()
            if vp is not None:
                global_pos = vp.mapToGlobal(view.mapFromScene(cursor))
                QToolTip.showText(
                    global_pos,
                    f"{new_rect_w:.0f} × {new_rect_h:.0f}",
                )

    def _apply_edge_resize(self, cursor: QPointF, skew: bool) -> None:
        """Resize from an edge midpoint handle. Ctrl = shear."""
        anchor = self._handle_anchor
        orig_rect = self._handle_origin_rect

        if skew:
            self._apply_skew(cursor)
            return

        hp = self._handle_pos
        sx = 1.0
        sy = 1.0
        if hp in (HandlePosition.MIDDLE_LEFT, HandlePosition.MIDDLE_RIGHT):
            orig_w = abs(self._drag_start.x() - anchor.x())
            new_w = abs(cursor.x() - anchor.x())
            sx = max(new_w / max(orig_w, 1.0), 0.01)
        elif hp in (HandlePosition.TOP_CENTER, HandlePosition.BOTTOM_CENTER):
            orig_h = abs(self._drag_start.y() - anchor.y())
            new_h = abs(cursor.y() - anchor.y())
            sy = max(new_h / max(orig_h, 1.0), 0.01)

        for item, orig_pos, orig_xform in self._handle_item_originals:
            offset = orig_pos - anchor
            item.setPos(anchor + QPointF(offset.x() * sx, offset.y() * sy))
            xform = QTransform(orig_xform)
            xform.scale(sx, sy)
            item.setTransform(xform)

        new_w = orig_rect.width() * sx
        new_h = orig_rect.height() * sy
        view = self._view
        if view is not None:
            vp = view.viewport()
            if vp is not None:
                global_pos = vp.mapToGlobal(view.mapFromScene(cursor))
                QToolTip.showText(
                    global_pos, f"{new_w:.0f} × {new_h:.0f}"
                )

    def _apply_skew(self, cursor: QPointF) -> None:
        """Apply shear when Ctrl+edge drag."""
        hp = self._handle_pos
        delta = cursor - self._drag_start
        rect = self._handle_origin_rect

        shear_x = 0.0
        shear_y = 0.0
        if hp in (HandlePosition.TOP_CENTER, HandlePosition.BOTTOM_CENTER):
            shear_x = delta.x() / max(rect.height(), 1.0)
        elif hp in (HandlePosition.MIDDLE_LEFT, HandlePosition.MIDDLE_RIGHT):
            shear_y = delta.y() / max(rect.width(), 1.0)

        center = rect.center()
        for item, orig_pos, orig_xform in self._handle_item_originals:
            offset = orig_pos - center
            new_x = offset.x() + offset.y() * shear_x
            new_y = offset.y() + offset.x() * shear_y
            item.setPos(center + QPointF(new_x, new_y))
            xform = QTransform(orig_xform)
            xform.shear(shear_x, shear_y)
            item.setTransform(xform)

    def _handle_transform_release(self) -> bool:
        """Commit transform as undoable command(s)."""
        from snapmock.commands.macro_command import MacroCommand
        from snapmock.commands.transform_item import TransformItemCommand

        commands = []
        for item, orig_pos, orig_xform in self._handle_item_originals:
            new_pos = QPointF(item.pos())
            new_xform = QTransform(item.transform())
            if new_pos != orig_pos or new_xform != orig_xform:
                # Revert to original so command redo applies change
                item.setPos(orig_pos)
                item.setTransform(orig_xform)
                commands.append(
                    TransformItemCommand(
                        item, orig_pos, new_pos, orig_xform, new_xform
                    )
                )

        if commands and self._scene is not None:
            if len(commands) == 1:
                self._scene.command_stack.push(commands[0])
            else:
                self._scene.command_stack.push(
                    MacroCommand(commands, "Transform items")
                )

        self._state = _State.IDLE
        self._handle_pos = None
        self._handle_item_originals = []
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
            # No items selected — let the event fall through for viewport pan
            return False

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

    @property
    def status_hint(self) -> str:
        if self._state == _State.DRAGGING:
            return "Shift: constrain axis | Release to place"
        if self._state == _State.RUBBER_BAND:
            return "Shift: add to selection | Ctrl: toggle selection"
        if self._state == _State.HANDLE_DRAG:
            if self._handle_pos == HandlePosition.ROTATE:
                return "Shift: snap to 15° increments"
            return "Shift: proportional | Alt: from center | Ctrl+edge: skew"
        return "Click to select | Drag to move | Shift+click: add | Right-click: menu"

    # --- context menu ---

    def context_menu(self, event: object) -> bool:
        from PyQt6.QtGui import QContextMenuEvent
        from PyQt6.QtWidgets import QMenu

        if not isinstance(event, QContextMenuEvent):
            return False
        if self._scene is None or self._selection_manager is None:
            return False

        view = self._view
        if view is None:
            return False

        scene_pos = view.mapToScene(event.pos())

        # If right-click on an unselected item, select it first
        item = self._item_at(scene_pos)
        if item is not None and item not in self._selection_manager.items:
            self._selection_manager.select(item)

        menu = QMenu()
        has_sel = not self._selection_manager.is_empty

        cut_action = menu.addAction("Cut")
        if cut_action is not None:
            cut_action.setEnabled(has_sel)
        copy_action = menu.addAction("Copy")
        if copy_action is not None:
            copy_action.setEnabled(has_sel)
        menu.addAction("Paste")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        if delete_action is not None:
            delete_action.setEnabled(has_sel)
        duplicate_action = menu.addAction("Duplicate")
        if duplicate_action is not None:
            duplicate_action.setEnabled(has_sel)

        chosen = menu.exec(event.globalPos())
        if chosen is None:
            return True

        parent = view.parentWidget()
        text = chosen.text()
        if text == "Cut" and parent and hasattr(parent, "_edit_cut"):
            parent._edit_cut()  # noqa: SLF001
        elif text == "Copy" and parent and hasattr(parent, "_edit_copy"):
            parent._edit_copy()  # noqa: SLF001
        elif text == "Paste" and parent and hasattr(parent, "_edit_paste"):
            parent._edit_paste()  # noqa: SLF001
        elif text == "Delete" and parent and hasattr(parent, "_edit_delete"):
            parent._edit_delete()  # noqa: SLF001
        elif text == "Duplicate" and parent and hasattr(parent, "_edit_duplicate"):
            parent._edit_duplicate()  # noqa: SLF001

        return True

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
