"""NumberedStepTool — click to place numbered step items."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.tools.base_tool import BaseTool


class NumberedStepTool(BaseTool):
    """Click to place incrementing numbered step markers."""

    def __init__(self) -> None:
        super().__init__()
        self._next_number: int = 1

    @property
    def tool_id(self) -> str:
        return "numbered_step"

    @property
    def display_name(self) -> str:
        return "Numbered Step"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    def activate(self, scene: object, selection_manager: object) -> None:
        super().activate(scene, selection_manager)  # type: ignore[arg-type]
        self._next_number = 1

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        scene_pos = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        item = NumberedStepItem(number=self._next_number)
        item.setPos(scene_pos)
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            cmd = AddItemCommand(self._scene, item, layer.layer_id)
            self._scene.command_stack.push(cmd)
            self._next_number += 1
        return True
