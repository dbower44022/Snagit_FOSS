"""BlurTool — click-and-drag to create blur regions (Blur PRD Section 2).

The drag draws a rectangle or an ellipse region (2.3, 2.4), Shift constraining it to a
square or a circle and Alt drawing from the centre, with the effect shown live beneath it;
a region under 16 square pixels is an accidental click. The Tool Options Bar of 2.6: the
Blur Mode toggles, the intensity slider whose label follows the mode (Blur Radius 1 to 50,
Pixel Size 2 to 100, hidden for Solid Fill), Fill Color for Solid Fill, the Region Shape
toggles (Rectangle, Ellipse; Freeform is not built, Basic Shape remainder decision 4),
Corner Radius for a rectangle, Feather, Invert Mask, and Opacity.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QAction, QColor, QMouseEvent
from PyQt6.QtWidgets import QButtonGroup, QLabel, QSlider, QSpinBox, QToolBar, QToolButton

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import (
    BLUR_FEATHER_MAX,
    BLUR_PIXEL_SIZE_MAX,
    BLUR_PIXEL_SIZE_MIN,
    BLUR_RADIUS_MAX,
    BLUR_RADIUS_MIN,
    CORNER_RADIUS_MAX,
    DEFAULT_BLUR_FILL_COLOR,
    BlurMode,
    BlurRegionShape,
)
from snapmock.items.blur_item import BlurItem
from snapmock.tools.base_tool import BaseTool

MIN_AREA = 16.0
"""A region under this many square pixels is an accidental click (2.3)."""

_MODES: tuple[tuple[BlurMode, str], ...] = (
    (BlurMode.GAUSSIAN, "Gaussian Blur"),
    (BlurMode.PIXELATE, "Pixelate"),
    (BlurMode.SOLID, "Solid Fill"),
)
_SHAPES: tuple[tuple[BlurRegionShape, str], ...] = (
    (BlurRegionShape.RECTANGLE, "Rectangle"),
    (BlurRegionShape.ELLIPSE, "Ellipse"),
)
_CONTROL_HEIGHT = 26


class BlurTool(BaseTool):
    """Interactive tool for creating blur regions."""

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF = QPointF()
        self._item: BlurItem | None = None
        self._mode_buttons: dict[BlurMode, QToolButton] = {}
        self._shape_buttons: dict[BlurRegionShape, QToolButton] = {}
        self._intensity_label: QLabel | None = None
        self._intensity_slider: QSlider | None = None
        self._intensity_spin: QSpinBox | None = None
        self._fill_picker: Any = None
        self._corner_spin: QSpinBox | None = None
        self._feather_spin: QSpinBox | None = None
        self._invert_button: QToolButton | None = None
        self._opacity_spin: QSpinBox | None = None
        self._groups: dict[str, list[QAction]] = {}
        self._syncing = False
        self._creation_defaults = {
            "blur_mode": BlurMode.GAUSSIAN,
            "region_shape": BlurRegionShape.RECTANGLE,
            "blur_radius": 10.0,
            "pixel_size": 10,
            "fill_color": QColor(DEFAULT_BLUR_FILL_COLOR),
            "corner_radius": 0.0,
            "feather": 0.0,
            "invert_mask": False,
            "opacity": 1.0,
        }

    @property
    def tool_id(self) -> str:
        return "blur"

    @property
    def display_name(self) -> str:
        return "Blur"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    @property
    def is_active_operation(self) -> bool:
        return self._item is not None

    @property
    def preview(self) -> BlurItem | None:
        return self._item

    @property
    def status_hint(self) -> str:
        """The hints of 2.10 for the rectangle and ellipse regions."""
        item = self._item
        if item is None:
            return "Click and drag to define blur region. Shift: constrain. Alt: from center."
        mode = dict(_MODES)[item.blur_mode]
        detail = ""
        if item.blur_mode is BlurMode.GAUSSIAN:
            detail = f" | Radius: {item.blur_radius:.0f}"
        elif item.blur_mode is BlurMode.PIXELATE:
            detail = f" | Pixel size: {item.pixel_size}"
        rect = item.rect
        return (
            f"W: {rect.width():.0f} H: {rect.height():.0f} | Mode: {mode}{detail} | "
            "Release to apply."
        )

    def _show_hint(self) -> None:
        view = self._view
        window = view.window() if view is not None else None
        show = getattr(window, "show_status_hint", None)
        if callable(show):
            show(self.status_hint)

    # ------------------------------------------------------------ the options bar (2.6)

    def _spin_slider(
        self, toolbar: QToolBar, label: str, low: int, high: int, suffix: str, key: str
    ) -> tuple[QLabel, QSlider, QSpinBox, list[QAction]]:
        text = QLabel(f" {label}:")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setFixedWidth(80)
        slider.setAccessibleName(f"{label} slider")
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setSuffix(suffix)
        spin.setMaximumWidth(64)
        spin.setMaximumHeight(_CONTROL_HEIGHT)
        spin.setAccessibleName(label)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        spin.valueChanged.connect(lambda v, k=key: self._on_value(k, v))
        actions = [toolbar.addWidget(w) for w in (text, slider, spin)]
        return text, slider, spin, [a for a in actions if a is not None]

    def _toggles(
        self, toolbar: QToolBar, entries: tuple[tuple[Any, str], ...], suffix: str, key: str
    ) -> dict[Any, QToolButton]:
        group = QButtonGroup(toolbar)
        group.setExclusive(True)
        buttons: dict[Any, QToolButton] = {}
        for value, name in entries:
            button = QToolButton()
            button.setCheckable(True)
            button.setText(name)
            button.setToolTip(name)
            button.setAccessibleName(f"{name} {suffix}")
            button.setMaximumHeight(_CONTROL_HEIGHT)
            button.toggled.connect(
                lambda checked, v=value, k=key: self._on_value(k, v) if checked else None
            )
            group.addButton(button)
            toolbar.addWidget(button)
            buttons[value] = button
        return buttons

    def build_options_widgets(self, toolbar: QToolBar) -> None:
        from snapmock.ui.color_picker import ColorPicker

        self._groups = {}
        toolbar.addWidget(QLabel(" Mode:"))
        self._mode_buttons = self._toggles(toolbar, _MODES, "mode", "blur_mode")
        label, slider, spin, actions = self._spin_slider(
            toolbar, "Blur Radius", int(BLUR_RADIUS_MIN), int(BLUR_RADIUS_MAX), " px", "intensity"
        )
        self._intensity_label, self._intensity_slider, self._intensity_spin = label, slider, spin
        self._groups["intensity"] = actions
        fill_label = toolbar.addWidget(QLabel(" Fill:"))
        picker = ColorPicker(swatch_size=24)
        picker.setToolTip("Fill colour for Solid Fill")
        picker.setAccessibleName("Fill color")
        picker.color_changed.connect(lambda c: self._on_value("fill_color", QColor(c)))
        fill_action = toolbar.addWidget(picker)
        self._fill_picker = picker
        self._groups["fill"] = [a for a in (fill_label, fill_action) if a is not None]
        toolbar.addWidget(QLabel(" Shape:"))
        self._shape_buttons = self._toggles(toolbar, _SHAPES, "region", "region_shape")
        _l, _s, self._corner_spin, actions = self._spin_slider(
            toolbar, "Corner Radius", 0, int(CORNER_RADIUS_MAX), " px", "corner_radius"
        )
        self._groups["corner"] = actions
        _l, _s, self._feather_spin, _a = self._spin_slider(
            toolbar, "Feather", 0, int(BLUR_FEATHER_MAX), " px", "feather"
        )
        invert = QToolButton()
        invert.setCheckable(True)
        invert.setText("Invert")
        invert.setToolTip("Invert Mask: obscure everything outside the region")
        invert.setAccessibleName("Invert mask")
        invert.setMaximumHeight(_CONTROL_HEIGHT)
        invert.toggled.connect(lambda checked: self._on_value("invert_mask", bool(checked)))
        toolbar.addWidget(invert)
        self._invert_button = invert
        _l, _s, self._opacity_spin, _a = self._spin_slider(
            toolbar, "Opacity", 0, 100, "%", "opacity"
        )
        self._sync_controls()

    @property
    def mode_buttons(self) -> dict[BlurMode, QToolButton]:
        return dict(self._mode_buttons)

    @property
    def shape_buttons(self) -> dict[BlurRegionShape, QToolButton]:
        return dict(self._shape_buttons)

    @property
    def intensity_label(self) -> QLabel | None:
        return self._intensity_label

    @property
    def intensity_spin(self) -> QSpinBox | None:
        return self._intensity_spin

    @property
    def invert_button(self) -> QToolButton | None:
        return self._invert_button

    def control_actions(self) -> dict[str, list[QAction]]:
        return {k: list(v) for k, v in self._groups.items()}

    def _on_value(self, key: str, value: Any) -> None:
        if self._syncing:
            return
        d = self._creation_defaults
        if key == "intensity":
            if d.get("blur_mode") is BlurMode.PIXELATE:
                d["pixel_size"] = int(value)
            else:
                d["blur_radius"] = float(value)
        elif key == "opacity":
            d["opacity"] = int(value) / 100.0
        elif key in ("corner_radius", "feather"):
            d[key] = float(value)
        else:
            d[key] = value
        self._sync_controls()
        view = self._view
        window: Any = view.window() if view is not None else None
        manager = getattr(window, "tool_manager", None)
        if manager is not None:
            manager.tool_defaults_changed.emit(self.tool_id)

    def _sync_controls(self) -> None:
        """Show the controls the mode and the shape use, holding the defaults (2.6)."""
        d = self._creation_defaults
        mode = d.get("blur_mode", BlurMode.GAUSSIAN)
        shape = d.get("region_shape", BlurRegionShape.RECTANGLE)
        self._syncing = True
        try:
            for mode_value, button in self._mode_buttons.items():
                button.setChecked(mode_value is mode)
            for shape_value, button in self._shape_buttons.items():
                button.setChecked(shape_value is shape)
            if self._intensity_spin is not None and self._intensity_slider is not None:
                if mode is BlurMode.PIXELATE:
                    low, high = int(BLUR_PIXEL_SIZE_MIN), int(BLUR_PIXEL_SIZE_MAX)
                    value, label = int(d.get("pixel_size", 10)), "Pixel Size"
                else:
                    low, high = int(BLUR_RADIUS_MIN), int(BLUR_RADIUS_MAX)
                    value, label = int(round(float(d.get("blur_radius", 10.0)))), "Blur Radius"
                for widget in (self._intensity_spin, self._intensity_slider):
                    widget.setRange(low, high)
                    widget.setValue(value)
                self._intensity_spin.setAccessibleName(label)
                self._intensity_slider.setAccessibleName(f"{label} slider")
                if self._intensity_label is not None:
                    self._intensity_label.setText(f" {label}:")
            if self._fill_picker is not None:
                self._fill_picker.color = QColor(d.get("fill_color", DEFAULT_BLUR_FILL_COLOR))
            if self._corner_spin is not None:
                self._corner_spin.setValue(int(round(float(d.get("corner_radius", 0.0)))))
            if self._feather_spin is not None:
                self._feather_spin.setValue(int(round(float(d.get("feather", 0.0)))))
            if self._invert_button is not None:
                self._invert_button.setChecked(bool(d.get("invert_mask")))
            if self._opacity_spin is not None:
                self._opacity_spin.setValue(int(round(float(d.get("opacity", 1.0)) * 100)))
        finally:
            self._syncing = False
        visible = {
            "intensity": mode is not BlurMode.SOLID,
            "fill": mode is BlurMode.SOLID,
            "corner": shape is BlurRegionShape.RECTANGLE,
        }
        for group, actions in self._groups.items():
            for action in actions:
                action.setVisible(visible.get(group, True))

    def on_option_changed(self, key: str, value: Any) -> None:
        self._sync_controls()

    # ------------------------------------------------------------ drawing (2.3)

    def _scene_pos(self, event: QMouseEvent) -> QPointF:
        if self._scene is not None and self._scene.views():
            return self._scene.views()[0].mapToScene(event.pos())
        return QPointF()

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._start = self._snap_pos(self._scene_pos(event))
        self._item = BlurItem(rect=QRectF(0, 0, 0, 0))
        self._item.apply_creation_defaults(self._creation_defaults)
        self._item.setPos(self._start)
        self._scene.addItem(self._item)
        self._show_hint()
        return True

    def region_for(
        self, start: QPointF, current: QPointF, modifiers: Qt.KeyboardModifier
    ) -> QRectF:
        """The drawn region in scene coordinates: Shift makes a square or a circle, Alt
        draws from the centre (2.3)."""
        dx = current.x() - start.x()
        dy = current.y() - start.y()
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            side = max(abs(dx), abs(dy))
            dx = side if dx >= 0 else -side
            dy = side if dy >= 0 else -side
        if modifiers & Qt.KeyboardModifier.AltModifier:
            return QRectF(start.x() - abs(dx), start.y() - abs(dy), 2 * abs(dx), 2 * abs(dy))
        return QRectF(start, QPointF(start.x() + dx, start.y() + dy)).normalized()

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        current = self._snap_pos(self._scene_pos(event))
        rect = self.region_for(self._start, current, event.modifiers())
        self._item.setPos(rect.topLeft())
        self._item.rect = QRectF(0, 0, rect.width(), rect.height())
        self._show_hint()
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._item is None or self._scene is None:
            return False
        self._scene.removeItem(self._item)
        created_item = self._item
        self._item = None
        rect = created_item.rect
        if rect.width() * rect.height() >= MIN_AREA:
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, created_item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                if self._selection_manager is not None:
                    self._selection_manager.select(created_item)
                self._switch_to_select()
        self._show_hint()
        return True

    def cancel(self) -> None:
        if self._item is not None and self._scene is not None and self._item.scene() is not None:
            self._scene.removeItem(self._item)
        self._item = None
