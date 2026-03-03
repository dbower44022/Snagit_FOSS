"""CalloutTool — drag to place tail tip then position bubble, or click for defaults."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QKeyEvent, QMouseEvent, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QLabel,
    QToolBar,
    QToolButton,
)

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    BubbleShape,
    TailStyle,
    VerticalAlign,
)
from snapmock.items.callout_item import CalloutItem
from snapmock.tools.base_tool import BaseTool

_MIN_DRAG = 20.0
_DEFAULT_BUBBLE_W = 200.0
_DEFAULT_BUBBLE_H = 80.0
_DEFAULT_OFFSET = 80.0


class CalloutTool(BaseTool):
    """Drag to place tail tip then position bubble, or click for quick creation."""

    def __init__(self) -> None:
        super().__init__()
        self._drag_start: QPointF | None = None
        self._is_dragging: bool = False
        self._preview_line: QGraphicsLineItem | None = None
        self._preview_dot: QGraphicsEllipseItem | None = None
        # Creation defaults (pre-configurable via PropertyPanel)
        self._creation_defaults = {
            "font_family": DEFAULT_FONT_FAMILY,
            "font_size": DEFAULT_FONT_SIZE,
            "bold": False,
            "italic": False,
            "underline": False,
            "text_color": QColor(Qt.GlobalColor.black),
            "bg_color": QColor("#FFFFCC"),
            "border_color": QColor("#333333"),
            "border_width": 2.0,
            "border_radius": 12.0,
            "padding": 10.0,
            "vertical_align": VerticalAlign.TOP,
        }

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
        if self._is_dragging:
            return "Drag to position the bubble | Shift: constrain tail angle | Release to create"
        return "Click to place callout tail tip, then drag to position the bubble"

    @property
    def is_active_operation(self) -> bool:
        return self._drag_start is not None

    def build_options_widgets(self, toolbar: QToolBar) -> None:
        # Bubble shape
        toolbar.addWidget(QLabel(" Shape:"))
        self._opt_shape = QComboBox()
        self._opt_shape.setMaximumWidth(120)
        for shape in BubbleShape:
            self._opt_shape.addItem(shape.value.replace("_", " ").title(), shape)
        toolbar.addWidget(self._opt_shape)

        toolbar.addSeparator()

        # Tail style
        toolbar.addWidget(QLabel(" Tail:"))
        for style in TailStyle:
            btn = QToolButton()
            btn.setText(style.value.title())
            btn.setCheckable(True)
            if style == TailStyle.STRAIGHT:
                btn.setChecked(True)
            btn.setToolTip(f"{style.value.title()} tail")
            toolbar.addWidget(btn)

        toolbar.addSeparator()

        # Tail width
        toolbar.addWidget(QLabel(" Tail W:"))
        self._opt_tail_w = QDoubleSpinBox()
        self._opt_tail_w.setRange(4.0, 100.0)
        self._opt_tail_w.setDecimals(0)
        self._opt_tail_w.setSuffix(" px")
        self._opt_tail_w.setValue(20.0)
        self._opt_tail_w.setMaximumWidth(80)
        toolbar.addWidget(self._opt_tail_w)

        toolbar.addSeparator()

        # Border width
        toolbar.addWidget(QLabel(" Border:"))
        self._opt_border_w = QDoubleSpinBox()
        self._opt_border_w.setRange(0.0, 20.0)
        self._opt_border_w.setDecimals(1)
        self._opt_border_w.setSuffix(" px")
        self._opt_border_w.setValue(2.0)
        self._opt_border_w.setMaximumWidth(80)
        toolbar.addWidget(self._opt_border_w)

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        view = self._view
        if view is None:
            return False

        scene_pos = view.mapToScene(event.pos())
        self._drag_start = scene_pos
        self._is_dragging = False

        # Show a small dot at the tail tip position
        dot = QGraphicsEllipseItem(-4, -4, 8, 8)
        dot.setPen(QPen(QColor("#FF0000"), 1))
        dot.setBrush(QBrush(QColor("#FF0000")))
        dot.setPos(scene_pos)
        self._scene.addItem(dot)
        self._preview_dot = dot

        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._drag_start is None or self._scene is None:
            return False
        view = self._view
        if view is None:
            return False

        current = view.mapToScene(event.pos())
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        # Apply angle constraint if Shift is held
        if shift:
            current = self._constrain_angle(self._drag_start, current)

        dx = abs(current.x() - self._drag_start.x())
        dy = abs(current.y() - self._drag_start.y())
        if not self._is_dragging and (dx > _MIN_DRAG or dy > _MIN_DRAG):
            self._is_dragging = True

        # Update preview line
        if self._is_dragging:
            if self._preview_line is None:
                line = QGraphicsLineItem()
                pen = QPen(QColor("#0078d7"), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                line.setPen(pen)
                self._scene.addItem(line)
                self._preview_line = line
            from PyQt6.QtCore import QLineF

            self._preview_line.setLine(QLineF(self._drag_start, current))

        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._drag_start is None or self._scene is None:
            return False
        view = self._view
        if view is None:
            self._cleanup()
            return False

        scene_pos = view.mapToScene(event.pos())
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if shift:
            scene_pos = self._constrain_angle(self._drag_start, scene_pos)

        self._cleanup_preview()

        tail_tip = self._drag_start
        dx = abs(scene_pos.x() - tail_tip.x())
        dy = abs(scene_pos.y() - tail_tip.y())

        if self._is_dragging and (dx >= _MIN_DRAG or dy >= _MIN_DRAG):
            # Drag-to-create: tail_tip at press, bubble at release
            bubble_cx = scene_pos.x()
            bubble_cy = scene_pos.y()
            bw = max(_DEFAULT_BUBBLE_W, dx * 0.8)
            bh = max(60.0, dy * 0.5)
            bubble_rect = QRectF(
                bubble_cx - bw / 2, bubble_cy - bh / 2, bw, bh
            )
            item = CalloutItem(text="", rect=bubble_rect, tail_tip=tail_tip)
        else:
            # Click-to-create: default bubble 80px above-right of click
            bubble_rect = QRectF(
                tail_tip.x() + _DEFAULT_OFFSET * 0.3,
                tail_tip.y() - _DEFAULT_OFFSET - _DEFAULT_BUBBLE_H,
                _DEFAULT_BUBBLE_W,
                _DEFAULT_BUBBLE_H,
            )
            item = CalloutItem(text="", rect=bubble_rect, tail_tip=tail_tip)

        self._apply_creation_defaults(item)
        layer = self._scene.layer_manager.active_layer
        if layer is not None:
            cmd = AddItemCommand(self._scene, item, layer.layer_id)
            self._scene.command_stack.push(cmd)
            # Switch to text tool and start editing
            self._enter_text_editing(item)

        self._drag_start = None
        self._is_dragging = False
        return True

    def key_press(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Escape and self._drag_start is not None:
            self._cleanup()
            return True
        return False

    def cancel(self) -> None:
        self._cleanup()

    def deactivate(self) -> None:
        self._cleanup()
        super().deactivate()

    def _cleanup_preview(self) -> None:
        if self._preview_line is not None and self._scene is not None:
            self._scene.removeItem(self._preview_line)
            self._preview_line = None
        if self._preview_dot is not None and self._scene is not None:
            self._scene.removeItem(self._preview_dot)
            self._preview_dot = None

    def _cleanup(self) -> None:
        self._cleanup_preview()
        self._drag_start = None
        self._is_dragging = False

    def _apply_creation_defaults(self, item: CalloutItem) -> None:
        """Apply user-configured creation defaults to a newly constructed item."""
        d = self._creation_defaults
        font = QFont(d.get("font_family", DEFAULT_FONT_FAMILY))
        font.setPointSize(d.get("font_size", DEFAULT_FONT_SIZE))
        font.setBold(d.get("bold", False))
        font.setItalic(d.get("italic", False))
        font.setUnderline(d.get("underline", False))
        item.font = font
        item.text_color = QColor(d.get("text_color", QColor(Qt.GlobalColor.black)))
        item.bg_color = QColor(d.get("bg_color", QColor("#FFFFCC")))
        item.border_color = QColor(d.get("border_color", QColor("#333333")))
        item.border_width = d.get("border_width", 2.0)
        item.border_radius = d.get("border_radius", 12.0)
        item.padding = d.get("padding", 10.0)
        item.vertical_align = d.get("vertical_align", VerticalAlign.TOP)

    def _enter_text_editing(self, item: CalloutItem) -> None:
        """Switch to text tool and start editing the newly created callout."""
        if self._scene is None:
            return
        views = self._scene.views()
        if not views:
            return
        view = views[0]
        main_window = view.window()
        if main_window is not None and hasattr(main_window, "tool_manager"):
            tm = main_window.tool_manager
            # Select the item first
            if self._selection_manager is not None:
                self._selection_manager.select_items([item])
            tm.activate_tool("text")

    @staticmethod
    def _constrain_angle(origin: QPointF, target: QPointF) -> QPointF:
        """Constrain angle to 15-degree increments."""
        dx = target.x() - origin.x()
        dy = target.y() - origin.y()
        dist = math.hypot(dx, dy)
        if dist < 1:
            return target
        angle = math.atan2(dy, dx)
        step = math.radians(15)
        angle = round(angle / step) * step
        return QPointF(
            origin.x() + dist * math.cos(angle),
            origin.y() + dist * math.sin(angle),
        )
