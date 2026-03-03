"""EllipseTool — click-and-drag to create ellipses."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import (
    DEFAULT_FILL_COLOR,
    DEFAULT_STROKE_COLOR,
    DEFAULT_STROKE_WIDTH,
)
from snapmock.items.ellipse_item import EllipseItem
from snapmock.tools.base_tool import BaseTool


class EllipseTool(BaseTool):
    """Interactive tool for creating ellipses by click-and-drag."""

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._item: EllipseItem | None = None
        self._creation_defaults = {
            "stroke_color": QColor(DEFAULT_STROKE_COLOR),
            "fill_color": QColor(DEFAULT_FILL_COLOR),
            "stroke_width": DEFAULT_STROKE_WIDTH,
            "opacity_pct": 100.0,
        }

    @property
    def tool_id(self) -> str:
        return "ellipse"

    @property
    def display_name(self) -> str:
        return "Ellipse"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def status_hint(self) -> str:
        return "Click and drag to draw ellipse | Shift: circle"

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._start = (
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._item = EllipseItem(rect=QRectF(0, 0, 0, 0))
        self._item.stroke_color = self._creation_defaults["stroke_color"]
        self._item.fill_color = self._creation_defaults["fill_color"]
        self._item.stroke_width = self._creation_defaults["stroke_width"]
        self._item.setOpacity(self._creation_defaults["opacity_pct"] / 100.0)
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
        self._scene.removeItem(self._item)
        created_item = self._item
        self._item = None
        if created_item.rect.width() > 2 and created_item.rect.height() > 2:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, created_item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                if self._selection_manager is not None:
                    self._selection_manager.select(created_item)
                self._switch_to_select()
        return True
