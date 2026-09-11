"""RectangleTool — click-and-drag to create rectangles."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import (
    DEFAULT_FILL_COLOR,
    DEFAULT_STROKE_COLOR,
    DEFAULT_STROKE_WIDTH,
    BorderStyle,
)
from snapmock.items.rectangle_item import RectangleItem
from snapmock.tools.base_tool import BaseTool


class RectangleTool(BaseTool):
    """Interactive tool for creating rectangles by click-and-drag."""

    # Tool Options Bar shared controls (General UI PRD 5.3)
    options_controls = (
        "stroke_color",
        "fill_color",
        "stroke_width",
        "stroke_style",
        "fill_opacity",
        "stroke_opacity",
        "shadow_enabled",
        "corner_radius",
    )

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._item: RectangleItem | None = None
        self._creation_defaults = {
            "stroke_color": QColor(DEFAULT_STROKE_COLOR),
            "fill_color": QColor(DEFAULT_FILL_COLOR),
            "stroke_width": DEFAULT_STROKE_WIDTH,
            "stroke_style": BorderStyle.SOLID,
            "fill_opacity": 1.0,
            "stroke_opacity": 1.0,
            "shadow_enabled": False,
            "corner_radius": 0.0,
        }

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
        self._start = self._snap_pos(
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._item = RectangleItem(rect=QRectF(0, 0, 0, 0))
        self._item.apply_creation_defaults(self._creation_defaults)
        self._item.setPos(self._start)
        self._scene.addItem(self._item)
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        current = self._snap_pos(
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
        created_item = self._item
        self._item = None
        # Only create if it has meaningful size
        if created_item.rect.width() > 2 and created_item.rect.height() > 2:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, created_item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                if self._selection_manager is not None:
                    self._selection_manager.select(created_item)
                self._switch_to_select()
        return True
