"""The shape tools' Tool Options Bar and presets after the Vector Item Properties work
(Basic Shape PRD 2.6; General UI PRD 5.2; decision 2, option A: the opacity migration)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QCheckBox, QComboBox, QSpinBox
from pytestqt.qtbot import QtBot

from snapmock.config.constants import BorderStyle, StrokeCap, StrokeJoin
from snapmock.core.tool_themes import (
    CUSTOM_LABEL,
    ToolPreset,
    ToolTheme,
    decode_value,
    encode_value,
    migrate_opacity,
)
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem
from snapmock.main_window import MainWindow
from snapmock.ui.manage_presets_dialog import summarise_values
from snapmock.ui.tool_options_bar import ToolOptionsBar

Button = Qt.MouseButton
Modifier = Qt.KeyboardModifier

CLOSED = [
    "stroke_color",
    "fill_color",
    "stroke_width",
    "stroke_style",
    "fill_opacity",
    "stroke_opacity",
    "shadow_enabled",
]
OPEN = ["stroke_color", "stroke_width", "stroke_style", "stroke_opacity", "shadow_enabled"]


def _bar(window: MainWindow) -> ToolOptionsBar:
    return window._tool_options  # noqa: SLF001


def _event(kind: QEvent.Type, window: MainWindow, scene_pos: QPointF) -> QMouseEvent:
    view_pos = QPointF(window.view.mapFromScene(scene_pos))
    return QMouseEvent(kind, view_pos, Button.LeftButton, Button.LeftButton, Modifier.NoModifier)


def _drag(window: MainWindow, start: QPointF, end: QPointF) -> None:
    tm = window.tool_manager
    tm.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, window, start))
    tm.handle_mouse_move(_event(QEvent.Type.MouseMove, window, end))
    tm.handle_mouse_release(_event(QEvent.Type.MouseButtonRelease, window, end))


def test_every_shape_tool_composes_the_basic_shape_prd_order(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    expected = {
        "rectangle": CLOSED,
        "ellipse": CLOSED,
        "line": OPEN,
        "arrow": OPEN,
        "freehand": [*OPEN, "smoothing"],
        # Phase 2 rebuilt the Highlighter's bar per Blur PRD 3.5
        "highlight": [
            "highlight_color",
            "highlight_width",
            "blend_mode",
            "stroke_style",
            "shadow_enabled",
        ],
    }
    for tool_id, keys in expected.items():
        main_window.tool_manager.activate(tool_id)
        assert list(bar.shared_widgets) == keys, tool_id
        tool = main_window.tool_manager.tool(tool_id)
        assert tool is not None and "opacity_pct" not in tool.creation_defaults
    main_window.tool_manager.activate("callout")
    assert list(bar.shared_widgets)[-1] == "border_style"


def test_the_opacity_sliders_hold_percent_and_store_a_fraction(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    main_window.tool_manager.activate("rectangle")
    tool = main_window.tool_manager.tool("rectangle")
    assert tool is not None
    fill = bar.shared_widgets["fill_opacity"]
    assert isinstance(fill, QSpinBox) and fill.value() == 100 and fill.suffix() == "%"
    fill.setValue(35)
    assert tool.creation_defaults["fill_opacity"] == pytest.approx(0.35)
    tool.creation_defaults["stroke_opacity"] = 0.6
    main_window.tool_manager.tool_defaults_changed.emit("rectangle")
    stroke = bar.shared_widgets["stroke_opacity"]
    assert isinstance(stroke, QSpinBox) and stroke.value() == 60


def test_bar_edits_reach_the_next_rectangle(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    main_window.tool_manager.activate("rectangle")
    style = bar.shared_widgets["stroke_style"]
    assert isinstance(style, QComboBox)
    style.setCurrentIndex(style.findData(BorderStyle.DOTTED))
    fill = bar.shared_widgets["fill_opacity"]
    assert isinstance(fill, QSpinBox)
    fill.setValue(40)
    shadow = bar.shared_widgets["shadow_enabled"]
    assert isinstance(shadow, QCheckBox)
    shadow.setChecked(True)
    _drag(main_window, QPointF(10, 10), QPointF(120, 80))
    items = [i for i in main_window.scene.annotation_items() if isinstance(i, RectangleItem)]
    assert len(items) == 1
    item = items[0]
    assert item.stroke_style is BorderStyle.DOTTED
    assert item.fill_opacity == pytest.approx(0.4)
    assert item.stroke_opacity == 1.0
    assert item.shadow_enabled is True
    assert item.opacity() == 1.0


def test_the_text_tool_border_style_reaches_a_new_text_box(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    main_window.tool_manager.activate("text")
    style = bar.shared_widgets["border_style"]
    assert isinstance(style, QComboBox)
    style.setCurrentIndex(style.findData(BorderStyle.DASHED))
    tm = main_window.tool_manager
    tm.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, main_window, QPointF(30, 30)))
    tm.handle_mouse_release(_event(QEvent.Type.MouseButtonRelease, main_window, QPointF(30, 30)))
    items = [i for i in main_window.scene.annotation_items() if isinstance(i, TextItem)]
    assert items and items[0].border_style is BorderStyle.DASHED


def test_a_preset_round_trips_the_new_values(main_window: MainWindow) -> None:
    themes = main_window._tool_themes  # noqa: SLF001
    tool = main_window.tool_manager.tool("ellipse")
    assert tool is not None
    tool.creation_defaults.update(
        {"stroke_style": BorderStyle.DASHDOT, "fill_opacity": 0.25, "shadow_enabled": True}
    )
    main_window.tool_manager.tool_defaults_changed.emit("ellipse")
    themes.save_preset("ellipse", "Faint")
    themes.reset_to_theme("ellipse")
    assert tool.creation_defaults["fill_opacity"] == 1.0
    assert themes.apply_preset("ellipse", "Faint")
    assert tool.creation_defaults["stroke_style"] is BorderStyle.DASHDOT
    assert tool.creation_defaults["fill_opacity"] == 0.25
    assert tool.creation_defaults["shadow_enabled"] is True
    assert themes.current_label("ellipse") == "Faint"


def test_a_stored_opacity_pct_is_read_once_into_both_opacities(
    main_window: MainWindow, tmp_path: Path
) -> None:
    """A preset, theme, or session state from before the work (decision 2's silence)."""
    themes = main_window._tool_themes  # noqa: SLF001
    tool = main_window.tool_manager.tool("rectangle")
    assert tool is not None
    old_values = {
        "stroke_color": {"$color": "#FFFF0000"},
        "fill_color": {"$color": "#00000000"},
        "stroke_width": 2.0,
        "opacity_pct": 40.0,
    }
    preset_dir = tmp_path / "snapmock-data" / "presets" / "rectangle"
    preset_dir.mkdir(parents=True)
    (preset_dir / "half.json").write_text(
        json.dumps(
            {"format_version": 1, "tool_id": "rectangle", "name": "Half", "values": old_values}
        )
    )
    assert themes.apply_preset("rectangle", "Half")
    assert tool.creation_defaults["fill_opacity"] == pytest.approx(0.4)
    assert tool.creation_defaults["stroke_opacity"] == pytest.approx(0.4)
    assert "opacity_pct" not in tool.creation_defaults
    assert themes.current_label("rectangle") == "Half"  # the migrated preset still matches
    # Update Preset writes the new keys and drops the old one.
    tool.creation_defaults["fill_opacity"] = 0.5
    main_window.tool_manager.tool_defaults_changed.emit("rectangle")
    assert themes.preset_is_modified("rectangle")
    assert themes.update_preset("rectangle")
    written = json.loads((preset_dir / "half.json").read_text())["values"]
    assert "opacity_pct" not in written and written["fill_opacity"] == 0.5
    # A theme carrying the old key gives the tool both opacities.
    theme = ToolTheme("Old", {"rectangle": dict(tool.creation_defaults, opacity_pct=70.0)})
    theme.tools["rectangle"].pop("fill_opacity")
    theme.tools["rectangle"].pop("stroke_opacity")
    values = themes.theme_values("rectangle", theme)
    assert values["fill_opacity"] == pytest.approx(0.7)
    assert values["stroke_opacity"] == pytest.approx(0.7)
    assert "opacity_pct" not in values


def test_migrate_opacity_rules() -> None:
    defaults = {"fill_opacity": 1.0, "stroke_opacity": 1.0}
    assert migrate_opacity({"opacity_pct": 50.0}, defaults) == {
        "fill_opacity": 0.5,
        "stroke_opacity": 0.5,
    }
    # A stroke-only tool takes the one key it has.
    assert migrate_opacity({"opacity_pct": 50.0}, {"stroke_opacity": 1.0}) == {
        "stroke_opacity": 0.5
    }
    # A tool that still takes opacity_pct (stamp, emoji) is left alone.
    assert migrate_opacity({"opacity_pct": 50.0}, {"opacity_pct": 100.0}) == {"opacity_pct": 50.0}
    # New keys present: the old key is dropped, not applied.
    assert migrate_opacity({"opacity_pct": 50.0, "fill_opacity": 0.9}, defaults) == {
        "opacity_pct": 50.0,
        "fill_opacity": 0.9,
    }
    assert migrate_opacity({"stroke_width": 2.0}, defaults) == {"stroke_width": 2.0}


def test_the_codec_knows_the_cap_and_join_and_the_summary_reads_percent() -> None:
    for value in (StrokeCap.SQUARE, StrokeJoin.MITER, BorderStyle.DOTTED):
        assert decode_value(encode_value(value)) is value
    text = summarise_values(
        {
            "stroke_style": BorderStyle.DASHED,
            "fill_opacity": 0.4,
            "stroke_opacity": 1.0,
            "shadow_enabled": True,
        }
    )
    assert "Style dashed" in text
    assert "Fill Opacity 40 %" in text and "Stroke Opacity 100 %" in text
    assert "Shadow" in text


def test_a_migrated_session_state_restores_the_shape_tools(
    main_window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    themes = main_window._tool_themes  # noqa: SLF001
    themes.save_session()
    state_path = tmp_path / "snapmock-data" / "tool_state.json"
    state = json.loads(state_path.read_text())
    state["tools"]["line"]["values"] = {
        "stroke_color": {"$color": "#FF00FF00"},
        "stroke_width": 3.0,
        "opacity_pct": 30.0,
    }
    state_path.write_text(json.dumps(state))
    second = MainWindow()
    qtbot.addWidget(second)
    line = second.tool_manager.tool("line")
    assert line is not None
    assert line.creation_defaults["stroke_opacity"] == pytest.approx(0.3)
    assert line.creation_defaults["stroke_width"] == 3.0
    assert "opacity_pct" not in line.creation_defaults
    assert second._tool_themes.current_label("line") == CUSTOM_LABEL  # noqa: SLF001
    assert isinstance(ToolPreset("line", "x", {}), ToolPreset)
