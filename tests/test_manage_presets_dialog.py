"""The Manage Presets dialog (General UI PRD 11.9; Phase 7 step 4)."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor
from pytestqt.qtbot import QtBot

from snapmock.config.constants import BubbleShape, TailStyle
from snapmock.core.tool_themes import CUSTOM_LABEL, ToolThemeManager
from snapmock.main_window import MainWindow
from snapmock.ui.manage_presets_dialog import ManagePresetsDialog, summarise_values
from snapmock.ui.tool_options_bar import ToolOptionsBar


def _themes(window: MainWindow) -> ToolThemeManager:
    return window._tool_themes  # noqa: SLF001


def _dialog(qtbot: QtBot, window: MainWindow, tool_id: str = "arrow") -> ManagePresetsDialog:
    tool = window.tool_manager.tool(tool_id)
    assert tool is not None
    dlg = ManagePresetsDialog(
        _themes(window), tool_id, tool.display_name, tool.options_controls, window
    )
    qtbot.addWidget(dlg)
    return dlg


def _seed(window: MainWindow, tool_id: str, *names: str) -> None:
    tool = window.tool_manager.tool(tool_id)
    assert tool is not None
    for i, name in enumerate(names):
        tool.creation_defaults["stroke_width"] = float(i + 1)
        _themes(window).save_preset(tool_id, name)
    _themes(window).reset_to_theme(tool_id)


def test_summary_lists_swatches_widths_and_enumerations() -> None:
    text = summarise_values(
        {
            "stroke_color": QColor("#FF0000"),
            "fill_color": QColor(0, 0, 0, 0),
            "stroke_width": 2.5,
            "opacity_pct": 100.0,
            "bold": True,
            "italic": False,
            "font_family": "Serif",
            "bubble_shape": BubbleShape.ROUNDED_RECT,
            "tail_style": TailStyle.CURVED,
        },
        ("stroke_width", "stroke_color"),
    )
    assert text.startswith("Width 2.5 px &middot; Stroke <span")
    assert "#FF0000" in text and "Fill transparent" in text
    assert "Opacity 100 %" in text
    assert "Bold" in text and "Italic" not in text
    assert "Font Serif" in text
    assert "Bubble rounded rect" in text and "Tail curved" in text


def test_dialog_title_rows_and_summaries(main_window: MainWindow, qtbot: QtBot) -> None:
    _seed(main_window, "arrow", "Zed", "alpha")
    dlg = _dialog(qtbot, main_window)
    assert dlg.windowTitle() == "Manage Arrow Presets"
    assert dlg.preset_names() == ["alpha", "Zed"]
    assert "Width 2 px" in dlg.summary_text(0)
    assert "Width 1 px" in dlg.summary_text(1)
    assert dlg._list.accessibleName() == "Arrow presets"  # noqa: SLF001


def test_rename_inline_applies_and_follows_the_applied_preset(
    main_window: MainWindow, qtbot: QtBot
) -> None:
    _seed(main_window, "arrow", "One", "Two")
    themes = _themes(main_window)
    themes.apply_preset("arrow", "Two")
    dlg = _dialog(qtbot, main_window)
    dlg.select("Two")
    dlg._rename()  # noqa: SLF001
    item = dlg._list.currentItem()  # noqa: SLF001
    assert item is not None
    item.setText(0, "  Deux ")
    assert themes.preset_names("arrow") == ["Deux", "One"]
    assert themes.applied_preset("arrow") == "Deux"
    assert dlg.preset_names() == ["Deux", "One"]
    assert dlg._selected_name() == "Deux"  # noqa: SLF001


def test_rename_rejects_empty_and_taken_names(
    main_window: MainWindow, qtbot: QtBot, unmet_messages: list[tuple[str, str]]
) -> None:
    _seed(main_window, "arrow", "One", "Two")
    dlg = _dialog(qtbot, main_window)
    dlg.select("One")
    item = dlg._list.currentItem()  # noqa: SLF001
    assert item is not None
    item.setText(0, "")
    assert unmet_messages == [("Rename", "Rename needs a name.")]
    assert dlg.preset_names() == ["One", "Two"]
    item = dlg._list.currentItem()  # noqa: SLF001
    assert item is not None
    item.setText(0, "Two")
    assert unmet_messages[-1] == ("Rename", 'Rename needs a name not already used ("Two" is).')
    assert _themes(main_window).preset_names("arrow") == ["One", "Two"]


def test_duplicate_and_delete(
    main_window: MainWindow,
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    unmet_messages: list[tuple[str, str]],
) -> None:
    _seed(main_window, "rectangle", "Green")
    themes = _themes(main_window)
    dlg = _dialog(qtbot, main_window, "rectangle")
    assert dlg.windowTitle() == "Manage Rectangle Presets"
    dlg._duplicate()  # noqa: SLF001
    assert dlg.preset_names() == ["Green", "Green Copy"]
    assert dlg._selected_name() == "Green Copy"  # noqa: SLF001

    themes.apply_preset("rectangle", "Green Copy")
    monkeypatch.setattr(ManagePresetsDialog, "_confirm_delete", lambda self, name: False)
    dlg._delete()  # noqa: SLF001
    assert themes.preset_names("rectangle") == ["Green", "Green Copy"]
    monkeypatch.setattr(ManagePresetsDialog, "_confirm_delete", lambda self, name: True)
    dlg._delete()  # noqa: SLF001
    assert themes.preset_names("rectangle") == ["Green"]
    assert dlg.preset_names() == ["Green"]
    assert themes.applied_preset("rectangle") is None
    assert themes.current_label("rectangle") == CUSTOM_LABEL

    dlg._list.clear()  # noqa: SLF001
    dlg._rename()  # noqa: SLF001
    dlg._duplicate()  # noqa: SLF001
    dlg._delete()  # noqa: SLF001
    assert [m[1] for m in unmet_messages] == [
        "Rename needs a preset selected.",
        "Duplicate needs a preset selected.",
        "Delete needs a preset selected.",
    ]


def test_dropdown_row_opens_the_dialog_or_says_what_is_missing(
    main_window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    unmet_messages: list[tuple[str, str]],
) -> None:
    main_window.tool_manager.activate("ellipse")
    bar = main_window._tool_options  # noqa: SLF001
    bar._populate_preset_menu()  # noqa: SLF001
    menu = bar._preset_menu  # noqa: SLF001
    assert menu is not None
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts == ["Save as Preset...", "Manage Presets...", "Reset to Theme"]
    bar._manage_presets()  # noqa: SLF001
    assert unmet_messages == [
        ("Manage Presets", "Manage Presets needs at least one saved preset for the Ellipse tool.")
    ]

    _seed(main_window, "ellipse", "Round")
    opened: list[str] = []
    monkeypatch.setattr(
        ManagePresetsDialog, "exec", lambda self: opened.append(self.windowTitle()) or 0
    )
    bar._manage_presets()  # noqa: SLF001
    assert opened == ["Manage Ellipse Presets"]
    assert isinstance(bar, ToolOptionsBar)
