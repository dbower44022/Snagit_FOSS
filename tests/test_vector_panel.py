"""The Property Panel's Appearance, Text Box, and Shadow sections after the Vector Item
Properties work (General UI PRD 8.3, 8.4, 8.6; decisions 1 and 2)."""

from __future__ import annotations

from PyQt6.QtCore import QLineF, QRectF
from PyQt6.QtGui import QColor
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.group_commands import GroupItemsCommand
from snapmock.config.constants import BorderStyle
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.callout_item import CalloutItem
from snapmock.items.line_item import LineItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem
from snapmock.tools.line_tool import LineTool
from snapmock.tools.rectangle_tool import RectangleTool
from snapmock.tools.select_tool import SelectTool
from snapmock.tools.tool_manager import ToolManager
from snapmock.ui.property_panel import MIXED_TEXT, PropertyPanel


def _panel(qtbot: QtBot) -> tuple[PropertyPanel, SnapScene, SelectionManager]:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    return panel, scene, sm


def _add(scene: SnapScene, item: SnapGraphicsItem, x: float = 0, y: float = 0) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.setPos(x, y)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))


def _visible(panel: PropertyPanel, section: object, field: object) -> bool:
    label = section.form_layout.labelForField(field)  # type: ignore[attr-defined]
    return bool(field.isVisible() and (label is None or label.isVisible()))  # type: ignore[attr-defined]


def test_a_rectangle_shows_style_the_two_opacities_and_shadow(qtbot: QtBot) -> None:
    panel, scene, sm = _panel(qtbot)
    rect = RectangleItem(rect=QRectF(0, 0, 100, 60))
    rect.stroke_style = BorderStyle.DOTTED
    rect.fill_opacity = 0.4
    rect.stroke_opacity = 0.7
    rect.shadow_enabled = True
    rect.shadow_blur = 5.0
    _add(scene, rect)
    sm.select(rect)
    appearance = panel._appearance_section  # noqa: SLF001
    assert appearance.isVisible()
    assert panel._stroke_style_combo.currentData() is BorderStyle.DOTTED  # noqa: SLF001
    assert panel._fill_opacity_spin.value() == 40  # noqa: SLF001
    assert panel._stroke_opacity_spin.value() == 70  # noqa: SLF001
    assert _visible(panel, appearance, panel._fill_opacity_row)  # noqa: SLF001
    assert not _visible(panel, appearance, panel._opacity_row)  # noqa: SLF001
    assert panel._shadow_section.isVisible()  # noqa: SLF001
    assert panel._shadow_check.isChecked()  # noqa: SLF001
    assert panel._shadow_blur_spin.value() == 5.0  # noqa: SLF001
    assert not panel._step_section.isVisible()  # noqa: SLF001


def test_panel_edits_on_a_line_are_commands(qtbot: QtBot) -> None:
    panel, scene, sm = _panel(qtbot)
    line = LineItem(line=QLineF(0, 0, 100, 0))
    _add(scene, line)
    sm.select(line)
    assert _visible(panel, panel._appearance_section, panel._fill_row)  # noqa: SLF001
    combo = panel._stroke_style_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(BorderStyle.DASHED))
    assert line.stroke_style is BorderStyle.DASHED
    panel._stroke_opacity_spin.setValue(30)  # noqa: SLF001
    assert line.stroke_opacity == 0.3
    panel._shadow_check.setChecked(True)  # noqa: SLF001
    assert line.shadow_enabled is True
    panel._shadow_y_spin.setValue(9.0)  # noqa: SLF001
    assert line.shadow_offset_y == 9.0
    stack = scene.command_stack
    for _ in range(4):
        assert stack.can_undo
        stack.undo()
    assert line.stroke_style is BorderStyle.SOLID and line.stroke_opacity == 1.0
    assert line.shadow_enabled is False and line.shadow_offset_y == 3.0


def test_a_text_box_keeps_appearance_hidden_and_takes_the_text_box_rows(
    qtbot: QtBot,
) -> None:
    panel, scene, sm = _panel(qtbot)
    text = TextItem("Hi")
    text.fill_opacity = 0.5
    _add(scene, text)
    sm.select(text)
    assert not panel._appearance_section.isVisible()  # noqa: SLF001
    assert panel._text_box_section.isVisible()  # noqa: SLF001
    assert panel._shadow_section.isVisible()  # noqa: SLF001
    assert panel._text_fill_opacity_spin.value() == 50  # noqa: SLF001
    panel._text_stroke_opacity_spin.setValue(20)  # noqa: SLF001
    assert text.stroke_opacity == 0.2
    panel._shadow_check.setChecked(True)  # noqa: SLF001
    assert text.shadow_enabled is True
    assert scene.command_stack.count == 3  # the add and the two edits
    callout = CalloutItem("Yo")
    _add(scene, callout, 200, 200)
    sm.select_items([text, callout])
    assert panel._text_box_section.isVisible()  # noqa: SLF001
    assert panel._text_stroke_opacity_spin.text() == MIXED_TEXT  # noqa: SLF001
    panel._text_fill_opacity_spin.setValue(60)  # noqa: SLF001
    assert text.fill_opacity == 0.6 and callout.fill_opacity == 0.6


def test_a_group_shows_its_own_opacity_beside_its_members_two(qtbot: QtBot) -> None:
    panel, scene, sm = _panel(qtbot)
    a = RectangleItem(rect=QRectF(0, 0, 50, 50))
    b = LineItem(line=QLineF(0, 0, 80, 0))
    _add(scene, a)
    _add(scene, b, 100, 100)
    command = GroupItemsCommand(scene, [a, b], sm)
    scene.command_stack.push(command)
    group = command.group
    assert group is not None
    sm.select(group)
    appearance = panel._appearance_section  # noqa: SLF001
    assert appearance.isVisible()
    assert _visible(panel, appearance, panel._opacity_row)  # noqa: SLF001
    assert panel._shadow_section.isVisible()  # noqa: SLF001
    panel._fill_opacity_spin.setValue(25)  # noqa: SLF001
    assert a.fill_opacity == 0.25 and b.fill_opacity == 0.25
    assert group.opacity() == 1.0
    panel._opacity_spin.setValue(50)  # noqa: SLF001
    assert group.opacity_pct == 50.0
    assert a.fill_opacity == 0.25
    panel._shadow_check.setChecked(True)  # noqa: SLF001
    assert a.shadow_enabled is True and b.shadow_enabled is True
    scene.command_stack.undo()
    assert a.shadow_enabled is False


def test_mixed_values_across_two_rectangles(qtbot: QtBot) -> None:
    panel, scene, sm = _panel(qtbot)
    a = RectangleItem(rect=QRectF(0, 0, 50, 50))
    b = RectangleItem(rect=QRectF(0, 0, 50, 50))
    b.stroke_style = BorderStyle.DASHED
    b.fill_opacity = 0.5
    b.shadow_enabled = True
    _add(scene, a)
    _add(scene, b, 100, 0)
    sm.select_items([a, b])
    assert panel._stroke_style_combo.currentIndex() == -1  # noqa: SLF001
    assert panel._fill_opacity_spin.text() == MIXED_TEXT  # noqa: SLF001
    assert panel._stroke_opacity_spin.value() == 100  # noqa: SLF001
    assert panel._shadow_check.checkState().name == "PartiallyChecked"  # noqa: SLF001
    panel._fill_opacity_spin.setValue(80)  # noqa: SLF001
    assert a.fill_opacity == 0.8 and b.fill_opacity == 0.8
    assert scene.command_stack.undo_text == "Change fill_opacity on 2 items"


def test_tool_defaults_mode_hides_the_fill_rows_for_a_line_and_writes_the_defaults(
    qtbot: QtBot,
) -> None:
    panel, scene, sm = _panel(qtbot)
    tm = ToolManager(scene, sm)
    for tool in (SelectTool(), RectangleTool(), LineTool()):
        tm.register(tool)
    panel.set_tool_manager(tm)
    tm.activate("line")
    appearance = panel._appearance_section  # noqa: SLF001
    assert appearance.isVisible()
    assert not _visible(panel, appearance, panel._fill_row)  # noqa: SLF001
    assert not _visible(panel, appearance, panel._fill_opacity_row)  # noqa: SLF001
    assert not _visible(panel, appearance, panel._opacity_row)  # noqa: SLF001
    assert not panel._shadow_section.isVisible()  # noqa: SLF001
    combo = panel._stroke_style_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(BorderStyle.DOTTED))
    panel._stroke_opacity_spin.setValue(45)  # noqa: SLF001
    line_tool = tm.tool("line")
    assert line_tool is not None
    assert line_tool.creation_defaults["stroke_style"] is BorderStyle.DOTTED
    assert line_tool.creation_defaults["stroke_opacity"] == 0.45
    assert "opacity_pct" not in line_tool.creation_defaults
    tm.activate("rectangle")
    assert _visible(panel, appearance, panel._fill_row)  # noqa: SLF001
    rect_tool = tm.tool("rectangle")
    assert rect_tool is not None
    rect_tool.creation_defaults["fill_opacity"] = 0.3
    tm.tool_defaults_changed.emit("rectangle")
    assert panel._fill_opacity_spin.value() == 30  # noqa: SLF001
    assert panel._stroke_color_picker.color == QColor("#FF0000")  # noqa: SLF001
