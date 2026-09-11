"""ArrowTool — click-and-drag to create arrows."""

from __future__ import annotations

from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import (
    DEFAULT_STROKE_COLOR,
    DEFAULT_STROKE_WIDTH,
    BorderStyle,
    HeadSize,
    HeadStyle,
)
from snapmock.items.arrow_item import ArrowItem
from snapmock.tools.base_tool import BaseTool


class ArrowTool(BaseTool):
    """Interactive tool for creating arrows by click-and-drag."""

    # Tool Options Bar shared controls (General UI PRD 5.3)
    # The shared set, then the head controls of Basic Shape PRD 4.7 (Line Style is not
    # shown: only Straight is drawn, Vector Item Properties decision 3)
    options_controls = (
        "stroke_color",
        "stroke_width",
        "stroke_style",
        "stroke_opacity",
        "shadow_enabled",
        "head_style",
        "tail_style",
        "head_size",
        "head_size_custom",
    )

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._item: ArrowItem | None = None
        self._creation_defaults = {
            "stroke_color": QColor(DEFAULT_STROKE_COLOR),
            "stroke_width": DEFAULT_STROKE_WIDTH,
            "stroke_style": BorderStyle.SOLID,
            "stroke_opacity": 1.0,
            "shadow_enabled": False,
            "head_style": HeadStyle.OPEN,
            "tail_style": HeadStyle.NONE,
            "head_size": HeadSize.MEDIUM,
            "head_size_custom": 0.0,
        }

    @property
    def tool_id(self) -> str:
        return "arrow"

    @property
    def display_name(self) -> str:
        return "Arrow"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def status_hint(self) -> str:
        return "Click and drag to draw arrow | Shift: constrain angle"

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._start = self._snap_pos(
            self._scene.views()[0].mapToScene(event.pos()) if self._scene.views() else QPointF()
        )
        self._item = ArrowItem(line=QLineF(QPointF(0, 0), QPointF(0, 0)))
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
        local_end = current - self._start
        self._item.line = QLineF(QPointF(0, 0), local_end)
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        self._scene.removeItem(self._item)
        created_item = self._item
        self._item = None
        if created_item.line.length() > 2:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, created_item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                if self._selection_manager is not None:
                    self._selection_manager.select(created_item)
                self._switch_to_select()
        return True
