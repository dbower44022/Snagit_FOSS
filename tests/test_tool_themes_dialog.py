"""The Tool Themes dialog and the Tools menu's theme rows (General UI PRD 3.7, 11.8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QWidgetAction
from pytestqt.qtbot import QtBot

from snapmock.core.tool_themes import DEFAULT_THEME_NAME, ToolThemeManager, write_theme_file
from snapmock.main_window import MainWindow
from snapmock.ui.tool_themes_dialog import ToolThemesDialog


def _themes(window: MainWindow) -> ToolThemeManager:
    return window._tool_themes  # noqa: SLF001


def _dialog(qtbot: QtBot, window: MainWindow) -> ToolThemesDialog:
    dlg = ToolThemesDialog(_themes(window), window.tool_manager, window)
    qtbot.addWidget(dlg)
    return dlg


def _set_arrow_width(window: MainWindow, width: float) -> None:
    arrow = window.tool_manager.tool("arrow")
    assert arrow is not None
    arrow.creation_defaults["stroke_width"] = width
    window.tool_manager.tool_defaults_changed.emit("arrow")


def _tools_menu_rows(window: MainWindow) -> list[str]:
    menu_bar = window.menuBar()
    assert menu_bar is not None
    for action in menu_bar.actions():
        if action.text() == "&Tools":
            menu = action.menu()
            assert menu is not None
            return [a.text() for a in menu.actions()]
    raise AssertionError("no Tools menu")


def test_tools_menu_ends_with_tool_themes_and_the_active_theme_label(
    main_window: MainWindow,
) -> None:
    rows = _tools_menu_rows(main_window)
    assert rows[-3] == "" and rows[-2] == "Tool Themes..."
    menu_bar = main_window.menuBar()
    assert menu_bar is not None
    tools = next(a.menu() for a in menu_bar.actions() if a.text() == "&Tools")
    assert tools is not None
    themes_action = tools.actions()[-2]
    assert not themes_action.icon().isNull()
    label_action = tools.actions()[-1]
    assert isinstance(label_action, QWidgetAction)
    label = label_action.defaultWidget()
    assert isinstance(label, QLabel)
    assert label.text() == "Active Theme: Default"
    assert label.accessibleName() == "Active tool theme"

    _set_arrow_width(main_window, 9.0)
    assert main_window.active_theme_text == "Active Theme: Default (modified)"
    _themes(main_window).reset_to_theme("arrow")
    assert main_window.active_theme_text == "Active Theme: Default"


def test_dialog_lists_themes_marks_the_active_one_and_previews(
    main_window: MainWindow, qtbot: QtBot
) -> None:
    themes = _themes(main_window)
    _set_arrow_width(main_window, 7.0)
    themes.capture_theme("Wide")
    dlg = _dialog(qtbot, main_window)
    assert dlg.theme_names() == [DEFAULT_THEME_NAME, "Wide"]
    assert dlg.display_texts() == ["✓ Default", "Wide"]
    assert dlg.selected_name() == DEFAULT_THEME_NAME
    assert "<b>Arrow</b>" in dlg.preview_text() and "Width 2 px" in dlg.preview_text()
    assert "<b>Callout</b>" in dlg.preview_text()
    dlg.select("Wide")
    assert "Width 7 px" in dlg.preview_text()


def test_apply_makes_the_theme_active_and_clears_overrides(
    main_window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    themes = _themes(main_window)
    _set_arrow_width(main_window, 7.0)
    dlg = _dialog(qtbot, main_window)
    monkeypatch.setattr(ToolThemesDialog, "_ask_name", lambda self, title, initial="": "Wide")
    dlg._new()  # noqa: SLF001
    assert dlg.selected_name() == "Wide"
    _set_arrow_width(main_window, 1.0)
    themes.save_preset("rectangle", "Thin")
    assert main_window.active_theme_text == "Active Theme: Default (modified)"

    dlg._apply()  # noqa: SLF001
    assert themes.active_theme_name == "Wide"
    arrow = main_window.tool_manager.tool("arrow")
    assert arrow is not None
    assert arrow.creation_defaults["stroke_width"] == 7.0
    assert themes.applied_preset("rectangle") is None
    assert main_window.active_theme_text == "Active Theme: Wide"
    assert dlg.display_texts() == ["Default", "✓ Wide"]
    main_window.tool_manager.activate("arrow")
    button = main_window._tool_options.preset_button  # noqa: SLF001
    assert button is not None and button.text() == "Wide ▾"


def test_new_needs_an_unused_name(
    main_window: MainWindow,
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    unmet_messages: list[tuple[str, str]],
) -> None:
    dlg = _dialog(qtbot, main_window)
    monkeypatch.setattr(ToolThemesDialog, "_ask_name", lambda self, title, initial="": "")
    dlg._new()  # noqa: SLF001
    assert unmet_messages == [("New", "New needs a name.")]
    monkeypatch.setattr(ToolThemesDialog, "_ask_name", lambda self, title, initial="": "Default")
    dlg._new()  # noqa: SLF001
    assert unmet_messages[-1] == ("New", 'New needs a name not already used ("Default" is).')
    monkeypatch.setattr(ToolThemesDialog, "_ask_name", lambda self, title, initial="": None)
    dlg._new()  # noqa: SLF001
    assert _themes(main_window).theme_names() == [DEFAULT_THEME_NAME]


def test_duplicate_rename_and_delete(
    main_window: MainWindow,
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    unmet_messages: list[tuple[str, str]],
) -> None:
    themes = _themes(main_window)
    dlg = _dialog(qtbot, main_window)
    dlg._duplicate()  # noqa: SLF001
    assert dlg.theme_names() == [DEFAULT_THEME_NAME, "Default Copy"]
    assert dlg.selected_name() == "Default Copy"

    dlg.select(DEFAULT_THEME_NAME)
    dlg._rename()  # noqa: SLF001
    assert unmet_messages[-1] == (
        "Rename",
        "Rename needs a theme other than the built-in Default.",
    )
    dlg._delete()  # noqa: SLF001
    assert unmet_messages[-1] == (
        "Delete",
        "Delete needs a theme other than the built-in Default.",
    )

    dlg.select("Default Copy")
    dlg._rename()  # noqa: SLF001
    item = dlg._list.currentItem()  # noqa: SLF001
    assert item is not None
    item.setText("Mine")
    assert themes.theme_names() == [DEFAULT_THEME_NAME, "Mine"]
    assert dlg.selected_name() == "Mine"
    dlg._rename()  # noqa: SLF001
    item = dlg._list.currentItem()  # noqa: SLF001
    assert item is not None
    item.setText("Default")
    assert unmet_messages[-1] == ("Rename", 'Rename needs a name not already used ("Default" is).')
    assert themes.theme_names() == [DEFAULT_THEME_NAME, "Mine"]

    themes.apply_theme("Mine")
    dlg.select("Mine")
    dlg._delete()  # noqa: SLF001
    assert unmet_messages[-1] == ("Delete", "Delete needs a theme that is not the active theme.")
    themes.apply_theme(DEFAULT_THEME_NAME)
    dlg.select("Mine")
    monkeypatch.setattr(ToolThemesDialog, "_confirm_delete", lambda self, name: False)
    dlg._delete()  # noqa: SLF001
    assert themes.theme_names() == [DEFAULT_THEME_NAME, "Mine"]
    monkeypatch.setattr(ToolThemesDialog, "_confirm_delete", lambda self, name: True)
    dlg._delete()  # noqa: SLF001
    assert themes.theme_names() == [DEFAULT_THEME_NAME]
    assert dlg.theme_names() == [DEFAULT_THEME_NAME]


def test_import_and_export(
    main_window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    themes = _themes(main_window)
    dlg = _dialog(qtbot, main_window)
    out = tmp_path / "default"
    monkeypatch.setattr(ToolThemesDialog, "_ask_export_path", lambda self, name: out)
    dlg._export()  # noqa: SLF001
    assert out.is_file()

    themed = tmp_path / "blue.smktheme"
    write_theme_file(
        themes.default_theme().__class__("Blue", {"arrow": {"stroke_color": QColor("#0000FF")}}),
        themed,
    )
    monkeypatch.setattr(ToolThemesDialog, "_ask_import_path", lambda self: themed)
    dlg._import()  # noqa: SLF001
    assert dlg.selected_name() == "Blue"
    assert "#0000FF" in dlg.preview_text()
    dlg._import()  # noqa: SLF001
    assert themes.theme_names() == ["Blue", "Blue 2", DEFAULT_THEME_NAME]

    errors: list[str] = []
    monkeypatch.setattr(ToolThemesDialog, "_show_error", lambda self, t, m: errors.append(m))
    bad = tmp_path / "bad.smktheme"
    bad.write_text("{")
    monkeypatch.setattr(ToolThemesDialog, "_ask_import_path", lambda self: bad)
    dlg._import()  # noqa: SLF001
    assert errors and errors[0].startswith("Cannot import bad.smktheme")
    monkeypatch.setattr(ToolThemesDialog, "_ask_import_path", lambda self: None)
    dlg._import()  # noqa: SLF001
    assert len(errors) == 1


def test_menu_row_opens_the_dialog(
    main_window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        ToolThemesDialog, "exec", lambda self: opened.append(self.windowTitle()) or 0
    )
    main_window._tools_tool_themes()  # noqa: SLF001
    assert opened == ["Tool Themes"]
