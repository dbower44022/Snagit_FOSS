"""ItemPropertiesDialog — inspect and edit properties of a SnapGraphicsItem."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from snapmock.ui.color_picker import ColorPicker

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.items.base_item import SnapGraphicsItem


class ItemPropertiesDialog(QDialog):
    """Modal dialog for viewing and editing item properties."""

    def __init__(
        self,
        item: SnapGraphicsItem,
        scene: SnapScene,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self._scene = scene
        self.setWindowTitle("Item Properties")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        # --- General group ---
        general_group = QGroupBox("General")
        general_layout = QFormLayout()

        self._type_label = QLabel(item.type_name)
        general_layout.addRow("Type:", self._type_label)

        self._id_label = QLabel(item.item_id[:12] + "...")
        general_layout.addRow("ID:", self._id_label)

        layer_name = self._resolve_layer_name()
        self._layer_label = QLabel(layer_name)
        general_layout.addRow("Layer:", self._layer_label)

        self._locked_cb = QCheckBox()
        self._locked_cb.setChecked(item.locked)
        general_layout.addRow("Locked:", self._locked_cb)

        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # --- Transform group ---
        transform_group = QGroupBox("Transform")
        transform_layout = QFormLayout()

        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(-99999.0, 99999.0)
        self._x_spin.setDecimals(1)
        self._x_spin.setSuffix(" px")
        self._x_spin.setValue(item.pos_x)
        transform_layout.addRow("X:", self._x_spin)

        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(-99999.0, 99999.0)
        self._y_spin.setDecimals(1)
        self._y_spin.setSuffix(" px")
        self._y_spin.setValue(item.pos_y)
        transform_layout.addRow("Y:", self._y_spin)

        br = item.boundingRect()
        self._w_label = QLabel(f"{br.width():.1f} px")
        transform_layout.addRow("W:", self._w_label)

        self._h_label = QLabel(f"{br.height():.1f} px")
        transform_layout.addRow("H:", self._h_label)

        self._rotation_spin = QDoubleSpinBox()
        self._rotation_spin.setRange(-360.0, 360.0)
        self._rotation_spin.setDecimals(1)
        self._rotation_spin.setSuffix("°")
        self._rotation_spin.setValue(item.rotation_deg)
        transform_layout.addRow("Rotation:", self._rotation_spin)

        self._opacity_spin = QSpinBox()
        self._opacity_spin.setRange(0, 100)
        self._opacity_spin.setSuffix("%")
        self._opacity_spin.setValue(int(item.opacity_pct))
        transform_layout.addRow("Opacity:", self._opacity_spin)

        transform_group.setLayout(transform_layout)
        layout.addWidget(transform_group)

        # --- Appearance group (VectorItem only) ---
        from snapmock.items.vector_item import VectorItem

        self._is_vector = isinstance(item, VectorItem)
        self._appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout()

        stroke_color = item.stroke_color if isinstance(item, VectorItem) else QColor("black")
        self._stroke_color_picker = ColorPicker(stroke_color)
        appearance_layout.addRow("Stroke color:", self._stroke_color_picker)

        self._stroke_width_spin = QDoubleSpinBox()
        self._stroke_width_spin.setRange(0.0, 100.0)
        self._stroke_width_spin.setDecimals(1)
        stroke_width = item.stroke_width if isinstance(item, VectorItem) else 0.0
        self._stroke_width_spin.setValue(stroke_width)
        appearance_layout.addRow("Stroke width:", self._stroke_width_spin)

        fill_color = item.fill_color if isinstance(item, VectorItem) else QColor("white")
        self._fill_color_picker = ColorPicker(fill_color)
        appearance_layout.addRow("Fill color:", self._fill_color_picker)

        self._appearance_group.setLayout(appearance_layout)
        layout.addWidget(self._appearance_group)
        self._appearance_group.setVisible(self._is_vector)

        # --- Text group (TextItem / CalloutItem only) ---
        from snapmock.items.callout_item import CalloutItem
        from snapmock.items.text_item import TextItem

        self._is_text = isinstance(item, (TextItem, CalloutItem))
        self._text_group = QGroupBox("Text")
        text_layout = QFormLayout()

        if isinstance(item, (TextItem, CalloutItem)):
            current_font = item.font
            current_text_color = item.text_color
        else:
            current_font = QFont()
            current_text_color = QColor("black")
        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(current_font)
        text_layout.addRow("Font:", self._font_combo)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(1, 200)
        self._font_size_spin.setSuffix(" pt")
        self._font_size_spin.setValue(current_font.pointSize() if self._is_text else 12)
        text_layout.addRow("Size:", self._font_size_spin)

        self._bold_cb = QCheckBox("Bold")
        self._bold_cb.setChecked(current_font.bold() if self._is_text else False)
        self._italic_cb = QCheckBox("Italic")
        self._italic_cb.setChecked(current_font.italic() if self._is_text else False)
        self._underline_cb = QCheckBox("Underline")
        self._underline_cb.setChecked(current_font.underline() if self._is_text else False)
        text_layout.addRow("Style:", self._bold_cb)
        text_layout.addRow("", self._italic_cb)
        text_layout.addRow("", self._underline_cb)

        self._text_color_picker = ColorPicker(current_text_color)
        text_layout.addRow("Text color:", self._text_color_picker)

        self._text_group.setLayout(text_layout)
        layout.addWidget(self._text_group)
        self._text_group.setVisible(self._is_text)

        # --- Snapshot original values ---
        self._orig: dict[str, Any] = {
            "pos_x": item.pos_x,
            "pos_y": item.pos_y,
            "rotation_deg": item.rotation_deg,
            "opacity_pct": item.opacity_pct,
            "locked": item.locked,
        }
        if self._is_vector:
            assert isinstance(item, VectorItem)
            self._orig["stroke_color"] = QColor(item.stroke_color)
            self._orig["stroke_width"] = item.stroke_width
            self._orig["fill_color"] = QColor(item.fill_color)
        if self._is_text:
            assert isinstance(item, (TextItem, CalloutItem))
            self._orig["font"] = QFont(item.font)
            self._orig["text_color"] = QColor(item.text_color)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _resolve_layer_name(self) -> str:
        layer = self._scene.layer_manager.layer_by_id(self._item.layer_id)
        return layer.name if layer is not None else "(unknown)"

    def get_changes(self) -> dict[str, tuple[object, object]]:
        """Return only properties that actually changed.

        Returns a dict keyed by property name, with ``(old_value, new_value)`` tuples.
        """
        changes: dict[str, tuple[object, object]] = {}

        new_x = round(self._x_spin.value(), 1)
        if new_x != round(self._orig["pos_x"], 1):
            changes["pos_x"] = (self._orig["pos_x"], new_x)

        new_y = round(self._y_spin.value(), 1)
        if new_y != round(self._orig["pos_y"], 1):
            changes["pos_y"] = (self._orig["pos_y"], new_y)

        new_rot = round(self._rotation_spin.value(), 1)
        if new_rot != round(self._orig["rotation_deg"], 1):
            changes["rotation_deg"] = (self._orig["rotation_deg"], new_rot)

        new_opacity = float(self._opacity_spin.value())
        if new_opacity != round(self._orig["opacity_pct"]):
            changes["opacity_pct"] = (self._orig["opacity_pct"], new_opacity)

        new_locked = self._locked_cb.isChecked()
        if new_locked != self._orig["locked"]:
            changes["locked"] = (self._orig["locked"], new_locked)

        if self._is_vector:
            new_sc = self._stroke_color_picker.color
            if new_sc != self._orig["stroke_color"]:
                changes["stroke_color"] = (self._orig["stroke_color"], new_sc)

            new_sw = round(self._stroke_width_spin.value(), 1)
            if new_sw != round(self._orig["stroke_width"], 1):
                changes["stroke_width"] = (self._orig["stroke_width"], new_sw)

            new_fc = self._fill_color_picker.color
            if new_fc != self._orig["fill_color"]:
                changes["fill_color"] = (self._orig["fill_color"], new_fc)

        if self._is_text:
            # Build font from dialog widgets
            new_font = QFont(self._font_combo.currentFont())
            new_font.setPointSize(self._font_size_spin.value())
            new_font.setBold(self._bold_cb.isChecked())
            new_font.setItalic(self._italic_cb.isChecked())
            new_font.setUnderline(self._underline_cb.isChecked())
            if new_font != self._orig["font"]:
                changes["font"] = (self._orig["font"], new_font)

            new_tc = self._text_color_picker.color
            if new_tc != self._orig["text_color"]:
                changes["text_color"] = (self._orig["text_color"], new_tc)

        return changes
