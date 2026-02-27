"""SelectTool — click-select, drag-move, rubber-band multi-select."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.move_items import MoveItemsCommand
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.tools.base_tool import BaseTool


class SelectTool(BaseTool):
    """The default selection and move tool."""

    def __init__(self) -> None:
        super().__init__()
        self._dragging: bool = False
        self._drag_start: QPointF = QPointF()
        self._drag_items: list[SnapGraphicsItem] = []

    @property
    def tool_id(self) -> str:
        return "select"

    @property
    def display_name(self) -> str:
        return "Select"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.ArrowCursor

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or self._selection_manager is None:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        scene_pos = self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else None
        if scene_pos is None:
            return False

        item = self._scene.itemAt(scene_pos, self._scene.views()[0].transform())
        if item is not None and isinstance(item, SnapGraphicsItem):
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if shift:
                self._selection_manager.toggle(item)
            elif item not in self._selection_manager.items:
                self._selection_manager.select(item)
            # Start drag
            self._dragging = True
            self._drag_start = scene_pos
            self._drag_items = [
                i for i in self._selection_manager.items if isinstance(i, SnapGraphicsItem)
            ]
        else:
            self._selection_manager.deselect_all()
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if not self._dragging or self._scene is None:
            return False
        scene_pos = self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else None
        if scene_pos is None:
            return False
        delta = scene_pos - self._drag_start
        for item in self._drag_items:
            item.moveBy(delta.x(), delta.y())
        self._drag_start = scene_pos
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if not self._dragging or self._scene is None:
            return False
        scene_pos = self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else None
        if scene_pos is None:
            self._dragging = False
            return False
        total_delta = scene_pos - self._drag_start
        # Only push command if there's actual movement to commit
        # (The visual moves were already done in mouse_move; we undo them and let the command redo)
        if self._drag_items and (total_delta.x() != 0 or total_delta.y() != 0):
            cmd = MoveItemsCommand(self._drag_items, total_delta)
            self._scene.command_stack.push(cmd)
        self._dragging = False
        self._drag_items = []
        return True
