"""Numbered step editing (Numbered Steps, Stamps & Emoji PRD 2.8): the inline editor, the
context menu rows, Renumber All Steps across layers and groups, and the Property Panel."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QMenu, QSpinBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.group_commands import GroupItemsCommand
from snapmock.commands.marker_commands import RenumberStepsCommand
from snapmock.config.constants import BadgeShape, DisplayMode, LabelPosition
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.tools import numbered_step_tool as tool_module
from snapmock.tools.numbered_step_tool import NumberedStepTool
from snapmock.ui.context_menus import build_item_context_menu
from snapmock.ui.property_panel import PropertyPanel
from snapmock.ui.step_inline_editor import EDIT_HINT, StepInlineEditor


@pytest.fixture(autouse=True)
def _no_animation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_module, "ANIMATIONS_ENABLED", False)


def _add_step(scene: SnapScene, number: int, x: float, y: float) -> NumberedStepItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = NumberedStepItem(number_value=number)
    item.setPos(x, y)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _menu_texts(menu: QMenu) -> list[str]:
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def _double_click(window: MainWindow, scene_pos: QPointF) -> None:
    view_pos = QPointF(window.view.mapFromScene(scene_pos))
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        view_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.tool_manager.handle_mouse_double_click(event)


# --- the inline editor (Section 2.8) ---


def test_open_marker_editor_shows_the_value_and_label_fields(
    main_window: MainWindow, qtbot: QtBot
) -> None:
    step = _add_step(main_window.scene, 3, 100, 100)
    step.label_text = "Go"
    assert main_window.open_marker_editor(step)
    editor = main_window.marker_editor
    assert isinstance(editor, StepInlineEditor)
    assert editor.value_edit.text() == "3"
    assert editor.label_edit.text() == "Go"
    assert not editor.isHidden()
    assert main_window._status_bar._hint_label.text() == EDIT_HINT  # noqa: SLF001
    assert main_window.selection_manager.items == [step]
    main_window.close_marker_editor()
    assert main_window.marker_editor is None


def test_enter_applies_number_and_label_as_one_undo_entry(
    main_window: MainWindow, qtbot: QtBot
) -> None:
    step = _add_step(main_window.scene, 3, 100, 100)
    main_window.open_marker_editor(step)
    editor = main_window.marker_editor
    assert isinstance(editor, StepInlineEditor)
    editor.value_edit.setText("12")
    qtbot.keyClick(editor.value_edit, Qt.Key.Key_Tab)  # Tab: edit label
    assert editor.label_edit.hasFocus() or not editor.value_edit.hasFocus()
    editor.label_edit.setText("Click Login")
    qtbot.keyClick(editor.label_edit, Qt.Key.Key_Return)
    assert main_window.marker_editor is None
    assert step.number_value == 12
    assert step.label_text == "Click Login"
    main_window.scene.command_stack.undo()
    assert step.number_value == 3
    assert step.label_text == ""
    # The tool's counter is not touched by a manual override (Section 2.8)
    tool = main_window.tool_manager.tool("numbered_step")
    assert isinstance(tool, NumberedStepTool)
    main_window.tool_manager.activate("numbered_step")
    assert tool.next_number == 4  # the highest step plus one on first activation


def test_escape_finishes_without_applying(main_window: MainWindow, qtbot: QtBot) -> None:
    step = _add_step(main_window.scene, 3, 100, 100)
    main_window.open_marker_editor(step)
    editor = main_window.marker_editor
    assert isinstance(editor, StepInlineEditor)
    editor.value_edit.setText("99")
    qtbot.keyClick(editor.value_edit, Qt.Key.Key_Escape)
    assert main_window.marker_editor is None
    assert step.number_value == 3
    main_window.scene.command_stack.undo()  # the placement was the only entry
    assert not main_window.scene.command_stack.can_undo


def test_text_mode_edits_the_custom_text(main_window: MainWindow, qtbot: QtBot) -> None:
    step = _add_step(main_window.scene, 3, 100, 100)
    step.display_mode = DisplayMode.TEXT
    step.custom_text = "A"
    main_window.open_marker_editor(step)
    editor = main_window.marker_editor
    assert isinstance(editor, StepInlineEditor)
    assert editor.value_edit.text() == "A"
    editor.value_edit.setText("OK")
    editor.finish()
    assert step.custom_text == "OK"
    assert step.number_value == 3


def test_double_click_opens_the_editor_from_the_select_tool_and_the_step_tool(
    main_window: MainWindow, qtbot: QtBot
) -> None:
    step = _add_step(main_window.scene, 5, 200, 200)
    main_window.tool_manager.activate("select")
    _double_click(main_window, QPointF(200, 200))
    assert isinstance(main_window.marker_editor, StepInlineEditor)
    assert main_window.marker_editor.item is step
    main_window.close_marker_editor()
    main_window.tool_manager.activate("numbered_step")
    _double_click(main_window, QPointF(200, 200))
    assert isinstance(main_window.marker_editor, StepInlineEditor)
    main_window.close_marker_editor()
    # A click on an existing step with the step tool selects it and places nothing
    from tests.test_tools.test_numbered_step_tool import _click

    _click(main_window, QPointF(200, 200))
    steps = [i for i in main_window.scene.annotation_items() if isinstance(i, NumberedStepItem)]
    assert steps == [step]
    assert main_window.selection_manager.items == [step]


def test_a_second_editor_finishes_the_first(main_window: MainWindow) -> None:
    a = _add_step(main_window.scene, 1, 100, 100)
    b = _add_step(main_window.scene, 2, 200, 100)
    main_window.open_marker_editor(a)
    first = main_window.marker_editor
    assert isinstance(first, StepInlineEditor)
    first.value_edit.setText("7")
    main_window.open_marker_editor(b)
    assert a.number_value == 7
    assert isinstance(main_window.marker_editor, StepInlineEditor)
    assert main_window.marker_editor.item is b
    main_window.close_marker_editor()


def test_open_marker_editor_refuses_a_non_marker(main_window: MainWindow) -> None:
    rect = RectangleItem()
    layer = main_window.scene.layer_manager.active_layer
    assert layer is not None
    main_window.scene.command_stack.push(AddItemCommand(main_window.scene, rect, layer.layer_id))
    assert main_window.open_marker_editor(rect) is False
    assert main_window.marker_editor is None


# --- the context menu rows (Section 2.8) ---


def test_context_menu_rows_appear_for_one_numbered_step_only(main_window: MainWindow) -> None:
    step = _add_step(main_window.scene, 1, 100, 100)
    main_window.selection_manager.select(step)
    texts = _menu_texts(build_item_context_menu(main_window))
    assert "Renumber All Steps" in texts
    assert "Set as Starting Number" in texts
    assert "Convert to Text Mode" in texts
    assert texts.index("Properties...") > texts.index("Convert to Text Mode")
    step.display_mode = DisplayMode.TEXT
    assert "Convert to Number Mode" in _menu_texts(build_item_context_menu(main_window))
    other = _add_step(main_window.scene, 2, 200, 100)
    main_window.selection_manager.select_items([step, other])
    texts = _menu_texts(build_item_context_menu(main_window))
    assert "Renumber All Steps" not in texts
    rect = RectangleItem()
    layer = main_window.scene.layer_manager.active_layer
    assert layer is not None
    main_window.scene.command_stack.push(AddItemCommand(main_window.scene, rect, layer.layer_id))
    main_window.selection_manager.select(rect)
    assert "Set as Starting Number" not in _menu_texts(build_item_context_menu(main_window))


def test_set_as_starting_number_reaches_the_tool(main_window: MainWindow) -> None:
    step = _add_step(main_window.scene, 8, 100, 100)
    main_window.selection_manager.select(step)
    tool = main_window.tool_manager.tool("numbered_step")
    assert isinstance(tool, NumberedStepTool)
    main_window.tool_manager.activate("numbered_step")
    main_window._step_set_as_starting_number()  # noqa: SLF001
    assert tool.creation_defaults["start_number"] == 8
    assert tool.next_number == 8
    bar_spin = main_window._tool_options.shared_widgets["start_number"]  # noqa: SLF001
    assert isinstance(bar_spin, QSpinBox)
    assert bar_spin.value() == 8


def test_convert_display_mode_toggles_with_undo(main_window: MainWindow) -> None:
    step = _add_step(main_window.scene, 1, 100, 100)
    main_window.selection_manager.select(step)
    main_window._step_toggle_text_mode()  # noqa: SLF001
    assert step.display_mode is DisplayMode.TEXT
    main_window.scene.command_stack.undo()
    assert step.display_mode is DisplayMode.NUMBER
    main_window.scene.command_stack.redo()
    assert step.display_mode is DisplayMode.TEXT
    main_window._step_toggle_text_mode()  # noqa: SLF001
    assert step.display_mode is DisplayMode.NUMBER


def test_step_rows_explain_without_one_step(
    main_window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    main_window._step_set_as_starting_number()  # noqa: SLF001
    assert unmet_messages[-1] == (
        "Set as Starting Number",
        "Set as Starting Number needs one numbered step.",
    )
    main_window._step_toggle_text_mode()  # noqa: SLF001
    assert unmet_messages[-1][0] == "Convert Display Mode"


# --- Renumber All Steps across layers and inside a group (Sections 2.3 and 6.1) ---


def test_renumber_reaches_every_layer_and_group_members(scene: SnapScene) -> None:
    first = scene.layer_manager.active_layer
    assert first is not None
    a = _add_step(scene, 9, 10, 300)  # lowest: becomes 3
    b = _add_step(scene, 9, 10, 10)  # top left: becomes 1
    second = scene.layer_manager.add_layer("Layer 2")
    scene.layer_manager.set_active(second.layer_id)
    assert second is not first
    c = _add_step(scene, 9, 200, 10)  # top right, other layer: becomes 2
    d = _add_step(scene, 9, 300, 10)  # top, far right, grouped: becomes 3
    a.setPos(10, 300)
    scene.command_stack.push(GroupItemsCommand(scene, [c, d]))
    command = RenumberStepsCommand(scene, 1)
    scene.command_stack.push(command)
    assert (b.number_value, c.number_value, d.number_value, a.number_value) == (1, 2, 3, 4)
    scene.command_stack.undo()
    assert {a.number_value, b.number_value, c.number_value, d.number_value} == {9}


# --- the Property Panel (General UI PRD 8.3; decision 1) ---


def _panel(qtbot: QtBot) -> tuple[PropertyPanel, SnapScene, SelectionManager]:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    return panel, scene, sm


def test_panel_shows_appearance_step_and_shadow_sections_for_a_step(qtbot: QtBot) -> None:
    panel, scene, sm = _panel(qtbot)
    step = _add_step(scene, 4, 50, 50)
    step.label_text = "Go"
    step.label_position = LabelPosition.TOP
    sm.select(step)
    assert panel._appearance_section.isVisible()  # noqa: SLF001
    assert panel._step_section.isVisible()  # noqa: SLF001
    assert panel._shadow_section.isVisible()  # noqa: SLF001
    assert not panel._text_section.isVisible()  # noqa: SLF001
    assert panel._step_value_spin.value() == 4  # noqa: SLF001
    assert panel._step_shape_combo.currentData() is BadgeShape.CIRCLE  # noqa: SLF001
    assert panel._step_label_edit.text() == "Go"  # noqa: SLF001
    assert panel._step_label_pos_combo.currentData() is LabelPosition.TOP  # noqa: SLF001
    assert panel._shadow_check.isChecked()  # noqa: SLF001
    assert panel._shadow_blur_spin.value() == 4.0  # noqa: SLF001
    assert panel._stroke_color_picker.color.name() == "#ffffff"  # noqa: SLF001
    assert panel._fill_color_picker.color.name() == "#cc0000"  # noqa: SLF001
    assert panel._type_label.text() == "Numbered Step"  # noqa: SLF001


def test_panel_hides_the_step_section_for_a_rectangle(qtbot: QtBot) -> None:
    """A rectangle shows Appearance and, since the Vector Item Properties work, Shadow."""
    panel, scene, sm = _panel(qtbot)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    rect = RectangleItem()
    scene.command_stack.push(AddItemCommand(scene, rect, layer.layer_id))
    sm.select(rect)
    assert panel._appearance_section.isVisible()  # noqa: SLF001
    assert not panel._step_section.isVisible()  # noqa: SLF001
    assert panel._shadow_section.isVisible()  # noqa: SLF001
    step = _add_step(scene, 1, 10, 10)
    sm.select_items([rect, step])
    assert panel._shadow_section.isVisible()  # noqa: SLF001
    assert not panel._step_section.isVisible()  # noqa: SLF001


def test_panel_edits_push_undoable_commands(qtbot: QtBot) -> None:
    panel, scene, sm = _panel(qtbot)
    step = _add_step(scene, 4, 50, 50)
    sm.select(step)
    shape = panel._step_shape_combo  # noqa: SLF001
    assert isinstance(shape, QComboBox)
    shape.setCurrentIndex(shape.findData(BadgeShape.PIN))
    assert step.badge_shape is BadgeShape.PIN
    panel._step_value_spin.setValue(11)  # noqa: SLF001
    assert step.number_value == 11
    size = panel._step_size_spin  # noqa: SLF001
    assert isinstance(size, QDoubleSpinBox)
    size.setValue(64.0)
    assert step.badge_size == 64.0
    panel._fill_opacity_spin.setValue(40)  # noqa: SLF001
    assert step.fill_opacity == pytest.approx(0.4)
    panel._step_label_edit.setText("Hello")  # noqa: SLF001
    panel._step_label_edit.editingFinished.emit()  # noqa: SLF001
    assert step.label_text == "Hello"
    pill = panel._step_label_pill_check  # noqa: SLF001
    assert isinstance(pill, QCheckBox)
    pill.setChecked(True)
    assert step.label_background_enabled is True
    panel._step_label_color_picker.color_changed.emit(QColor("#123456"))  # noqa: SLF001
    assert step.label_color.name() == "#123456"
    # Shadow
    panel._shadow_check.setChecked(False)  # noqa: SLF001
    assert step.shadow_enabled is False
    panel._shadow_x_spin.setValue(6.0)  # noqa: SLF001
    assert step.shadow_offset_x == 6.0
    panel._shadow_blur_spin.setValue(9.0)  # noqa: SLF001
    assert step.shadow_blur == 9.0
    panel._shadow_color_picker.color_changed.emit(QColor(255, 0, 0, 80))  # noqa: SLF001
    assert step.shadow_color.red() == 255 and step.shadow_color.alpha() == 80
    # Every edit was a command
    stack = scene.command_stack
    for _ in range(11):
        assert stack.can_undo
        stack.undo()
    assert step.badge_shape is BadgeShape.CIRCLE
    assert step.number_value == 4
    assert step.shadow_enabled is True


def test_panel_shows_mixed_values_across_two_steps(qtbot: QtBot) -> None:
    panel, scene, sm = _panel(qtbot)
    a = _add_step(scene, 1, 10, 10)
    b = _add_step(scene, 2, 60, 10)
    b.badge_shape = BadgeShape.STAR
    sm.select_items([a, b])
    assert panel._step_section.isVisible()  # noqa: SLF001
    assert panel._step_value_spin.value() == panel._step_value_spin.minimum()  # noqa: SLF001
    assert panel._step_shape_combo.currentIndex() == -1  # noqa: SLF001
    panel._step_shape_combo.setCurrentIndex(  # noqa: SLF001
        panel._step_shape_combo.findData(BadgeShape.SQUARE)  # noqa: SLF001
    )
    assert a.badge_shape is BadgeShape.SQUARE and b.badge_shape is BadgeShape.SQUARE
    scene.command_stack.undo()
    assert a.badge_shape is BadgeShape.CIRCLE and b.badge_shape is BadgeShape.STAR
