"""StampTool — click to place a stamp item."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.stamp_item import StampItem
from snapmock.tools.base_tool import BaseTool


class StampTool(BaseTool):
    """Click on the canvas to place a stamp."""

    @property
    def tool_id(self) -> str:
        return "stamp"

    @property
    def display_name(self) -> str:
        return "Stamp"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        scene_pos = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        item = StampItem()
        item.setPos(scene_pos)
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            cmd = AddItemCommand(self._scene, item, layer.layer_id)
            self._scene.command_stack.push(cmd)
        return True
