"""Applying a sampled colour, the momentary Alt mode, and the hints (Blur PRD 4.6 to 4.8).

``ApplyEyedropperColorCommand`` is 6.2's command; it replaces the macro of property
commands the Apply to Stroke and Apply to Fill buttons pushed before this work.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QRectF, Qt
from PyQt6.QtGui import QColor, QKeyEvent
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.eyedropper_commands import ApplyEyedropperColorCommand
from snapmock.config.constants import ApplyTarget, ColorFormat
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem
from snapmock.main_window import MainWindow, momentary_pick_key
from snapmock.tools.eyedropper_tool import EyedropperTool
from snapmock.tools.text_tool import TextTool
from snapmock.ui.tool_options_bar import ToolOptionsBar

ALT = Qt.KeyboardModifier.AltModifier


def _bar(window: MainWindow) -> ToolOptionsBar:
    return window._tool_options  # noqa: SLF001


def _eyedropper(window: MainWindow) -> EyedropperTool:
    tool = window.tool_manager.tool("eyedropper")
    assert isinstance(tool, EyedropperTool)
    return tool


def _rect(window: MainWindow, color: str = "#000000") -> RectangleItem:
    scene = window.scene
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 40, 30))
    item.stroke_color = QColor(color)
    item.fill_color = QColor(color)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _key(
    key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)


def _release(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier)


# ---- 6.2, the command ----


def test_the_command_restores_each_items_own_colour(main_window: MainWindow) -> None:
    first = _rect(main_window, "#111111")
    second = _rect(main_window, "#222222")
    command = ApplyEyedropperColorCommand([first, second], "stroke_color", QColor("#FF0000"))
    assert command.description == "Apply eyedropper color"
    main_window.scene.command_stack.push(command)
    assert first.stroke_color == QColor("#FF0000")
    assert second.stroke_color == QColor("#FF0000")
    main_window.scene.command_stack.undo()
    assert first.stroke_color == QColor("#111111")
    assert second.stroke_color == QColor("#222222")
    main_window.scene.command_stack.redo()
    assert second.stroke_color == QColor("#FF0000")


def test_the_command_leaves_out_an_item_without_the_property(main_window: MainWindow) -> None:
    rect = _rect(main_window)
    text = TextItem("hello")
    command = ApplyEyedropperColorCommand([rect, text], "corner_radius_mode", QColor("#FF0000"))
    assert command.items == []  # nothing carries that as a colour


# ---- 4.6, the three apply routes ----


def test_route_one_sets_the_previous_tools_default(main_window: MainWindow) -> None:
    tm = main_window.tool_manager
    tm.activate("rectangle")
    tm.activate("eyedropper")
    _bar(main_window)._on_color_applied(QColor("#FF8800"))  # noqa: SLF001
    rectangle = tm.tool("rectangle")
    assert rectangle is not None
    assert rectangle.creation_defaults["stroke_color"] == QColor("#FF8800")
    # The tool the Eyedropper was not reached from is left alone.
    line = tm.tool("line")
    assert line is not None
    assert line.creation_defaults["stroke_color"] != QColor("#FF8800")


def test_route_two_applies_to_the_selection_undoably(main_window: MainWindow) -> None:
    tm = main_window.tool_manager
    item = _rect(main_window, "#111111")
    main_window.selection_manager.select_items([item])
    tm.activate("rectangle")
    tm.activate("eyedropper")
    tool = _eyedropper(main_window)
    tool.creation_defaults["apply_target"] = ApplyTarget.FILL_COLOR
    _bar(main_window)._on_color_applied(QColor("#00FF00"))  # noqa: SLF001
    assert item.fill_color == QColor("#00FF00")
    stack = main_window.scene.command_stack
    assert stack.undo_text == "Apply eyedropper color"
    stack.undo()
    assert item.fill_color == QColor("#111111")


def test_route_three_reaches_every_tool_when_there_is_neither(main_window: MainWindow) -> None:
    tm = main_window.tool_manager
    tm.activate("eyedropper")
    tm._last_tool_id = None  # noqa: SLF001
    tm._previous_tool_id = None  # noqa: SLF001
    _bar(main_window)._on_color_applied(QColor("#0000FF"))  # noqa: SLF001
    for tool_id in ("rectangle", "line", "freehand", "arrow"):
        other = tm.tool(tool_id)
        assert other is not None
        assert other.creation_defaults["stroke_color"] == QColor("#0000FF")


# ---- 4.7, the momentary Alt mode ----


def test_alt_names_the_tool_it_picks_for_and_shows_the_loupe(main_window: MainWindow) -> None:
    main_window.tool_manager.activate("rectangle")
    main_window.keyPressEvent(_key(Qt.Key.Key_Alt, ALT))
    tool = _eyedropper(main_window)
    assert main_window.tool_manager.active_tool_id == "eyedropper"
    assert tool.momentary_from == "Rectangle"
    assert "click to sample color for Rectangle" in tool.status_hint
    main_window.keyReleaseEvent(_release(Qt.Key.Key_Alt))
    assert main_window.tool_manager.active_tool_id == "rectangle"
    assert tool.momentary_from is None


def test_alt_released_without_a_click_changes_nothing(main_window: MainWindow) -> None:
    tm = main_window.tool_manager
    tm.activate("rectangle")
    rectangle = tm.tool("rectangle")
    assert rectangle is not None
    before = QColor(rectangle.creation_defaults["stroke_color"])
    main_window.keyPressEvent(_key(Qt.Key.Key_Alt, ALT))
    main_window.keyReleaseEvent(_release(Qt.Key.Key_Alt))
    assert rectangle.creation_defaults["stroke_color"] == before
    tool = _eyedropper(main_window)
    assert tool.pick_serial == 0
    assert tool.loupe is None or tool.loupe.isHidden()


def test_the_momentary_pick_sets_each_tools_own_primary_colour(main_window: MainWindow) -> None:
    """4.7: the stroke colour for a shape, the highlight colour for the Highlighter, the
    text colour for the Text tool, and the badge colour for the Numbered Step tool."""
    tm = main_window.tool_manager
    tool = _eyedropper(main_window)
    for tool_id, key in (
        ("rectangle", "stroke_color"),
        ("highlight", "highlight_color"),
        ("text", "text_color"),
        ("numbered_step", "badge_color"),
    ):
        other = tm.tool(tool_id)
        assert other is not None
        assert momentary_pick_key(other) == key
        tm.activate(tool_id)
        main_window._momentary_pick_serial = tool.pick_serial  # noqa: SLF001
        tool._picked_color = QColor("#123456")  # noqa: SLF001
        tool._pick_serial += 1  # noqa: SLF001
        main_window._apply_momentary_pick()  # noqa: SLF001
        assert other.creation_defaults[key] == QColor("#123456"), tool_id


def test_a_tool_with_no_colour_takes_nothing(main_window: MainWindow) -> None:
    tm = main_window.tool_manager
    for tool_id in ("select", "crop", "pan", "zoom"):
        other = tm.tool(tool_id)
        assert other is not None
        assert momentary_pick_key(other) is None


def test_alt_stands_down_during_inline_text_editing(main_window: MainWindow) -> None:
    """4.7: Alt is reserved in text editing. The Text tool reports the edit as an active
    operation, which the Alt branch already refuses."""
    tm = main_window.tool_manager
    tm.activate("text")
    tool = tm.active_tool
    assert isinstance(tool, TextTool)
    item = TextItem("hello")
    layer = main_window.scene.layer_manager.active_layer
    assert layer is not None
    main_window.scene.command_stack.push(AddItemCommand(main_window.scene, item, layer.layer_id))
    tool._start_editing(item)  # noqa: SLF001
    assert tool.editing_item is item
    assert tool.is_active_operation
    main_window.keyPressEvent(_key(Qt.Key.Key_Alt, ALT))
    assert tm.active_tool_id == "text"
    assert _eyedropper(main_window).momentary_from is None
    tool.cancel()


# ---- 4.8, the hints ----


def test_each_hint_of_4_8(main_window: MainWindow) -> None:
    tm = main_window.tool_manager
    tm.activate("eyedropper")
    tool = _eyedropper(main_window)
    # Idle, with the sample size and the target named.
    assert tool.status_hint == (
        "Click to sample a color. Drag to preview. Sample: 1x1 | Target: Stroke Color."
    )
    tool.creation_defaults["sample_size"] = 5
    tool.creation_defaults["apply_target"] = ApplyTarget.FILL_COLOR
    assert "Sample: 5x5 | Target: Fill Color." in tool.status_hint
    # Dragging: the colour under the cursor, and what the release will do.
    tool._sampling = True  # noqa: SLF001
    tool._preview_color = QColor("#4A90D9")  # noqa: SLF001
    assert tool.status_hint == "Sampling: #4A90D9 (rgb 74,144,217). Release to apply."
    tool._sampling = False  # noqa: SLF001
    # After sampling: what was sampled and where it went.
    tool._picked_color = QColor("#4A90D9")  # noqa: SLF001
    assert tool.status_hint == ("Sampled: #4A90D9. Applied to Fill Color. Click to sample again.")
    # The momentary mode names the tool it is picking for.
    tool.set_momentary_from("Arrow")
    assert tool.status_hint == (
        "Eyedropper: click to sample color for Arrow. Release Alt to cancel."
    )


def test_the_hint_reaches_the_status_bar(main_window: MainWindow, qapp: QApplication) -> None:
    main_window.tool_manager.activate("eyedropper")
    tool = _eyedropper(main_window)
    tool._picked_color = QColor("#4A90D9")  # noqa: SLF001
    tool.show_hint()
    label = main_window._status_bar._hint_label  # noqa: SLF001
    assert "Sampled: #4A90D9" in label.text()


def test_the_value_text_follows_the_format(main_window: MainWindow) -> None:
    main_window.tool_manager.activate("eyedropper")
    tool = _eyedropper(main_window)
    tool._picked_color = QColor("#4A90D9")  # noqa: SLF001
    assert tool.value_text() == "#4A90D9"
    tool.creation_defaults["color_format"] = ColorFormat.RGB
    assert tool.value_text() == "rgb (74, 144, 217)"
    assert tool.value_text(QColor("#000000")) == "rgb (0, 0, 0)"
