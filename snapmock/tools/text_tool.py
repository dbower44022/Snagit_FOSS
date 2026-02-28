"""TextTool — click to place a text item."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.text_item import TextItem
from snapmock.tools.base_tool import BaseTool


class TextTool(BaseTool):
    """Click on the canvas to place a text item."""

    @property
    def tool_id(self) -> str:
        return "text"

    @property
    def display_name(self) -> str:
        return "Text"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.IBeamCursor

    @property
    def status_hint(self) -> str:
        return "Click to place text | Drag to set text box width"

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        scene_pos = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        item = TextItem(text="Text", pos_x=scene_pos.x(), pos_y=scene_pos.y())
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            cmd = AddItemCommand(self._scene, item, layer.layer_id)
            self._scene.command_stack.push(cmd)
        return True
