"""FreehandTool — click-and-drag to draw freehand paths."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.freehand_item import FreehandItem
from snapmock.tools.base_tool import BaseTool


class FreehandTool(BaseTool):
    """Interactive tool for freehand drawing."""

    def __init__(self) -> None:
        super().__init__()
        self._item: FreehandItem | None = None

    @property
    def tool_id(self) -> str:
        return "freehand"

    @property
    def display_name(self) -> str:
        return "Freehand"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    def _scene_pos(self, event: QMouseEvent) -> QPointF:
        if self._scene is not None and self._scene.views():
            return self._scene.views()[0].mapToScene(event.pos())
        return QPointF()

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        pos = self._scene_pos(event)
        self._item = FreehandItem()
        self._item.setPos(pos)
        self._item.add_point(QPointF(0, 0))
        self._scene.addItem(self._item)
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        pos = self._scene_pos(event)
        local = pos - self._item.pos()
        self._item.add_point(local)
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        self._scene.removeItem(self._item)
        if len(self._item.points) > 2:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, self._item, layer.layer_id)
                self._scene.command_stack.push(cmd)
        self._item = None
        return True
