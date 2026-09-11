"""HighlightTool — click-and-drag to draw highlight strokes.

Blur, Highlighter & Eyedropper PRD Section 3. The Tool Options Bar per 3.5: Highlight
Color, Stroke Width (10 to 80 px), Blend Mode, Stroke Style, then the tool's own Cap Style
toggles and the six preset colour swatches, and the shared Shadow toggle. Auto-Straighten
and Snap to Axis are not shown: the tool does not straighten strokes (Vector Item
Properties silence 7), and a control with nothing behind it cannot be greyed out (General
UI PRD 1.3). The colour's alpha is the opacity (3.7), so there is no opacity control.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QButtonGroup, QLabel, QToolBar, QToolButton

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import (
    DEFAULT_HIGHLIGHT_BLEND_MODE,
    DEFAULT_HIGHLIGHT_COLOR,
    DEFAULT_HIGHLIGHT_WIDTH,
    HIGHLIGHT_PRESET_COLORS,
    BorderStyle,
    StrokeCap,
)
from snapmock.items.highlight_item import HighlightItem
from snapmock.tools.base_tool import BaseTool

_CAP_STYLES: tuple[tuple[StrokeCap, str, str], ...] = (
    (StrokeCap.FLAT, "Flat", "Flat cap: the band ends at the endpoint"),
    (StrokeCap.ROUND, "Round", "Round cap: a half-circle beyond the endpoint"),
    (StrokeCap.SQUARE, "Square", "Square cap: a half-square beyond the endpoint"),
)
_SWATCH = 16
_CONTROL_HEIGHT = 26


def cap_icon(cap: StrokeCap, size: int = 16) -> QPixmap:
    """A short stroke drawn with *cap*, the toggle's preview icon (PRD 3.5)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = painter.pen()
    pen.setColor(QColor(90, 90, 90))
    pen.setWidth(max(4, size // 3))
    pen.setCapStyle(
        {
            StrokeCap.FLAT: Qt.PenCapStyle.FlatCap,
            StrokeCap.ROUND: Qt.PenCapStyle.RoundCap,
            StrokeCap.SQUARE: Qt.PenCapStyle.SquareCap,
        }[cap]
    )
    painter.setPen(pen)
    painter.drawLine(QPointF(size * 0.3, size / 2), QPointF(size * 0.7, size / 2))
    painter.end()
    return pixmap


class HighlightTool(BaseTool):
    """Interactive tool for drawing highlight strokes."""

    options_controls = (
        "highlight_color",
        "highlight_width",
        "blend_mode",
        "stroke_style",
        "tool",
        "shadow_enabled",
    )

    def __init__(self) -> None:
        super().__init__()
        self._item: HighlightItem | None = None
        self._creation_defaults = {
            "highlight_color": QColor(DEFAULT_HIGHLIGHT_COLOR),
            "highlight_width": DEFAULT_HIGHLIGHT_WIDTH,
            "blend_mode": DEFAULT_HIGHLIGHT_BLEND_MODE,
            "stroke_style": BorderStyle.SOLID,
            "stroke_cap": StrokeCap.FLAT,
            "shadow_enabled": False,
        }
        self._cap_buttons: dict[StrokeCap, QToolButton] = {}
        self._cap_group: QButtonGroup | None = None
        self._swatches: list[QToolButton] = []
        self._toolbar: QToolBar | None = None

    @property
    def tool_id(self) -> str:
        return "highlight"

    @property
    def display_name(self) -> str:
        return "Highlight"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def status_hint(self) -> str:
        return "Click and drag to highlight"

    # ------------------------------------------------------------ the bar

    def build_options_widgets(self, toolbar: QToolBar) -> None:
        """The Cap Style toggles and the six preset colour swatches (PRD 3.5)."""
        self._toolbar = toolbar
        toolbar.addWidget(QLabel(" Cap:"))
        group = QButtonGroup(toolbar)
        group.setExclusive(True)
        self._cap_buttons = {}
        for cap, name, tip in _CAP_STYLES:
            button = QToolButton()
            button.setCheckable(True)
            button.setIcon(QIcon(cap_icon(cap)))
            button.setToolTip(tip)
            button.setAccessibleName(f"{name} cap")
            button.setFixedSize(_CONTROL_HEIGHT, _CONTROL_HEIGHT)
            button.toggled.connect(lambda checked, c=cap: self._on_cap_toggled(c, checked))
            group.addButton(button)
            toolbar.addWidget(button)
            self._cap_buttons[cap] = button
        self._cap_group = group
        toolbar.addWidget(QLabel(" Presets:"))
        self._swatches = []
        for name, argb in HIGHLIGHT_PRESET_COLORS:
            swatch = QToolButton()
            pixmap = QPixmap(_SWATCH, _SWATCH)
            pixmap.fill(QColor(argb))
            swatch.setIcon(QIcon(pixmap))
            swatch.setToolTip(f"{name} highlight")
            swatch.setAccessibleName(f"{name} preset colour")
            swatch.setFixedSize(_CONTROL_HEIGHT - 4, _CONTROL_HEIGHT - 4)
            swatch.clicked.connect(lambda _c=False, a=argb: self._on_swatch_clicked(QColor(a)))
            toolbar.addWidget(swatch)
            self._swatches.append(swatch)
        self._sync_cap_buttons()

    @property
    def cap_buttons(self) -> dict[StrokeCap, QToolButton]:
        return dict(self._cap_buttons)

    @property
    def preset_swatches(self) -> list[QToolButton]:
        return list(self._swatches)

    def _sync_cap_buttons(self) -> None:
        current = self._creation_defaults.get("stroke_cap", StrokeCap.FLAT)
        for cap, button in self._cap_buttons.items():
            button.blockSignals(True)
            button.setChecked(cap is current)
            button.blockSignals(False)

    def _announce(self) -> None:
        window = self._window()
        manager = getattr(window, "tool_manager", None)
        if manager is not None:
            manager.tool_defaults_changed.emit(self.tool_id)

    def _on_cap_toggled(self, cap: StrokeCap, checked: bool) -> None:
        if not checked:
            return
        self._creation_defaults["stroke_cap"] = cap
        self._announce()

    def _on_swatch_clicked(self, color: QColor) -> None:
        self._creation_defaults["highlight_color"] = QColor(color)
        self._announce()

    def on_option_changed(self, key: str, value: Any) -> None:
        if key == "stroke_cap":
            self._sync_cap_buttons()

    def _window(self) -> Any:
        view = self._view
        return view.window() if view is not None else None

    # ------------------------------------------------------------ drawing

    def _scene_pos(self, event: QMouseEvent) -> QPointF:
        if self._scene is not None and self._scene.views():
            return self._scene.views()[0].mapToScene(event.pos())
        return QPointF()

    def _item_defaults(self) -> dict[str, Any]:
        """The creation defaults under the item's key names."""
        d = dict(self._creation_defaults)
        d["stroke_color"] = QColor(d.pop("highlight_color", QColor(DEFAULT_HIGHLIGHT_COLOR)))
        d["stroke_width"] = float(d.pop("highlight_width", DEFAULT_HIGHLIGHT_WIDTH))
        return d

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        pos = self._scene_pos(event)
        self._item = HighlightItem()
        self._item.apply_creation_defaults(self._item_defaults())
        self._item.setPos(pos)
        self._item.add_point(0, 0)
        self._scene.addItem(self._item)
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        pos = self._scene_pos(event)
        local = pos - self._item.pos()
        self._item.add_point(local.x(), local.y())
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        self._scene.removeItem(self._item)
        created_item = self._item
        self._item = None
        if len(created_item.points) > 2:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, created_item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                if self._selection_manager is not None:
                    self._selection_manager.select(created_item)
                self._switch_to_select()
        return True
