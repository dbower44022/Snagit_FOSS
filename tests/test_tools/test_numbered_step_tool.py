"""NumberedStepTool and its Tool Options Bar (Numbered Steps, Stamps & Emoji PRD 2.2, 2.3,
2.7, 2.11; kickoff Phase 1 step 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWidgets import QCheckBox, QComboBox, QPushButton, QSpinBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.marker_commands import RenumberStepsCommand, steps_in_reading_order
from snapmock.config.constants import BadgeShape, BorderStyle, DisplayMode, FontWeight
from snapmock.core.document import Document
from snapmock.core.scene import SnapScene
from snapmock.core.tool_themes import decode_values, encode_values
from snapmock.io.project_serializer import load_project, save_project
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.main_window import MainWindow
from snapmock.tools import numbered_step_tool as tool_module
from snapmock.tools.numbered_step_tool import NumberedStepTool
from snapmock.ui.color_picker import ColorPicker
from snapmock.ui.tool_options_bar import ToolOptionsBar

Button = Qt.MouseButton
Modifier = Qt.KeyboardModifier


@pytest.fixture(autouse=True)
def _no_animation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A placed item lands at scale 1 at once (kickoff silence 4)."""
    monkeypatch.setattr(tool_module, "ANIMATIONS_ENABLED", False)


def _tool(window: MainWindow) -> NumberedStepTool:
    window.tool_manager.activate("numbered_step")
    tool = window.tool_manager.tool("numbered_step")
    assert isinstance(tool, NumberedStepTool)
    return tool


def _bar(window: MainWindow) -> ToolOptionsBar:
    return window._tool_options  # noqa: SLF001


def _event(kind: QEvent.Type, window: MainWindow, scene_pos: QPointF) -> QMouseEvent:
    view_pos = QPointF(window.view.mapFromScene(scene_pos))
    return QMouseEvent(kind, view_pos, Button.LeftButton, Button.LeftButton, Modifier.NoModifier)


def _press(window: MainWindow, scene_pos: QPointF) -> None:
    window.tool_manager.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, window, scene_pos))


def _move(window: MainWindow, scene_pos: QPointF) -> None:
    window.tool_manager.handle_mouse_move(_event(QEvent.Type.MouseMove, window, scene_pos))


def _release(window: MainWindow, scene_pos: QPointF) -> None:
    window.tool_manager.handle_mouse_release(
        _event(QEvent.Type.MouseButtonRelease, window, scene_pos)
    )


def _click(window: MainWindow, scene_pos: QPointF) -> None:
    _press(window, scene_pos)
    _release(window, scene_pos)


def _steps(window: MainWindow) -> list[NumberedStepItem]:
    """The steps in placement order (the scene lists the topmost first)."""
    found = [i for i in window.scene.annotation_items() if isinstance(i, NumberedStepItem)]
    return list(reversed(found))


# --- identity and hints (Sections 2.1 and 2.11) ---


def test_identity_cursor_and_idle_hint(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    assert tool.tool_id == "numbered_step"
    assert tool.display_name == "Numbered Step"
    assert not tool.cursor.pixmap().isNull()  # type: ignore[union-attr]
    assert tool.status_hint == "Click to place step 1. Drag to set size. Next: 1."


# --- click to place (Section 2.2) ---


def test_click_places_the_next_number_centred_at_the_click(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    _click(main_window, QPointF(100, 120))
    _click(main_window, QPointF(200, 120))
    _click(main_window, QPointF(300, 120))
    steps = _steps(main_window)
    assert [s.number_value for s in steps] == [1, 2, 3]
    assert steps[0].pos() == QPointF(100, 120)
    assert steps[0].badge_size == 32.0
    assert steps[0].scale() == 1.0
    assert tool.next_number == 4
    assert main_window.tool_manager.active_tool_id == "numbered_step"  # the tool stays
    assert tool.status_hint == "Placed Step 3. Click to place Step 4."
    tool._show_idle_hint()  # noqa: SLF001
    assert tool.status_hint == "Click to place step 4. Drag to set size. Next: 4."


def test_placement_is_undoable(main_window: MainWindow) -> None:
    _tool(main_window)
    _click(main_window, QPointF(50, 50))
    assert len(_steps(main_window)) == 1
    main_window.scene.command_stack.undo()
    assert _steps(main_window) == []


def test_drag_sets_the_diameter_to_twice_the_distance(main_window: MainWindow) -> None:
    _tool(main_window)
    _press(main_window, QPointF(200, 200))
    _move(main_window, QPointF(230, 200))
    assert main_window.tool_manager.active_tool.is_active_operation  # type: ignore[union-attr]
    _release(main_window, QPointF(230, 200))
    (step,) = _steps(main_window)
    assert step.badge_size == pytest.approx(60.0)
    assert step.pos() == QPointF(200, 200)


def test_a_drag_under_ten_pixels_is_a_click(main_window: MainWindow) -> None:
    _tool(main_window)
    _press(main_window, QPointF(200, 200))
    _move(main_window, QPointF(204, 203))
    _release(main_window, QPointF(204, 203))
    (step,) = _steps(main_window)
    assert step.badge_size == 32.0


def test_drag_size_is_clamped_to_the_range(main_window: MainWindow) -> None:
    _tool(main_window)
    _press(main_window, QPointF(200, 200))
    _move(main_window, QPointF(600, 200))
    _release(main_window, QPointF(600, 200))
    assert _steps(main_window)[0].badge_size == 128.0


def test_placement_takes_the_creation_defaults(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    tool.creation_defaults.update(
        {
            "badge_color": QColor("#00aa00"),
            "text_color": QColor("#111111"),
            "badge_shape": BadgeShape.HEXAGON,
            "badge_size": 48.0,
            "display_mode": DisplayMode.LETTER,
            "font_weight": FontWeight.NORMAL,
            "border_width": 0.0,
            "border_color": QColor("#0000ff"),
            "border_style": BorderStyle.DOTTED,
            "shadow_enabled": False,
        }
    )
    _click(main_window, QPointF(10, 10))
    (step,) = _steps(main_window)
    assert step.badge_color.name() == "#00aa00"
    assert step.text_color.name() == "#111111"
    assert step.badge_shape is BadgeShape.HEXAGON
    assert step.badge_size == 48.0
    assert step.display_mode is DisplayMode.LETTER
    assert step.font_weight is FontWeight.NORMAL
    assert step.border_width == 0.0
    assert step.border_color.name() == "#0000ff"
    assert step.border_style is BorderStyle.DOTTED
    assert step.shadow_enabled is False


def test_text_mode_does_not_advance_the_counter(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    tool.creation_defaults["display_mode"] = DisplayMode.TEXT
    _click(main_window, QPointF(10, 10))
    assert tool.next_number == 1


def test_locked_or_hidden_layer_refuses_with_the_message(
    main_window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    _tool(main_window)
    layer = main_window.scene.layer_manager.active_layer
    assert layer is not None
    main_window.scene.layer_manager.set_locked(layer.layer_id, True)
    _click(main_window, QPointF(10, 10))
    assert _steps(main_window) == []
    assert unmet_messages[-1] == ("Numbered Step", "Numbered Step needs an unlocked active layer.")
    main_window.scene.layer_manager.set_locked(layer.layer_id, False)
    main_window.scene.layer_manager.set_visibility(layer.layer_id, False)
    _click(main_window, QPointF(10, 10))
    assert _steps(main_window) == []
    assert unmet_messages[-1] == ("Numbered Step", "Numbered Step needs a visible active layer.")


# --- the counter (Sections 2.3 and 7.1) ---


def test_counter_survives_a_tool_switch(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    _click(main_window, QPointF(10, 10))
    _click(main_window, QPointF(60, 10))
    main_window.tool_manager.activate("select")
    main_window.tool_manager.activate("numbered_step")
    assert tool.next_number == 3
    _click(main_window, QPointF(110, 10))
    assert _steps(main_window)[-1].number_value == 3


def test_counter_is_per_project_and_a_new_project_starts_over(
    main_window: MainWindow,
) -> None:
    tool = _tool(main_window)
    _click(main_window, QPointF(10, 10))
    _click(main_window, QPointF(60, 10))
    first = main_window.scene
    main_window._file_new()  # noqa: SLF001
    assert main_window.scene is not first
    main_window.tool_manager.activate("numbered_step")
    assert tool.next_number == 1
    _click(main_window, QPointF(10, 10))
    assert _steps(main_window)[0].number_value == 1
    # Back on the first project the sequence continues where it left off
    main_window._documents.set_active_index(0)  # noqa: SLF001
    main_window.tool_manager.activate("numbered_step")
    assert main_window.scene is first
    assert tool.next_number == 3


def test_a_loaded_project_continues_from_its_highest_step(
    main_window: MainWindow, tmp_path: Path, scene: SnapScene
) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    for n in (4, 9, 2):
        scene.command_stack.push(
            AddItemCommand(scene, NumberedStepItem(number_value=n), layer.layer_id)
        )
    text = NumberedStepItem(number_value=50)
    text.display_mode = DisplayMode.TEXT  # a text-mode step does not count
    scene.command_stack.push(AddItemCommand(scene, text, layer.layer_id))
    path = tmp_path / "steps.smk"
    save_project(scene, path)
    loaded = load_project(path)
    main_window._add_document(Document(loaded, parent=main_window))  # noqa: SLF001
    tool = _tool(main_window)
    assert main_window.scene is loaded
    assert tool.next_number == 10


def test_starting_number_sets_the_next_number_and_the_counter_continues_from_it(
    main_window: MainWindow,
) -> None:
    tool = _tool(main_window)
    _click(main_window, QPointF(10, 10))
    spin = _bar(main_window).shared_widgets["start_number"]
    assert isinstance(spin, QSpinBox)
    spin.setValue(10)
    assert tool.next_number == 10
    _click(main_window, QPointF(60, 10))
    _click(main_window, QPointF(110, 10))
    assert [s.number_value for s in _steps(main_window)] == [1, 10, 11]
    assert tool.creation_defaults["start_number"] == 10  # the default, not the counter


# --- the Tool Options Bar (Section 2.7) ---


def test_bar_composes_the_section_2_7_controls_in_order(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    bar = _bar(main_window)
    widgets = bar.shared_widgets
    assert list(widgets) == [
        "badge_color",
        "text_color",
        "badge_shape",
        "badge_size",
        "start_number",
        "display_mode",
        "font_weight",
        "border_width",
        "border_color",
        "border_style",
        "shadow_enabled",
    ]
    assert isinstance(widgets["badge_color"], ColorPicker)
    shape = widgets["badge_shape"]
    assert isinstance(shape, QComboBox)
    assert shape.count() == len(BadgeShape)
    assert all(not shape.itemIcon(i).isNull() for i in range(shape.count()))
    size = widgets["badge_size"]
    assert isinstance(size, QSpinBox)
    assert (size.minimum(), size.maximum()) == (16, 128)
    assert isinstance(widgets["shadow_enabled"], QCheckBox)
    buttons = [b for b in bar.findChildren(QPushButton) if b.text() == "Renumber All"]
    assert len(buttons) == 1
    # Every control reads the tool's defaults
    assert shape.currentData() is BadgeShape.CIRCLE
    assert widgets["shadow_enabled"].isChecked()  # type: ignore[attr-defined]
    assert tool.creation_defaults["badge_shape"] is BadgeShape.CIRCLE


def test_bar_edits_reach_the_creation_defaults(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    widgets = _bar(main_window).shared_widgets
    shape = widgets["badge_shape"]
    assert isinstance(shape, QComboBox)
    shape.setCurrentIndex(shape.findData(BadgeShape.PIN))
    assert tool.creation_defaults["badge_shape"] is BadgeShape.PIN
    mode = widgets["display_mode"]
    assert isinstance(mode, QComboBox)
    mode.setCurrentIndex(mode.findData(DisplayMode.ROMAN))
    assert tool.creation_defaults["display_mode"] is DisplayMode.ROMAN
    weight = widgets["font_weight"]
    assert isinstance(weight, QComboBox)
    weight.setCurrentIndex(weight.findData(FontWeight.NORMAL))
    assert tool.creation_defaults["font_weight"] is FontWeight.NORMAL
    style = widgets["border_style"]
    assert isinstance(style, QComboBox)
    style.setCurrentIndex(style.findData(BorderStyle.DASHED))
    assert tool.creation_defaults["border_style"] is BorderStyle.DASHED
    shadow = widgets["shadow_enabled"]
    assert isinstance(shadow, QCheckBox)
    shadow.setChecked(False)
    assert tool.creation_defaults["shadow_enabled"] is False
    size = widgets["badge_size"]
    assert isinstance(size, QSpinBox)
    size.setValue(64)
    assert tool.creation_defaults["badge_size"] == 64
    _click(main_window, QPointF(10, 10))
    (step,) = _steps(main_window)
    assert step.badge_shape is BadgeShape.PIN
    assert step.display_mode is DisplayMode.ROMAN
    assert step.badge_size == 64.0
    assert step.shadow_enabled is False


def test_bar_reads_a_theme_or_preset_change_back(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    tool.creation_defaults["badge_shape"] = BadgeShape.STAR
    tool.creation_defaults["shadow_enabled"] = False
    main_window.tool_manager.tool_defaults_changed.emit("numbered_step")
    widgets = _bar(main_window).shared_widgets
    assert widgets["badge_shape"].currentData() is BadgeShape.STAR  # type: ignore[attr-defined]
    assert widgets["shadow_enabled"].isChecked() is False  # type: ignore[attr-defined]


def test_renumber_all_button_renumbers_in_reading_order(
    main_window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    _tool(main_window)
    bar = _bar(main_window)
    button = next(b for b in bar.findChildren(QPushButton) if b.text() == "Renumber All")
    button.click()
    assert unmet_messages[-1] == (
        "Renumber All Steps",
        "Renumber All Steps needs at least one numbered step.",
    )
    _click(main_window, QPointF(300, 300))  # placed first, sits lowest: becomes 3
    _click(main_window, QPointF(200, 100))  # top row, right: becomes 2
    _click(main_window, QPointF(100, 100))  # top row, left: becomes 1
    button.click()
    by_pos = {(s.pos().x(), s.pos().y()): s.number_value for s in _steps(main_window)}
    assert by_pos == {(100.0, 100.0): 1, (200.0, 100.0): 2, (300.0, 300.0): 3}
    main_window.scene.command_stack.undo()
    by_pos = {(s.pos().x(), s.pos().y()): s.number_value for s in _steps(main_window)}
    assert by_pos == {(300.0, 300.0): 1, (200.0, 100.0): 2, (100.0, 100.0): 3}


# --- presets and themes (General UI PRD 5.2; Phase 7) ---


def test_preset_codec_round_trips_the_numbered_step_values() -> None:
    values = {
        "badge_color": QColor("#cc0000"),
        "badge_shape": BadgeShape.PIN,
        "badge_size": 40.0,
        "start_number": 3,
        "display_mode": DisplayMode.LETTER,
        "font_weight": FontWeight.NORMAL,
        "border_width": 1.5,
        "border_style": BorderStyle.DASHDOTDOT,
        "shadow_enabled": False,
    }
    encoded = encode_values(values)
    assert encoded["badge_shape"] == {"$enum": "BadgeShape", "value": "pin"}
    assert decode_values(encoded) == values


def test_save_and_apply_a_preset_carries_the_new_keys(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    themes = main_window._tool_themes  # noqa: SLF001
    tool.creation_defaults["badge_shape"] = BadgeShape.DIAMOND
    tool.creation_defaults["shadow_enabled"] = False
    themes.save_preset("numbered_step", "Diamonds")
    tool.creation_defaults["badge_shape"] = BadgeShape.CIRCLE
    tool.creation_defaults["shadow_enabled"] = True
    assert themes.apply_preset("numbered_step", "Diamonds")
    assert tool.creation_defaults["badge_shape"] is BadgeShape.DIAMOND
    assert tool.creation_defaults["shadow_enabled"] is False


# --- RenumberStepsCommand (Section 6.1) ---


def test_renumber_command_records_assignments_and_skips_text_steps(scene: SnapScene) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    a = NumberedStepItem(number_value=7)
    a.setPos(50, 200)
    b = NumberedStepItem(number_value=1)
    b.setPos(300, 10)
    c = NumberedStepItem(number_value=4)
    c.setPos(10, 10)
    t = NumberedStepItem(number_value=99)
    t.display_mode = DisplayMode.TEXT
    t.setPos(0, 0)
    for item in (a, b, c, t):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    assert steps_in_reading_order(scene) == [c, b, a]
    command = RenumberStepsCommand(scene, 5)
    assert command.item_assignments == [(c.item_id, 4, 5), (b.item_id, 1, 6), (a.item_id, 7, 7)]
    assert command.description == "Renumber all steps"
    scene.command_stack.push(command)
    assert (c.number_value, b.number_value, a.number_value, t.number_value) == (5, 6, 7, 99)
    scene.command_stack.undo()
    assert (c.number_value, b.number_value, a.number_value) == (4, 1, 7)


def test_animation_scales_the_item_from_120_percent_to_100(
    qtbot: QtBot, scene: SnapScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tool_module, "ANIMATIONS_ENABLED", True)
    item = NumberedStepItem()
    scene.addItem(item)
    animation = tool_module.animate_placement(item, 1.2, 60, scene)
    assert animation is not None
    assert 1.0 < item.scale() <= 1.2 + 1e-6  # started at 120 percent, on its way down
    qtbot.waitUntil(lambda: item.scale() == 1.0, timeout=2000)
