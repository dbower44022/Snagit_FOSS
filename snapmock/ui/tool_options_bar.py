"""ToolOptionsBar — the shared control set and per-tool options (General UI PRD Section 5).

The bar composes each tool's options from the tool's :attr:`BaseTool.options_controls`
declaration: every shared control (colour swatches, stroke width, opacity, font
family and size, bold/italic/underline, smoothing, starting number) is built by one
factory here and bound to the key of the same name in the tool's ``creation_defaults``.
The tool's own :meth:`BaseTool.build_options_widgets` adds what only it has.

The Select tool's bar and the Eyedropper's bar are composed here too, because both
act on things a tool cannot reach: the Arrange actions and the other tools' defaults.

The leftmost control of every tool that has creation defaults is the preset dropdown of
PRD 5.2: a button naming the applied preset, the active theme, or "Custom", whose menu
lists the tool's presets and the Save as Preset, Update Preset, Manage Presets, and Reset
to Theme rows. It reads and writes through the :class:`ToolThemeManager`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolBar,
    QToolButton,
    QWidget,
)

from snapmock.commands.macro_command import MacroCommand
from snapmock.commands.modify_property import ModifyPropertyCommand
from snapmock.config.constants import (
    BADGE_SIZE_MAX,
    BADGE_SIZE_MIN,
    CORNER_RADIUS_MAX,
    HEAD_SIZE_CUSTOM_MAX,
    HIGHLIGHT_WIDTH_MAX,
    HIGHLIGHT_WIDTH_MIN,
    BadgeShape,
    BorderStyle,
    DisplayMode,
    FontWeight,
    HeadSize,
    HeadStyle,
)
from snapmock.core.emoji_data import EMOJI_SIZE_MAX, EMOJI_SIZE_MIN
from snapmock.core.stamp_library import STAMP_SIZE_MAX, STAMP_SIZE_MIN
from snapmock.core.theme_manager import theme_manager
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.tools.eyedropper_tool import EyedropperTool
from snapmock.ui.accessibility import apply_default_names
from snapmock.ui.color_picker import ColorPicker
from snapmock.ui.unmet_requirements import check_requirements

if TYPE_CHECKING:
    from snapmock.core.command_stack import BaseCommand
    from snapmock.core.selection_manager import SelectionManager
    from snapmock.core.tool_themes import ToolThemeManager
    from snapmock.tools.base_tool import BaseTool
    from snapmock.tools.tool_manager import ToolManager

TOOL_OPTIONS_BAR_HEIGHT = 36
SWATCH_SIZE = 24
_CONTROL_HEIGHT = 26


@dataclass(frozen=True)
class ControlSpec:
    """One shared control: its widget kind, label, and range (PRD 5.2)."""

    key: str
    label: str
    kind: str  # color | double | int | slider | font | text_style | enum | check
    minimum: float = 0.0
    maximum: float = 100.0
    step: float = 1.0
    suffix: str = ""
    decimals: int = 0
    choices: tuple[tuple[str, Any], ...] = ()
    """The enum kind's rows as (label, value) pairs, in order."""
    icon: str = ""
    """The toggle kind's Tabler glyph."""
    scale: float = 1.0
    """The slider kind's widget units per stored unit: 100 for a 0.0 to 1.0 opacity."""


SHARED_CONTROLS: dict[str, ControlSpec] = {
    "stroke_color": ControlSpec("stroke_color", "Stroke", "color"),
    "fill_color": ControlSpec("fill_color", "Fill", "color"),
    "stroke_width": ControlSpec(
        "stroke_width", "Width", "double", 0.5, 50.0, 0.5, " px", decimals=1
    ),
    "opacity_pct": ControlSpec("opacity_pct", "Opacity", "slider", 0, 100, 1, "%"),
    # The vector items' shared set (Basic Shape PRD 2.6; General UI PRD 5.2)
    "stroke_style": ControlSpec(
        "stroke_style",
        "Style",
        "enum",
        choices=tuple((s.value.replace("dashdot", "dash-dot").title(), s) for s in BorderStyle),
    ),
    "fill_opacity": ControlSpec(
        "fill_opacity", "Fill Opacity", "slider", 0, 100, 1, "%", scale=100.0
    ),
    "stroke_opacity": ControlSpec(
        "stroke_opacity", "Stroke Opacity", "slider", 0, 100, 1, "%", scale=100.0
    ),
    # The Highlighter (Blur PRD 3.5): its colour and width under their own names and
    # range, the four blend modes of 3.4 (the item takes every mode of ITEM_BLEND_MODES)
    "highlight_color": ControlSpec("highlight_color", "Highlight", "color"),
    "highlight_width": ControlSpec(
        "highlight_width", "Width", "slider", HIGHLIGHT_WIDTH_MIN, HIGHLIGHT_WIDTH_MAX, 1, " px"
    ),
    "blend_mode": ControlSpec(
        "blend_mode",
        "Blend",
        "enum",
        choices=(
            ("Multiply", "Multiply"),
            ("Overlay", "Overlay"),
            ("Soft Light", "Soft Light"),
            ("Normal", "Normal"),
        ),
    ),
    # The Rectangle tool (Basic Shape PRD 5.4): the uniform corner radius
    "corner_radius": ControlSpec(
        "corner_radius", "Corner Radius", "slider", 0, CORNER_RADIUS_MAX, 1, " px"
    ),
    # The Arrow tool (Basic Shape PRD 4.7): the head and tail styles with glyphs, the size
    "head_style": ControlSpec(
        "head_style",
        "Head",
        "enum",
        choices=tuple((s.value.title(), s) for s in HeadStyle),
    ),
    "tail_style": ControlSpec(
        "tail_style",
        "Tail",
        "enum",
        choices=tuple((s.value.title(), s) for s in HeadStyle),
    ),
    "head_size": ControlSpec(
        "head_size",
        "Head Size",
        "enum",
        choices=(
            ("Small", HeadSize.SMALL),
            ("Medium", HeadSize.MEDIUM),
            ("Large", HeadSize.LARGE),
            ("XLarge", HeadSize.XLARGE),
        ),
    ),
    "head_size_custom": ControlSpec(
        "head_size_custom",
        "Custom",
        "double",
        0.0,
        HEAD_SIZE_CUSTOM_MAX,
        1.0,
        " px",
        decimals=0,
    ),
    "font_family": ControlSpec("font_family", "Font", "font"),
    "font_size": ControlSpec("font_size", "Size", "int", 6, 200, 1, " pt"),
    "text_style": ControlSpec("text_style", "", "text_style"),
    "text_color": ControlSpec("text_color", "Text", "color"),
    "bg_color": ControlSpec("bg_color", "Background", "color"),
    "border_color": ControlSpec("border_color", "Border", "color"),
    "border_width": ControlSpec("border_width", "Border", "double", 0.0, 20.0, 0.5, " px", 1),
    "smoothing": ControlSpec("smoothing", "Smoothing", "slider", 0, 100, 1, "%"),
    "start_number": ControlSpec("start_number", "Start at", "int", 1, 999, 1),
    # The Numbered Step tool (Numbered Steps, Stamps & Emoji PRD 2.7)
    "badge_color": ControlSpec("badge_color", "Badge", "color"),
    "badge_shape": ControlSpec(
        "badge_shape",
        "Shape",
        "enum",
        choices=tuple((s.value.replace("_", " ").title(), s) for s in BadgeShape),
    ),
    "badge_size": ControlSpec(
        "badge_size", "Size", "slider", BADGE_SIZE_MIN, BADGE_SIZE_MAX, 1, " px"
    ),
    "display_mode": ControlSpec(
        "display_mode",
        "Mode",
        "enum",
        choices=(
            ("Number", DisplayMode.NUMBER),
            ("Letter", DisplayMode.LETTER),
            ("Roman", DisplayMode.ROMAN),
            ("Custom Text", DisplayMode.TEXT),
        ),
    ),
    "font_weight": ControlSpec(
        "font_weight",
        "Weight",
        "enum",
        choices=(("Normal", FontWeight.NORMAL), ("Bold", FontWeight.BOLD)),
    ),
    "border_style": ControlSpec(
        "border_style",
        "Style",
        "enum",
        choices=tuple((s.value.replace("dashdot", "dash-dot").title(), s) for s in BorderStyle),
    ),
    "shadow_enabled": ControlSpec("shadow_enabled", "Shadow", "check"),
    # The Stamp tool (PRD 3.6) and the Emoji tool (PRD 4.5)
    "stamp_size": ControlSpec(
        "stamp_size", "Size", "slider", STAMP_SIZE_MIN, STAMP_SIZE_MAX, 1, " px"
    ),
    "stamp_color": ControlSpec("stamp_color", "Color", "color"),
    "stamp_secondary_color": ControlSpec("stamp_secondary_color", "Secondary", "color"),
    "flip_horizontal": ControlSpec(
        "flip_horizontal", "Flip Horizontal", "toggle", icon="flip-horizontal"
    ),
    "flip_vertical": ControlSpec("flip_vertical", "Flip Vertical", "toggle", icon="flip-vertical"),
    "emoji_size": ControlSpec(
        "emoji_size", "Size", "slider", EMOJI_SIZE_MIN, EMOJI_SIZE_MAX, 1, " px"
    ),
}

_TEXT_STYLE_KEYS: tuple[tuple[str, str, str], ...] = (
    ("bold", "B", "Bold"),
    ("italic", "I", "Italic"),
    ("underline", "U", "Underline"),
)


def arrow_head_icon(style: HeadStyle, size: int = 20, *, tail: bool = False) -> QIcon:
    """A short arrow drawn with *style* at its head (or its tail), the dropdown's glyph
    (Basic Shape PRD 4.7, "visual icons")."""
    from PyQt6.QtCore import QLineF

    from snapmock.items.arrow_item import ArrowItem
    from snapmock.items.vector_item import with_alpha  # noqa: F401  (keeps the import graph)

    item = ArrowItem(line=QLineF(3.0, size / 2, size - 3.0, size / 2))
    item.stroke_width = 1.5
    item.stroke_color = QColor(90, 90, 90)
    item.head_size = HeadSize.SMALL
    item.head_size_custom = 6.0
    if tail:
        item.tail_style = style
        item.head_style = HeadStyle.NONE
    else:
        item.head_style = style
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    item.paint(painter, None)
    painter.end()
    return QIcon(pixmap)


def badge_shape_icon(shape: BadgeShape, size: int = 16) -> QIcon:
    """The badge shape drawn as a small filled glyph (PRD 2.7, "visual icons")."""
    from snapmock.items.numbered_step_item import NumberedStepItem

    item = NumberedStepItem(badge_size=float(size) - 2.0)
    item.badge_shape = shape
    item.shadow_enabled = False
    path = item.badge_path()
    bounds = path.boundingRect()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(size / 2 - bounds.center().x(), size / 2 - bounds.center().y())
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(90, 90, 90))
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


class ToolOptionsBar(QToolBar):
    """Context-sensitive options for the active tool, 36 px tall (PRD 2.2)."""

    def __init__(self, tool_manager: ToolManager, parent: QWidget | None = None) -> None:
        super().__init__("Tool Options", parent)
        self.setAccessibleName("Tool Options")
        self._tool_manager = tool_manager
        self._tool: BaseTool | None = None
        self._updating = False
        self._shared: dict[str, QWidget] = {}
        self._control_actions: dict[str, list[QAction]] = {}
        self._style_buttons: dict[str, QToolButton] = {}
        self._selection: SelectionManager | None = None
        self._selection_actions: list[QAction] = []
        self._selection_copies: list[QAction] = []
        self._selection_label: QLabel | None = None
        self._eyedropper_swatch: QLabel | None = None
        self._eyedropper_hex: QLabel | None = None
        self._eyedropper_rgb: QLabel | None = None
        self._themes: ToolThemeManager | None = None
        self._preset_button: QToolButton | None = None
        self._preset_menu: QMenu | None = None
        self._label = QLabel("No tool selected")
        self.addWidget(self._label)
        self.setMovable(False)
        self.setFixedHeight(TOOL_OPTIONS_BAR_HEIGHT)

        tool_manager.tool_changed.connect(self._on_tool_changed)
        tool_manager.tool_defaults_changed.connect(self._on_tool_defaults_changed)
        self._on_tool_changed(tool_manager.active_tool_id)

    # ---- wiring from the window ----

    def set_selection_actions(self, actions: Sequence[QAction]) -> None:
        """The Arrange actions the Select tool's bar shows for two or more items (PRD 5.3)."""
        self._selection_actions = list(actions)
        if self._tool is not None and self._tool.tool_id == "select":
            self._on_tool_changed("select")

    def set_selection_manager(self, selection: SelectionManager) -> None:
        """Follow another document's selection (tab switch)."""
        if self._selection is selection:
            return
        if self._selection is not None:
            try:
                self._selection.selection_changed.disconnect(self._on_selection_changed)
            except (TypeError, RuntimeError):
                pass
        self._selection = selection
        selection.selection_changed.connect(self._on_selection_changed)
        self._update_selection_widgets()

    def set_theme_manager(self, themes: ToolThemeManager) -> None:
        """The presets and themes the dropdown reads and writes (PRD 5.2)."""
        self._themes = themes
        themes.state_changed.connect(self._refresh_preset_label)
        themes.presets_changed.connect(self._on_presets_changed)
        if self._tool is not None:
            self._on_tool_changed(self._tool.tool_id)

    def refresh(self) -> None:
        """Re-read the active tool's creation defaults into the shared controls."""
        if self._tool is not None:
            self._read_defaults(self._tool)
        self._refresh_preset_label()

    @property
    def preset_button(self) -> QToolButton | None:
        """The preset dropdown, when the active tool has creation defaults."""
        return self._preset_button

    @property
    def shared_widgets(self) -> dict[str, QWidget]:
        """The shared controls currently shown, keyed by creation-defaults key."""
        return dict(self._shared)

    @property
    def selection_action_copies(self) -> list[QAction]:
        return list(self._selection_copies)

    # ---- composition ----

    def set_control_visible(self, key: str, visible: bool) -> None:
        """Show or hide one shared control with its label (the Rectangle bar's single
        Corner Radius slider, replaced by four spin boxes in Individual mode, PRD 5.4)."""
        for action in self._control_actions.get(key, []):
            action.setVisible(visible)

    def _on_tool_changed(self, tool_id: str) -> None:
        self.clear()
        self._shared.clear()
        self._control_actions.clear()
        self._style_buttons.clear()
        self._selection_copies.clear()
        self._selection_label = None
        self._eyedropper_swatch = self._eyedropper_hex = self._eyedropper_rgb = None
        self._preset_button = self._preset_menu = None
        tool = self._tool_manager.tool(tool_id)
        self._tool = tool
        if tool is None:
            self._label = QLabel("No tool selected")
            self.addWidget(self._label)
            return
        if self._themes is not None and tool_id in self._themes.tool_ids:
            self._build_preset_dropdown(tool)
        self._label = QLabel(f"{tool.display_name} ")
        self.addWidget(self._label)

        keys = list(tool.options_controls)
        if "tool" not in keys:
            keys.append("tool")
        for key in keys:
            if key == "tool":
                if tool.tool_id == "select":
                    self._build_selection_controls()
                elif isinstance(tool, EyedropperTool):
                    self._build_eyedropper_controls(tool)
                tool.build_options_widgets(self)
                continue
            spec = SHARED_CONTROLS[key]
            if spec.key != "text_style" and spec.key not in tool.creation_defaults:
                continue
            before = len(self.actions())
            self._build_control(spec)
            self._control_actions[spec.key] = self.actions()[before:]
        self._read_defaults(tool)
        self._update_selection_widgets()
        apply_default_names(self)

    def _add_labelled(self, label: str, widget: QWidget) -> None:
        if label:
            text = QLabel(f" {label}:")
            self.addWidget(text)
        widget.setMaximumHeight(_CONTROL_HEIGHT)
        self.addWidget(widget)

    def _build_control(self, spec: ControlSpec) -> None:
        if spec.kind == "color":
            picker = ColorPicker(swatch_size=SWATCH_SIZE)
            picker.setToolTip(f"{spec.label} colour")
            picker.setAccessibleName(f"{spec.label} color")
            picker.color_changed.connect(lambda c, k=spec.key: self._write(k, QColor(c)))
            self._add_labelled(spec.label, picker)
            self._shared[spec.key] = picker
        elif spec.kind == "double":
            dspin = QDoubleSpinBox()
            dspin.setRange(spec.minimum, spec.maximum)
            dspin.setSingleStep(spec.step)
            dspin.setDecimals(spec.decimals)
            dspin.setSuffix(spec.suffix)
            dspin.setMaximumWidth(80)
            dspin.setAccessibleName(spec.label)
            dspin.valueChanged.connect(lambda v, k=spec.key: self._write(k, float(v)))
            self._add_labelled(spec.label, dspin)
            self._shared[spec.key] = dspin
        elif spec.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(spec.minimum), int(spec.maximum))
            spin.setSingleStep(int(spec.step))
            spin.setSuffix(spec.suffix)
            spin.setMaximumWidth(80)
            spin.setAccessibleName(spec.label)
            spin.valueChanged.connect(lambda v, k=spec.key: self._write(k, int(v)))
            self._add_labelled(spec.label, spin)
            self._shared[spec.key] = spin
        elif spec.kind == "slider":
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(int(spec.minimum), int(spec.maximum))
            slider.setFixedWidth(80)
            slider.setAccessibleName(f"{spec.label} slider")
            spin = QSpinBox()
            spin.setRange(int(spec.minimum), int(spec.maximum))
            spin.setSuffix(spec.suffix)
            spin.setMaximumWidth(64)
            spin.setAccessibleName(spec.label)
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            if spec.scale != 1.0:
                spin.valueChanged.connect(
                    lambda v, k=spec.key, s=spec.scale: self._write(k, float(v) / s)
                )
            else:
                spin.valueChanged.connect(lambda v, k=spec.key: self._write(k, v))
            self._add_labelled(spec.label, slider)
            spin.setMaximumHeight(_CONTROL_HEIGHT)
            self.addWidget(spin)
            self._shared[spec.key] = spin
        elif spec.kind == "font":
            font_combo = QFontComboBox()
            font_combo.setMaximumWidth(160)
            font_combo.setAccessibleName(spec.label)
            font_combo.currentFontChanged.connect(
                lambda f, k=spec.key: self._write(k, str(f.family()))
            )
            self._add_labelled(spec.label, font_combo)
            self._shared[spec.key] = font_combo
        elif spec.kind == "enum":
            combo = QComboBox()
            combo.setMaximumWidth(130)
            combo.setAccessibleName(spec.label)
            for text, value in spec.choices:
                if spec.key == "badge_shape" and isinstance(value, BadgeShape):
                    combo.addItem(badge_shape_icon(value), text, value)
                elif spec.key in ("head_style", "tail_style") and isinstance(value, HeadStyle):
                    combo.addItem(
                        arrow_head_icon(value, tail=spec.key == "tail_style"), text, value
                    )
                else:
                    combo.addItem(text, value)
            combo.currentIndexChanged.connect(
                lambda index, k=spec.key, c=combo: self._write(k, c.itemData(index))
            )
            self._add_labelled(spec.label, combo)
            self._shared[spec.key] = combo
        elif spec.kind == "toggle":
            toggle = QToolButton()
            toggle.setCheckable(True)
            toggle.setToolTip(spec.label)
            toggle.setAccessibleName(spec.label)
            toggle.setFixedSize(_CONTROL_HEIGHT, _CONTROL_HEIGHT)
            icon = theme_manager().icon(spec.icon) if spec.icon else QIcon()
            if icon.isNull():
                toggle.setText(spec.label[:1])
            else:
                toggle.setIcon(icon)
            toggle.toggled.connect(lambda checked, k=spec.key: self._write(k, bool(checked)))
            self.addWidget(toggle)
            self._shared[spec.key] = toggle
        elif spec.kind == "check":
            check = QCheckBox(spec.label)
            check.setAccessibleName(spec.label)
            check.toggled.connect(lambda checked, k=spec.key: self._write(k, bool(checked)))
            check.setMaximumHeight(_CONTROL_HEIGHT)
            self.addWidget(check)
            self._shared[spec.key] = check
        elif spec.kind == "text_style":
            for key, text, tip in _TEXT_STYLE_KEYS:
                button = QToolButton()
                button.setText(text)
                button.setToolTip(tip)
                button.setAccessibleName(tip)
                button.setCheckable(True)
                button.setFixedSize(_CONTROL_HEIGHT, _CONTROL_HEIGHT)
                font = button.font()
                if key == "bold":
                    font.setBold(True)
                elif key == "italic":
                    font.setItalic(True)
                else:
                    font.setUnderline(True)
                button.setFont(font)
                button.toggled.connect(lambda checked, k=key: self._write(k, bool(checked)))
                self.addWidget(button)
                self._style_buttons[key] = button
                self._shared[key] = button

    # ---- the preset dropdown (PRD 5.2) ----

    def _build_preset_dropdown(self, tool: BaseTool) -> None:
        button = QToolButton()
        button.setObjectName("PresetDropdown")
        button.setAccessibleName(f"{tool.display_name} preset")
        button.setToolTip("Preset: the applied preset, the active theme, or Custom")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setMaximumHeight(_CONTROL_HEIGHT)
        menu = QMenu(button)
        menu.setObjectName("PresetMenu")
        menu.aboutToShow.connect(self._populate_preset_menu)
        button.setMenu(menu)
        self.addWidget(button)
        self._preset_button = button
        self._preset_menu = menu
        self._refresh_preset_label()

    def _refresh_preset_label(self) -> None:
        if self._preset_button is None or self._themes is None or self._tool is None:
            return
        self._preset_button.setText(f"{self._themes.current_label(self._tool.tool_id)} ▾")

    def _on_presets_changed(self, tool_id: str) -> None:
        if self._tool is not None and self._tool.tool_id == tool_id:
            self._refresh_preset_label()

    def _populate_preset_menu(self) -> None:
        """Rebuild the dropdown's rows from the tool's presets and state."""
        menu, themes, tool = self._preset_menu, self._themes, self._tool
        if menu is None or themes is None or tool is None:
            return
        menu.clear()
        tool_id = tool.tool_id
        label = themes.current_label(tool_id)
        for preset in themes.presets(tool_id):
            action = menu.addAction(preset.name)
            if action is None:
                continue
            action.setCheckable(True)
            action.setChecked(preset.name == label)
            action.triggered.connect(
                lambda _checked=False, name=preset.name: self._apply_preset(name)
            )
        if themes.presets(tool_id):
            menu.addSeparator()
        save = menu.addAction("Save as Preset...")
        if save is not None:
            save.triggered.connect(self._save_as_preset)
        if themes.preset_is_modified(tool_id):
            update = menu.addAction("Update Preset")
            if update is not None:
                update.triggered.connect(self._update_preset)
        manage = menu.addAction("Manage Presets...")
        if manage is not None:
            manage.triggered.connect(self._manage_presets)
        reset = menu.addAction("Reset to Theme")
        if reset is not None:
            reset.triggered.connect(self._reset_to_theme)

    def _ask_preset_name(self, initial: str = "") -> str | None:
        """Prompt for a preset name; None when cancelled."""
        text, ok = QInputDialog.getText(self, "Save as Preset", "Preset name:", text=initial)
        return text.strip() if ok else None

    def _confirm_replace(self, name: str) -> bool:
        answer = QMessageBox.question(
            self,
            "Save as Preset",
            f'A preset named "{name}" exists. Replace it with the current settings?',
        )
        return answer == QMessageBox.StandardButton.Yes

    def _apply_preset(self, name: str) -> None:
        if self._themes is not None and self._tool is not None:
            self._themes.apply_preset(self._tool.tool_id, name)

    def _save_as_preset(self) -> None:
        if self._themes is None or self._tool is None:
            return
        tool_id = self._tool.tool_id
        name = self._ask_preset_name()
        if name is None:
            return
        if not check_requirements(self, "Save as Preset", [(bool(name), "a preset name")]):
            return
        if name in self._themes.preset_names(tool_id) and not self._confirm_replace(name):
            return
        self._themes.save_preset(tool_id, name)

    def _update_preset(self) -> None:
        if self._themes is None or self._tool is None:
            return
        tool_id = self._tool.tool_id
        if check_requirements(
            self,
            "Update Preset",
            [(self._themes.applied_preset(tool_id) is not None, "an applied preset")],
        ):
            self._themes.update_preset(tool_id)

    def _manage_presets(self) -> None:
        """Manage Presets... (PRD 11.9): the dialog for the active tool's presets."""
        if self._themes is None or self._tool is None:
            return
        from snapmock.ui.manage_presets_dialog import ManagePresetsDialog

        tool = self._tool
        if not check_requirements(
            self,
            "Manage Presets",
            [
                (
                    bool(self._themes.preset_names(tool.tool_id)),
                    f"at least one saved preset for the {tool.display_name} tool",
                )
            ],
        ):
            return
        dialog = ManagePresetsDialog(
            self._themes, tool.tool_id, tool.display_name, tool.options_controls, self.window()
        )
        dialog.exec()

    def _reset_to_theme(self) -> None:
        if self._themes is None or self._tool is None:
            return
        tool_id = self._tool.tool_id
        if check_requirements(
            self,
            "Reset to Theme",
            [
                (
                    self._themes.is_overridden(tool_id),
                    "a setting that differs from the active theme",
                )
            ],
        ):
            self._themes.reset_to_theme(tool_id)

    # ---- the two-way binding ----

    def _write(self, key: str, value: Any) -> None:
        """A control changed: store the default and tell the other surfaces."""
        if self._updating or self._tool is None:
            return
        self._tool.creation_defaults[key] = value
        self._tool.on_option_changed(key, value)
        self._tool_manager.tool_defaults_changed.emit(self._tool.tool_id)

    def _on_tool_defaults_changed(self, tool_id: str) -> None:
        if self._tool is not None and self._tool.tool_id == tool_id:
            self._read_defaults(self._tool)

    def _read_defaults(self, tool: BaseTool) -> None:
        """Show the tool's creation defaults in the shared controls without writing back."""
        d = tool.creation_defaults
        self._updating = True
        try:
            for key, widget in self._shared.items():
                if key not in d:
                    continue
                value = d[key]
                if isinstance(widget, ColorPicker):
                    widget.color = QColor(value) if isinstance(value, QColor) else QColor("black")
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QSpinBox):
                    spec = SHARED_CONTROLS.get(key)
                    scale = spec.scale if spec is not None else 1.0
                    widget.setValue(int(round(float(value) * scale)))
                elif isinstance(widget, QFontComboBox):
                    widget.setCurrentFont(QFont(str(value)))
                elif isinstance(widget, QComboBox):
                    index = widget.findData(value)
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif isinstance(widget, QCheckBox | QToolButton):
                    widget.setChecked(bool(value))
        finally:
            self._updating = False

    # ---- the Select tool's bar (PRD 5.3; Navigation PRD 2.5) ----

    def _build_selection_controls(self) -> None:
        self._selection_label = QLabel("No selection")
        self.addWidget(self._selection_label)
        if not self._selection_actions:
            return
        self.addSeparator()
        for action in self._selection_actions:
            copy = QAction(action.text(), self)
            copy.setIcon(action.icon())
            copy.setToolTip(action.toolTip() or action.text().replace("&", ""))
            copy.triggered.connect(action.trigger)
            self.addAction(copy)
            button = self.widgetForAction(copy)
            if isinstance(button, QToolButton):
                button.setFixedSize(_CONTROL_HEIGHT, _CONTROL_HEIGHT)
                button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            self._selection_copies.append(copy)

    def _on_selection_changed(self, _items: list[object]) -> None:
        self._update_selection_widgets()

    def _update_selection_widgets(self) -> None:
        count = self._selection.count if self._selection is not None else 0
        if self._selection_label is not None:
            if count == 0 or self._selection is None:
                self._selection_label.setText("No selection")
            else:
                items = [i for i in self._selection.items if isinstance(i, SnapGraphicsItem)]
                noun = "item" if count == 1 else "items"
                text = f"Selection: {count} {noun}"
                if items:
                    rect = items[0].sceneBoundingRect()
                    for item in items[1:]:
                        rect = rect.united(item.sceneBoundingRect())
                    text += f"   W: {rect.width():.0f} H: {rect.height():.0f}"
                self._selection_label.setText(text)
        for copy in self._selection_copies:
            copy.setVisible(count >= 2)

    # ---- the Eyedropper's bar (PRD 5.3) ----

    def _build_eyedropper_controls(self, tool: EyedropperTool) -> None:
        self._eyedropper_swatch = QLabel()
        self._eyedropper_swatch.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        self._eyedropper_swatch.setToolTip("Picked colour")
        self.addWidget(self._eyedropper_swatch)
        self._eyedropper_hex = QLabel()
        self._eyedropper_hex.setMinimumWidth(64)
        self.addWidget(self._eyedropper_hex)
        self._eyedropper_rgb = QLabel()
        self._eyedropper_rgb.setMinimumWidth(110)
        self.addWidget(self._eyedropper_rgb)
        stroke = QPushButton("Apply to Stroke")
        stroke.setMaximumHeight(_CONTROL_HEIGHT)
        stroke.clicked.connect(lambda: self._apply_picked("stroke_color"))
        self.addWidget(stroke)
        fill = QPushButton("Apply to Fill")
        fill.setMaximumHeight(_CONTROL_HEIGHT)
        fill.clicked.connect(lambda: self._apply_picked("fill_color"))
        self.addWidget(fill)
        tool.set_pick_callback(self._on_color_picked)
        self._on_color_picked(tool.picked_color)

    def _on_color_picked(self, color: QColor) -> None:
        if self._eyedropper_swatch is None or self._eyedropper_hex is None:
            return
        pixmap = QPixmap(SWATCH_SIZE, SWATCH_SIZE)
        if color.isValid():
            pixmap.fill(color)
            self._eyedropper_hex.setText(color.name().upper())
            if self._eyedropper_rgb is not None:
                self._eyedropper_rgb.setText(f"RGB {color.red()}, {color.green()}, {color.blue()}")
        else:
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawRect(0, 0, SWATCH_SIZE - 1, SWATCH_SIZE - 1)
            painter.end()
            self._eyedropper_hex.setText("—")
            if self._eyedropper_rgb is not None:
                self._eyedropper_rgb.setText("Click the canvas to pick")
        self._eyedropper_swatch.setPixmap(pixmap)

    def _apply_picked(self, key: str) -> None:
        """Apply the picked colour to the selected items, else to every tool's default."""
        tool = self._tool
        if not isinstance(tool, EyedropperTool):
            return
        color = tool.picked_color
        if not color.isValid():
            return
        if self._selection is not None and self._selection.count:
            scene = None
            commands: list[BaseCommand] = []
            for item in self._selection.items:
                if isinstance(item, SnapGraphicsItem) and hasattr(item, key):
                    commands.append(ModifyPropertyCommand(item, key, getattr(item, key), color))
                    scene = item.scene()
            if commands and scene is not None and hasattr(scene, "command_stack"):
                label = "Apply to Stroke" if key == "stroke_color" else "Apply to Fill"
                scene.command_stack.push(MacroCommand(commands, label))
                return
        for tool_id in self._tool_manager.tool_ids:
            other = self._tool_manager.tool(tool_id)
            if other is not None and key in other.creation_defaults:
                other.creation_defaults[key] = QColor(color)
                self._tool_manager.tool_defaults_changed.emit(tool_id)
