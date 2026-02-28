"""CalloutTool — click to place a callout item."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.callout_item import CalloutItem
from snapmock.tools.base_tool import BaseTool


class CalloutTool(BaseTool):
    """Click on the canvas to place a callout."""

    @property
    def tool_id(self) -> str:
        return "callout"

    @property
    def display_name(self) -> str:
        return "Callout"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def status_hint(self) -> str:
        return "Click to place callout | Drag tail to point"

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        scene_pos = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        item = CalloutItem()
        item.setPos(scene_pos)
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            cmd = AddItemCommand(self._scene, item, layer.layer_id)
            self._scene.command_stack.push(cmd)
        return True
