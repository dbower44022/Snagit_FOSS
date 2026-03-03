"""PropertyPanel — dock widget showing selected item properties."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from snapmock.commands.modify_property import ModifyPropertyCommand
from snapmock.commands.move_item_layer import MoveItemToLayerCommand
from snapmock.commands.scale_geometry_command import ScaleGeometryCommand
from snapmock.config.constants import VerticalAlign
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.callout_item import CalloutItem
from snapmock.items.text_item import TextItem
from snapmock.items.vector_item import VectorItem
from snapmock.ui.collapsible_section import CollapsibleSection
from snapmock.ui.color_picker import ColorPicker

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsItem

    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager
    from snapmock.tools.tool_manager import ToolManager


class PropertyPanel(QDockWidget):
    """Dockable panel showing properties of the selected item(s)."""

    def __init__(
        self,
        selection_manager: SelectionManager,
        scene: SnapScene,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Properties", parent)
        self._selection_manager = selection_manager
        self._scene = scene
        self._updating = False
        self._tool_manager: ToolManager | None = None
        self._active_tool_id: str = ""

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        # Scroll area wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(2)

        # --- Transform section ---
        self._transform_section = CollapsibleSection("Transform")
        self._x_spin = self._make_double_spin(-99999.0, 99999.0, 1, " px")
        self._y_spin = self._make_double_spin(-99999.0, 99999.0, 1, " px")
        self._w_spin = self._make_double_spin(1.0, 99999.0, 1, " px")
        self._h_spin = self._make_double_spin(1.0, 99999.0, 1, " px")
        self._rot_spin = self._make_double_spin(-360.0, 360.0, 1, "\u00b0")
        self._transform_section.add_row("X:", self._x_spin)
        self._transform_section.add_row("Y:", self._y_spin)
        self._transform_section.add_row("W:", self._w_spin)
        self._transform_section.add_row("H:", self._h_spin)
        self._transform_section.add_row("Rotation:", self._rot_spin)
        self._main_layout.addWidget(self._transform_section)

        # --- Appearance section ---
        self._appearance_section = CollapsibleSection("Appearance")

        self._stroke_color_picker = ColorPicker(QColor("black"))
        self._appearance_section.add_row("Stroke:", self._stroke_color_picker)

        stroke_w_container = QWidget()
        stroke_w_layout = QHBoxLayout(stroke_w_container)
        stroke_w_layout.setContentsMargins(0, 0, 0, 0)
        self._stroke_w_slider = QSlider(Qt.Orientation.Horizontal)
        self._stroke_w_slider.setRange(0, 100)
        self._stroke_w_spin = QDoubleSpinBox()
        self._stroke_w_spin.setRange(0.0, 100.0)
        self._stroke_w_spin.setDecimals(1)
        stroke_w_layout.addWidget(self._stroke_w_slider)
        stroke_w_layout.addWidget(self._stroke_w_spin)
        self._appearance_section.add_row("Width:", stroke_w_container)

        self._fill_color_picker = ColorPicker(QColor("transparent"))
        self._no_fill_check = QCheckBox("No fill")
        fill_container = QWidget()
        fill_layout = QHBoxLayout(fill_container)
        fill_layout.setContentsMargins(0, 0, 0, 0)
        fill_layout.addWidget(self._fill_color_picker)
        fill_layout.addWidget(self._no_fill_check)
        self._appearance_section.add_row("Fill:", fill_container)

        opacity_container = QWidget()
        opacity_layout = QHBoxLayout(opacity_container)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_spin = QSpinBox()
        self._opacity_spin.setRange(0, 100)
        self._opacity_spin.setSuffix("%")
        opacity_layout.addWidget(self._opacity_slider)
        opacity_layout.addWidget(self._opacity_spin)
        self._appearance_section.add_row("Opacity:", opacity_container)

        self._main_layout.addWidget(self._appearance_section)

        # --- Text section ---
        self._text_section = CollapsibleSection("Text")

        self._font_combo = QFontComboBox()
        self._text_section.add_row("Font:", self._font_combo)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(1, 200)
        self._font_size_spin.setSuffix(" pt")
        self._font_size_spin.setKeyboardTracking(False)
        self._text_section.add_row("Size:", self._font_size_spin)

        style_container = QWidget()
        style_layout = QHBoxLayout(style_container)
        style_layout.setContentsMargins(0, 0, 0, 0)
        self._bold_check = QCheckBox("Bold")
        self._italic_check = QCheckBox("Italic")
        self._underline_check = QCheckBox("Underline")
        style_layout.addWidget(self._bold_check)
        style_layout.addWidget(self._italic_check)
        style_layout.addWidget(self._underline_check)
        self._text_section.add_row("Style:", style_container)

        self._text_color_picker = ColorPicker(QColor("black"))
        self._text_section.add_row("Color:", self._text_color_picker)

        self._main_layout.addWidget(self._text_section)

        # --- Text Box section (TextItem only) ---
        self._text_box_section = CollapsibleSection("Text Box")

        self._text_bg_color_picker = ColorPicker(QColor("transparent"))
        self._no_bg_check = QCheckBox("No background")
        text_bg_container = QWidget()
        text_bg_layout = QHBoxLayout(text_bg_container)
        text_bg_layout.setContentsMargins(0, 0, 0, 0)
        text_bg_layout.addWidget(self._text_bg_color_picker)
        text_bg_layout.addWidget(self._no_bg_check)
        self._text_box_section.add_row("Background:", text_bg_container)

        self._text_border_color_picker = ColorPicker(QColor("transparent"))
        self._text_box_section.add_row("Border:", self._text_border_color_picker)

        self._text_border_w_spin = QDoubleSpinBox()
        self._text_border_w_spin.setRange(0.0, 20.0)
        self._text_border_w_spin.setDecimals(1)
        self._text_border_w_spin.setSuffix(" px")
        self._text_border_w_spin.setKeyboardTracking(False)
        self._text_box_section.add_row("Border width:", self._text_border_w_spin)

        self._text_corner_radius_spin = QDoubleSpinBox()
        self._text_corner_radius_spin.setRange(0.0, 50.0)
        self._text_corner_radius_spin.setDecimals(1)
        self._text_corner_radius_spin.setSuffix(" px")
        self._text_corner_radius_spin.setKeyboardTracking(False)
        self._text_box_section.add_row("Corner radius:", self._text_corner_radius_spin)

        self._text_padding_spin = QDoubleSpinBox()
        self._text_padding_spin.setRange(0.0, 50.0)
        self._text_padding_spin.setDecimals(1)
        self._text_padding_spin.setSuffix(" px")
        self._text_padding_spin.setKeyboardTracking(False)
        self._text_box_section.add_row("Padding:", self._text_padding_spin)

        self._text_valign_combo = QComboBox()
        self._text_valign_combo.addItem("Top", VerticalAlign.TOP)
        self._text_valign_combo.addItem("Center", VerticalAlign.CENTER)
        self._text_valign_combo.addItem("Bottom", VerticalAlign.BOTTOM)
        self._text_box_section.add_row("Vertical align:", self._text_valign_combo)

        self._text_auto_size_check = QCheckBox("Auto-size height")
        self._text_box_section.add_row("", self._text_auto_size_check)

        self._main_layout.addWidget(self._text_box_section)

        # --- Item Info section ---
        self._info_section = CollapsibleSection("Item Info")
        self._type_label = QLabel("")
        self._layer_combo = QComboBox()
        self._locked_check = QCheckBox("Locked")
        self._info_section.add_row("Type:", self._type_label)
        self._info_section.add_row("Layer:", self._layer_combo)
        self._info_section.add_row("", self._locked_check)
        self._main_layout.addWidget(self._info_section)

        # --- Canvas section ---
        self._canvas_section = CollapsibleSection("Canvas")
        self._canvas_w_label = QLabel("")
        self._canvas_h_label = QLabel("")
        self._bg_color_picker = ColorPicker(QColor("white"))
        self._canvas_section.add_row("Width:", self._canvas_w_label)
        self._canvas_section.add_row("Height:", self._canvas_h_label)
        self._canvas_section.add_row("Background:", self._bg_color_picker)
        self._main_layout.addWidget(self._canvas_section)

        self._main_layout.addStretch()
        scroll.setWidget(container)
        self.setWidget(scroll)

        # Connect edit handlers
        self._x_spin.valueChanged.connect(self._on_x_changed)
        self._y_spin.valueChanged.connect(self._on_y_changed)
        self._w_spin.valueChanged.connect(self._on_w_changed)
        self._h_spin.valueChanged.connect(self._on_h_changed)
        self._rot_spin.valueChanged.connect(self._on_rotation_changed)
        self._stroke_color_picker.color_changed.connect(self._on_stroke_color_changed)
        self._stroke_w_slider.valueChanged.connect(self._on_stroke_w_slider_changed)
        self._stroke_w_spin.valueChanged.connect(self._on_stroke_w_spin_changed)
        self._fill_color_picker.color_changed.connect(self._on_fill_color_changed)
        self._no_fill_check.toggled.connect(self._on_no_fill_toggled)
        self._opacity_slider.valueChanged.connect(self._on_opacity_slider_changed)
        self._opacity_spin.valueChanged.connect(self._on_opacity_spin_changed)
        self._layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        self._locked_check.toggled.connect(self._on_locked_changed)
        self._bg_color_picker.color_changed.connect(self._on_bg_color_changed)
        self._font_combo.currentFontChanged.connect(self._on_font_family_changed)
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        self._bold_check.toggled.connect(self._on_bold_changed)
        self._italic_check.toggled.connect(self._on_italic_changed)
        self._underline_check.toggled.connect(self._on_underline_changed)
        self._text_color_picker.color_changed.connect(self._on_text_color_changed)
        self._text_bg_color_picker.color_changed.connect(self._on_text_bg_color_changed)
        self._no_bg_check.toggled.connect(self._on_no_bg_toggled)
        self._text_border_color_picker.color_changed.connect(self._on_text_border_color_changed)
        self._text_border_w_spin.valueChanged.connect(self._on_text_border_w_changed)
        self._text_corner_radius_spin.valueChanged.connect(self._on_text_corner_radius_changed)
        self._text_padding_spin.valueChanged.connect(self._on_text_padding_changed)
        self._text_valign_combo.currentIndexChanged.connect(self._on_text_valign_changed)
        self._text_auto_size_check.toggled.connect(self._on_text_auto_size_changed)

        # Connect selection signals
        self._connect_selection_signals()
        self._connect_scene_signals()

        # Initial state
        self._refresh_from_selection()

    # --- helpers ---

    @staticmethod
    def _make_double_spin(
        minimum: float, maximum: float, decimals: int, suffix: str
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        return spin

    def _connect_selection_signals(self) -> None:
        self._selection_manager.selection_changed.connect(self._refresh_from_selection)
        self._selection_manager.selection_cleared.connect(self._refresh_from_selection)

    def _connect_scene_signals(self) -> None:
        self._scene.command_stack.stack_changed.connect(self._refresh_from_selection)
        lm = self._scene.layer_manager
        lm.layer_added.connect(self._rebuild_layer_combo)
        lm.layer_removed.connect(self._rebuild_layer_combo)
        lm.layer_renamed.connect(self._rebuild_layer_combo)

    def _first_selected_item(self) -> SnapGraphicsItem | None:
        items = self._selection_manager.items
        if items:
            item = items[0]
            if isinstance(item, SnapGraphicsItem):
                return item
        return None

    # --- refresh ---

    def _refresh_from_selection(self, _items: list[QGraphicsItem] | None = None) -> None:
        self._updating = True
        try:
            item = self._first_selected_item()
            has_selection = item is not None
            is_vector = isinstance(item, VectorItem)
            has_text = isinstance(item, (TextItem, CalloutItem))
            is_text_item = isinstance(item, TextItem)

            # Check for tool-defaults mode: no selection + text/callout tool active
            in_tool_defaults = (
                not has_selection and self._active_tool_id in ("text", "callout")
            )

            # Section visibility
            self._transform_section.setVisible(has_selection)
            self._appearance_section.setVisible(has_selection and is_vector)
            self._text_section.setVisible((has_selection and has_text) or in_tool_defaults)
            self._text_box_section.setVisible((has_selection and has_text) or in_tool_defaults)
            self._info_section.setVisible(has_selection)
            self._canvas_section.setVisible(not has_selection and not in_tool_defaults)

            if in_tool_defaults:
                self._populate_from_tool_defaults()
            elif item is not None:
                # Transform
                self._x_spin.setValue(item.pos_x)
                self._y_spin.setValue(item.pos_y)
                br = item.boundingRect()
                self._w_spin.setValue(br.width())
                self._h_spin.setValue(br.height())
                self._rot_spin.setValue(item.rotation_deg)

                # Appearance (VectorItem only)
                if is_vector:
                    assert isinstance(item, VectorItem)
                    self._stroke_color_picker.color = item.stroke_color
                    self._stroke_w_slider.setValue(int(item.stroke_width))
                    self._stroke_w_spin.setValue(item.stroke_width)
                    self._fill_color_picker.color = item.fill_color
                    self._no_fill_check.setChecked(item.fill_color.alpha() == 0)
                    self._opacity_slider.setValue(int(item.opacity_pct))
                    self._opacity_spin.setValue(int(item.opacity_pct))

                # Text (TextItem / CalloutItem)
                if has_text:
                    assert isinstance(item, (TextItem, CalloutItem))
                    f = item.font
                    self._font_combo.setCurrentFont(f)
                    self._font_size_spin.setValue(f.pointSize())
                    self._bold_check.setChecked(f.bold())
                    self._italic_check.setChecked(f.italic())
                    self._underline_check.setChecked(f.underline())
                    self._text_color_picker.color = item.text_color

                # Text Box (TextItem and CalloutItem)
                if has_text:
                    assert isinstance(item, (TextItem, CalloutItem))
                    self._text_bg_color_picker.color = item.bg_color
                    self._no_bg_check.setChecked(item.bg_color.alpha() == 0)
                    self._text_border_color_picker.color = item.border_color
                    self._text_border_w_spin.setValue(item.border_width)
                    self._text_corner_radius_spin.setValue(item.border_radius)
                    self._text_padding_spin.setValue(item.padding)
                    # Set valign combo
                    for i in range(self._text_valign_combo.count()):
                        if self._text_valign_combo.itemData(i) == item.vertical_align:
                            self._text_valign_combo.setCurrentIndex(i)
                            break
                    # Auto-size only applies to TextItem
                    self._text_auto_size_check.setVisible(is_text_item)
                    if is_text_item:
                        assert isinstance(item, TextItem)
                        self._text_auto_size_check.setChecked(item.auto_size)

                # Item Info
                self._type_label.setText(item.type_name)
                self._rebuild_layer_combo()
                self._locked_check.setChecked(item.locked)
            else:
                # Canvas mode
                cs = self._scene.canvas_size
                self._canvas_w_label.setText(f"{int(cs.width())} px")
                self._canvas_h_label.setText(f"{int(cs.height())} px")
                self._bg_color_picker.color = self._scene.background_color
        finally:
            self._updating = False

    def _in_tool_defaults_mode(self) -> bool:
        """Return True if showing tool defaults (no selection + text/callout tool)."""
        return (
            self._first_selected_item() is None
            and self._active_tool_id in ("text", "callout")
        )

    def _active_tool_defaults(self) -> dict[str, object] | None:
        """Return the creation_defaults dict for the active tool, or None."""
        if self._tool_manager is None:
            return None
        tool = self._tool_manager.tool(self._active_tool_id)
        if tool is None:
            return None
        return tool.creation_defaults

    def _populate_from_tool_defaults(self) -> None:
        """Fill Text + Text Box widgets from the active tool's creation_defaults."""
        d = self._active_tool_defaults()
        if d is None:
            return
        # Text section
        font = QFont(str(d.get("font_family", "Sans Serif")))
        font.setPointSize(int(d.get("font_size", 14)))
        self._font_combo.setCurrentFont(font)
        self._font_size_spin.setValue(int(d.get("font_size", 14)))
        self._bold_check.setChecked(bool(d.get("bold", False)))
        self._italic_check.setChecked(bool(d.get("italic", False)))
        self._underline_check.setChecked(bool(d.get("underline", False)))
        tc = d.get("text_color")
        self._text_color_picker.color = QColor(tc) if isinstance(tc, QColor) else QColor("black")

        # Text Box section
        bg = d.get("bg_color")
        bg_color = QColor(bg) if isinstance(bg, QColor) else QColor("#00000000")
        self._text_bg_color_picker.color = bg_color
        self._no_bg_check.setChecked(bg_color.alpha() == 0)

        bc = d.get("border_color")
        self._text_border_color_picker.color = (
            QColor(bc) if isinstance(bc, QColor) else QColor("#00000000")
        )
        self._text_border_w_spin.setValue(float(d.get("border_width", 0.0)))
        self._text_corner_radius_spin.setValue(float(d.get("border_radius", 0.0)))
        self._text_padding_spin.setValue(float(d.get("padding", 8.0)))

        # Vertical align
        va = d.get("vertical_align", VerticalAlign.TOP)
        for i in range(self._text_valign_combo.count()):
            if self._text_valign_combo.itemData(i) == va:
                self._text_valign_combo.setCurrentIndex(i)
                break

        # Auto-size: only for text tool (not callout)
        is_text_tool = self._active_tool_id == "text"
        self._text_auto_size_check.setVisible(is_text_tool)
        if is_text_tool:
            self._text_auto_size_check.setChecked(bool(d.get("auto_size", True)))

    def _rebuild_layer_combo(self, *_args: object) -> None:
        was_updating = self._updating
        self._updating = True
        try:
            self._layer_combo.clear()
            layers = self._scene.layer_manager.layers
            item = self._first_selected_item()
            current_idx = 0
            for i, layer in enumerate(layers):
                self._layer_combo.addItem(layer.name, layer.layer_id)
                if item is not None and layer.layer_id == item.layer_id:
                    current_idx = i
            self._layer_combo.setCurrentIndex(current_idx)
        finally:
            self._updating = was_updating

    # --- edit handlers ---

    def _on_x_changed(self, value: float) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if item is None:
            return
        cmd = ModifyPropertyCommand(item, "pos_x", item.pos_x, value)
        self._scene.command_stack.push(cmd)

    def _on_y_changed(self, value: float) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if item is None:
            return
        cmd = ModifyPropertyCommand(item, "pos_y", item.pos_y, value)
        self._scene.command_stack.push(cmd)

    def _on_w_changed(self, value: float) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if item is None:
            return
        br = item.boundingRect()
        old_w = br.width()
        if old_w <= 0:
            return
        sx = value / old_w
        cmd = ScaleGeometryCommand(item, sx, 1.0)
        self._scene.command_stack.push(cmd)

    def _on_h_changed(self, value: float) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if item is None:
            return
        br = item.boundingRect()
        old_h = br.height()
        if old_h <= 0:
            return
        sy = value / old_h
        cmd = ScaleGeometryCommand(item, 1.0, sy)
        self._scene.command_stack.push(cmd)

    def _on_rotation_changed(self, value: float) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if item is None:
            return
        cmd = ModifyPropertyCommand(item, "rotation_deg", item.rotation_deg, value)
        self._scene.command_stack.push(cmd)

    def _on_stroke_color_changed(self, color: QColor) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if not isinstance(item, VectorItem):
            return
        cmd = ModifyPropertyCommand(item, "stroke_color", item.stroke_color, color)
        self._scene.command_stack.push(cmd)

    def _on_stroke_w_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        self._stroke_w_spin.setValue(float(value))
        self._updating = False
        item = self._first_selected_item()
        if not isinstance(item, VectorItem):
            return
        cmd = ModifyPropertyCommand(item, "stroke_width", item.stroke_width, float(value))
        self._scene.command_stack.push(cmd)

    def _on_stroke_w_spin_changed(self, value: float) -> None:
        if self._updating:
            return
        self._updating = True
        self._stroke_w_slider.setValue(int(value))
        self._updating = False
        item = self._first_selected_item()
        if not isinstance(item, VectorItem):
            return
        cmd = ModifyPropertyCommand(item, "stroke_width", item.stroke_width, value)
        self._scene.command_stack.push(cmd)

    def _on_fill_color_changed(self, color: QColor) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if not isinstance(item, VectorItem):
            return
        cmd = ModifyPropertyCommand(item, "fill_color", item.fill_color, color)
        self._scene.command_stack.push(cmd)

    def _on_no_fill_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if not isinstance(item, VectorItem):
            return
        old_color = item.fill_color
        if checked:
            new_color = QColor(old_color)
            new_color.setAlpha(0)
        else:
            new_color = QColor(old_color)
            if new_color.alpha() == 0:
                new_color.setAlpha(255)
        cmd = ModifyPropertyCommand(item, "fill_color", old_color, new_color)
        self._scene.command_stack.push(cmd)

    def _on_opacity_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        self._opacity_spin.setValue(value)
        self._updating = False
        item = self._first_selected_item()
        if item is None:
            return
        cmd = ModifyPropertyCommand(item, "opacity_pct", item.opacity_pct, float(value))
        self._scene.command_stack.push(cmd)

    def _on_opacity_spin_changed(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        self._opacity_slider.setValue(value)
        self._updating = False
        item = self._first_selected_item()
        if item is None:
            return
        cmd = ModifyPropertyCommand(item, "opacity_pct", item.opacity_pct, float(value))
        self._scene.command_stack.push(cmd)

    def _on_layer_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        item = self._first_selected_item()
        if item is None:
            return
        target_layer_id = self._layer_combo.itemData(index)
        if not isinstance(target_layer_id, str) or target_layer_id == item.layer_id:
            return
        cmd = MoveItemToLayerCommand(self._scene, [item], target_layer_id)
        self._scene.command_stack.push(cmd)

    def _on_locked_changed(self, checked: bool) -> None:
        if self._updating:
            return
        item = self._first_selected_item()
        if item is None:
            return
        cmd = ModifyPropertyCommand(item, "locked", item.locked, checked)
        self._scene.command_stack.push(cmd)

    def _text_item(self) -> TextItem | CalloutItem | None:
        item = self._first_selected_item()
        if isinstance(item, (TextItem, CalloutItem)):
            return item
        return None

    def _get_active_editor(self) -> QWidget | None:
        """Return the active _RichTextEditor if a text item is being edited."""
        parent = self.parent()
        if parent is not None and hasattr(parent, "tool_manager"):
            text_tool = parent.tool_manager.tool("text")
            if text_tool is not None and hasattr(text_tool, "active_editor"):
                editor = text_tool.active_editor
                if isinstance(editor, QWidget):
                    return editor
        return None

    def _push_font_change(self, item: TextItem | CalloutItem, new_font: QFont) -> None:
        old_font = item.font
        cmd = ModifyPropertyCommand(item, "font", old_font, new_font)
        self._scene.command_stack.push(cmd)

    def _on_font_family_changed(self, font: QFont) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["font_family"] = font.family()
            return
        item = self._text_item()
        if item is None:
            return
        # Edit-mode: apply to cursor selection
        if item.is_editing:
            editor = self._get_active_editor()
            if editor is not None and hasattr(editor, "textCursor"):
                fmt = QTextCharFormat()
                fmt.setFontFamilies([font.family()])
                editor.textCursor().mergeCharFormat(fmt)
                return
        new_font = QFont(item.font)
        new_font.setFamily(font.family())
        self._push_font_change(item, new_font)

    def _on_font_size_changed(self, value: int) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["font_size"] = value
            return
        item = self._text_item()
        if item is None:
            return
        # Edit-mode: apply to cursor selection
        if item.is_editing:
            editor = self._get_active_editor()
            if editor is not None and hasattr(editor, "textCursor"):
                fmt = QTextCharFormat()
                fmt.setFontPointSize(float(value))
                editor.textCursor().mergeCharFormat(fmt)
                return
        new_font = QFont(item.font)
        new_font.setPointSize(value)
        self._push_font_change(item, new_font)

    def _on_bold_changed(self, checked: bool) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["bold"] = checked
            return
        item = self._text_item()
        if item is None:
            return
        # Edit-mode: apply to cursor selection
        if item.is_editing:
            editor = self._get_active_editor()
            if editor is not None and hasattr(editor, "textCursor"):
                fmt = QTextCharFormat()
                fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
                editor.textCursor().mergeCharFormat(fmt)
                return
        new_font = QFont(item.font)
        new_font.setBold(checked)
        self._push_font_change(item, new_font)

    def _on_italic_changed(self, checked: bool) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["italic"] = checked
            return
        item = self._text_item()
        if item is None:
            return
        # Edit-mode: apply to cursor selection
        if item.is_editing:
            editor = self._get_active_editor()
            if editor is not None and hasattr(editor, "textCursor"):
                fmt = QTextCharFormat()
                fmt.setFontItalic(checked)
                editor.textCursor().mergeCharFormat(fmt)
                return
        new_font = QFont(item.font)
        new_font.setItalic(checked)
        self._push_font_change(item, new_font)

    def _on_underline_changed(self, checked: bool) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["underline"] = checked
            return
        item = self._text_item()
        if item is None:
            return
        # Edit-mode: apply to cursor selection
        if item.is_editing:
            editor = self._get_active_editor()
            if editor is not None and hasattr(editor, "textCursor"):
                fmt = QTextCharFormat()
                fmt.setFontUnderline(checked)
                editor.textCursor().mergeCharFormat(fmt)
                return
        new_font = QFont(item.font)
        new_font.setUnderline(checked)
        self._push_font_change(item, new_font)

    def _on_text_color_changed(self, color: QColor) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["text_color"] = QColor(color)
            return
        item = self._text_item()
        if item is None:
            return
        # Edit-mode: apply to cursor selection
        if item.is_editing:
            editor = self._get_active_editor()
            if editor is not None and hasattr(editor, "textCursor"):
                fmt = QTextCharFormat()
                fmt.setForeground(color)
                editor.textCursor().mergeCharFormat(fmt)
                return
        cmd = ModifyPropertyCommand(item, "text_color", item.text_color, color)
        self._scene.command_stack.push(cmd)

    def _on_text_bg_color_changed(self, color: QColor) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["bg_color"] = QColor(color)
            return
        item = self._first_selected_item()
        if not isinstance(item, (TextItem, CalloutItem)):
            return
        cmd = ModifyPropertyCommand(item, "bg_color", item.bg_color, color)
        self._scene.command_stack.push(cmd)

    def _on_no_bg_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                old = d.get("bg_color", QColor("#00000000"))
                new_color = QColor(old) if isinstance(old, QColor) else QColor(old)
                if checked:
                    new_color.setAlpha(0)
                elif new_color.alpha() == 0:
                    new_color.setAlpha(255)
                d["bg_color"] = new_color
            return
        item = self._first_selected_item()
        if not isinstance(item, (TextItem, CalloutItem)):
            return
        old_color = item.bg_color
        if checked:
            new_color = QColor(old_color)
            new_color.setAlpha(0)
        else:
            new_color = QColor(old_color)
            if new_color.alpha() == 0:
                new_color.setAlpha(255)
        cmd = ModifyPropertyCommand(item, "bg_color", old_color, new_color)
        self._scene.command_stack.push(cmd)

    def _on_text_border_color_changed(self, color: QColor) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["border_color"] = QColor(color)
            return
        item = self._first_selected_item()
        if not isinstance(item, (TextItem, CalloutItem)):
            return
        cmd = ModifyPropertyCommand(item, "border_color", item.border_color, color)
        self._scene.command_stack.push(cmd)

    def _on_text_border_w_changed(self, value: float) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["border_width"] = value
            return
        item = self._first_selected_item()
        if not isinstance(item, (TextItem, CalloutItem)):
            return
        cmd = ModifyPropertyCommand(item, "border_width", item.border_width, value)
        self._scene.command_stack.push(cmd)

    def _on_text_corner_radius_changed(self, value: float) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["border_radius"] = value
            return
        item = self._first_selected_item()
        if not isinstance(item, (TextItem, CalloutItem)):
            return
        cmd = ModifyPropertyCommand(item, "border_radius", item.border_radius, value)
        self._scene.command_stack.push(cmd)

    def _on_text_padding_changed(self, value: float) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["padding"] = value
            return
        item = self._first_selected_item()
        if not isinstance(item, (TextItem, CalloutItem)):
            return
        cmd = ModifyPropertyCommand(item, "padding", item.padding, value)
        self._scene.command_stack.push(cmd)

    def _on_text_valign_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            new_align = self._text_valign_combo.itemData(index)
            if d is not None and isinstance(new_align, VerticalAlign):
                d["vertical_align"] = new_align
            return
        item = self._first_selected_item()
        if not isinstance(item, (TextItem, CalloutItem)):
            return
        new_align = self._text_valign_combo.itemData(index)
        if not isinstance(new_align, VerticalAlign):
            return
        cmd = ModifyPropertyCommand(
            item, "vertical_align", item.vertical_align, new_align
        )
        self._scene.command_stack.push(cmd)

    def _on_text_auto_size_changed(self, checked: bool) -> None:
        if self._updating:
            return
        if self._in_tool_defaults_mode():
            d = self._active_tool_defaults()
            if d is not None:
                d["auto_size"] = checked
            return
        item = self._first_selected_item()
        if not isinstance(item, TextItem):
            return
        cmd = ModifyPropertyCommand(item, "auto_size", item.auto_size, checked)
        self._scene.command_stack.push(cmd)

    def _on_bg_color_changed(self, color: QColor) -> None:
        if self._updating:
            return
        self._scene.set_background_color(color)

    # --- public API for scene/selection replacement ---

    def set_scene(self, scene: SnapScene) -> None:
        """Replace the scene reference (e.g. after File > New or Open)."""
        self._scene = scene
        self._connect_scene_signals()
        self._refresh_from_selection()

    def set_selection(self, selection_manager: SelectionManager) -> None:
        """Replace the SelectionManager (e.g. after opening a new project)."""
        self._selection_manager = selection_manager
        self._connect_selection_signals()
        self._refresh_from_selection()

    def set_tool_manager(self, tm: ToolManager) -> None:
        """Wire the property panel to the tool manager for tool-defaults mode."""
        self._tool_manager = tm
        tm.tool_changed.connect(self._on_tool_changed)

    def _on_tool_changed(self, tool_id: str) -> None:
        """Track the active tool and refresh the panel."""
        self._active_tool_id = tool_id
        self._refresh_from_selection()
