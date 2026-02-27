"""LineTool — click-and-drag to create lines."""

from __future__ import annotations

from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.line_item import LineItem
from snapmock.tools.base_tool import BaseTool


class LineTool(BaseTool):
    """Interactive tool for creating lines by click-and-drag."""

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._item: LineItem | None = None

    @property
    def tool_id(self) -> str:
        return "line"

    @property
    def display_name(self) -> str:
        return "Line"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._start = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._item = LineItem(line=QLineF(QPointF(0, 0), QPointF(0, 0)))
        self._item.setPos(self._start)
        self._scene.addItem(self._item)
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        current = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        local_end = current - self._start
        self._item.line = QLineF(QPointF(0, 0), local_end)
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        self._scene.removeItem(self._item)
        if self._item.line.length() > 2:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, self._item, layer.layer_id)
                self._scene.command_stack.push(cmd)
        self._item = None
        return True
