"""The Eyedropper's properties and Tool Options Bar (Blur PRD 4.4, 4.5).

Decision 3 of the Eyedropper and Blur performance work, option A: 4.5's bar in full, with
General UI PRD 5.3's two Apply buttons replaced by the Apply Target dropdown.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import QComboBox, QWidget

from snapmock.config.constants import ApplyTarget, ColorFormat
from snapmock.main_window import MainWindow
from snapmock.tools.eyedropper_tool import EyedropperTool, format_color_value
from snapmock.ui.accessibility import describe, unnamed_controls
from snapmock.ui.tool_options_bar import ToolOptionsBar


def _bar(window: MainWindow) -> ToolOptionsBar:
    return window._tool_options  # noqa: SLF001


def _tool(window: MainWindow) -> EyedropperTool:
    window.tool_manager.activate("eyedropper")
    tool = window.tool_manager.tool("eyedropper")
    assert isinstance(tool, EyedropperTool)
    return tool


def _combo(bar: ToolOptionsBar, name: str) -> QComboBox:
    combos = [c for c in bar.findChildren(QComboBox) if c.accessibleName() == name]
    assert combos, name
    return combos[0]


# ---- the colour value and its three formats (4.4, 4.5) ----


def test_each_format_writes_the_prds_own_spelling() -> None:
    blue = QColor("#4A90D9")  # 4.4's own example
    assert format_color_value(blue, ColorFormat.HEX) == "#4A90D9"
    assert format_color_value(blue, ColorFormat.RGB) == "rgb (74, 144, 217)"
    # 4.4's own example reads "210°, 63%, 57%"; the saturation of #4A90D9 is 65 percent
    # (143 of 219), so the PRD's figure is rounded from something else and the standard
    # value is written instead (notes Section 7).
    assert format_color_value(blue, ColorFormat.HSL) == "210°, 65%, 57%"
    assert format_color_value(QColor(0, 0, 0, 0), ColorFormat.HEX) == "transparent"
    assert format_color_value(QColor(), ColorFormat.RGB) == "transparent"


def test_the_format_dropdown_rewrites_the_value(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tool = _tool(main_window)
    bar.show_picked_color(QColor("#4A90D9"))
    assert bar.eyedropper_value_text == "#4A90D9"
    combo = _combo(bar, "Color format")
    combo.setCurrentIndex(combo.findData(ColorFormat.RGB))
    assert tool.color_format is ColorFormat.RGB
    assert bar.eyedropper_value_text == "rgb (74, 144, 217)"
    combo.setCurrentIndex(combo.findData(ColorFormat.HSL))
    assert bar.eyedropper_value_text == "210°, 65%, 57%"


# ---- the sample size toggles (4.5) ----


def test_the_sample_size_toggles_reach_the_tool(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tool = _tool(main_window)
    assert tool.sample_size == 1
    buttons = bar.eyedropper_size_buttons
    assert buttons[1].isChecked()
    buttons[5].click()
    assert tool.sample_size == 5  # noqa: PLR2004
    assert not buttons[1].isChecked()
    assert buttons[5].isChecked()
    # A preset or a theme writing the default puts the bar back in step.
    tool.creation_defaults["sample_size"] = 11
    main_window.tool_manager.tool_defaults_changed.emit("eyedropper")
    assert bar.eyedropper_size_buttons[11].isChecked()


def test_the_apply_target_dropdown_reaches_the_tool(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tool = _tool(main_window)
    assert tool.apply_target is ApplyTarget.STROKE_COLOR
    combo = _combo(bar, "Apply target")
    assert [combo.itemData(i) for i in range(combo.count())] == [
        ApplyTarget.STROKE_COLOR,
        ApplyTarget.FILL_COLOR,
        ApplyTarget.TEXT_COLOR,
    ]
    combo.setCurrentIndex(combo.findData(ApplyTarget.TEXT_COLOR))
    assert tool.apply_target is ApplyTarget.TEXT_COLOR


# ---- the colour history (4.5) ----


def test_the_history_is_newest_first_deduplicated_and_capped(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tool = _tool(main_window)
    for index in range(10):
        bar.show_picked_color(QColor(index * 20, 0, 0))
    history = tool.color_history
    assert len(history) == 8  # noqa: PLR2004
    assert history[0] == QColor(180, 0, 0)  # newest first
    assert history[-1] == QColor(40, 0, 0)  # the two oldest fell off
    bar.show_picked_color(QColor(40, 0, 0))  # already in the list, further down
    assert tool.color_history[0] == QColor(40, 0, 0)
    assert len(tool.color_history) == 8  # noqa: PLR2004
    assert [c for c in tool.color_history].count(QColor(40, 0, 0)) == 1
    # A transparent sample is not a colour to remember.
    bar.show_picked_color(QColor(0, 0, 0, 0))
    assert tool.color_history[0] == QColor(40, 0, 0)


def test_a_click_on_a_history_swatch_re_applies_that_colour(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tool = _tool(main_window)
    bar.show_picked_color(QColor("#112233"))
    bar.show_picked_color(QColor("#445566"))
    swatches = bar.eyedropper_history_swatches
    assert swatches[0].isVisibleTo(bar) and swatches[1].isVisibleTo(bar)
    assert not swatches[2].isVisibleTo(bar)
    swatches[1].click()  # the older of the two
    assert tool.last_sampled_color == QColor("#112233")
    assert bar.eyedropper_value_text == "#112233"
    rectangle = main_window.tool_manager.tool("rectangle")
    assert rectangle is not None
    assert rectangle.creation_defaults["stroke_color"] == QColor("#112233")


# ---- the clipboard (4.4, 4.5) ----


def test_the_clipboard_toggle_copies_every_sample(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tool = _tool(main_window)
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    clipboard.setText("untouched")
    bar.show_picked_color(QColor("#4A90D9"))
    assert clipboard.text() == "untouched"  # the toggle is off by default
    tool.creation_defaults["copy_to_clipboard"] = True
    bar.show_picked_color(QColor("#4A90D9"))
    assert clipboard.text() == "#4A90D9"


def test_a_click_on_the_value_field_copies_what_it_reads(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tool = _tool(main_window)
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    clipboard.setText("untouched")
    bar.show_picked_color(QColor("#4A90D9"))
    tool.creation_defaults["color_format"] = ColorFormat.RGB
    main_window.tool_manager.tool_defaults_changed.emit("eyedropper")
    field = bar._eyedropper_value  # noqa: SLF001
    assert field is not None
    field.clicked.emit()
    assert clipboard.text() == "rgb (74, 144, 217)"


# ---- the properties are captured by a preset and a theme (General UI PRD 5.2) ----


def test_the_four_properties_are_creation_defaults(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    assert set(tool.creation_defaults) == {
        "sample_size",
        "color_format",
        "apply_target",
        "copy_to_clipboard",
    }
    themes = main_window._tool_themes  # noqa: SLF001
    assert "eyedropper" in themes.tool_ids
    values = themes.current_values("eyedropper")
    assert values["sample_size"] == 1
    assert values["color_format"] is ColorFormat.HEX


def test_every_new_control_is_named(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    _tool(main_window)
    missing = unnamed_controls(bar)
    assert missing == [], "\n".join(describe(w) for w in missing)
    assert all(isinstance(w, QWidget) for w in bar.findChildren(QWidget))
