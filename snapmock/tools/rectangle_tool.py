"""RectangleTool — click-and-drag to create rectangles."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.rectangle_item import RectangleItem
from snapmock.tools.base_tool import BaseTool


class RectangleTool(BaseTool):
    """Interactive tool for creating rectangles by click-and-drag."""

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._item: RectangleItem | None = None

    @property
    def tool_id(self) -> str:
        return "rectangle"

    @property
    def display_name(self) -> str:
        return "Rectangle"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def status_hint(self) -> str:
        return "Click and drag to draw rectangle | Shift: square"

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._start = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._item = RectangleItem(rect=QRectF(0, 0, 0, 0))
        self._item.setPos(self._start)
        self._scene.addItem(self._item)
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        current = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        rect = QRectF(self._start, current).normalized()
        self._item.setPos(rect.topLeft())
        self._item.rect = QRectF(0, 0, rect.width(), rect.height())
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        # Remove the preview item
        self._scene.removeItem(self._item)
        # Only create if it has meaningful size
        if self._item.rect.width() > 2 and self._item.rect.height() > 2:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, self._item, layer.layer_id)
                self._scene.command_stack.push(cmd)
        self._item = None
        return True
