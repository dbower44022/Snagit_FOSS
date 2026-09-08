"""Tests for menu structure completeness."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QMenu
from pytestqt.qtbot import QtBot

from snapmock.main_window import MainWindow


@pytest.fixture()
def window(qtbot: QtBot) -> MainWindow:
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def _menu_titles(window: MainWindow) -> list[str]:
    """Return the text of all top-level menus."""
    menu_bar = window.menuBar()
    assert menu_bar is not None
    return [a.text() for a in menu_bar.actions() if isinstance(a.menu(), QMenu)]


def test_all_ten_menus_exist(window: MainWindow) -> None:
    titles = _menu_titles(window)
    expected = [
        "&File",
        "&Edit",
        "&View",
        "&Image",
        "&Layer",
        "&Arrange",
        "&Tools",
        "Li&brary",
        "&Capture",
        "&Help",
    ]
    assert titles == expected


def test_tools_menu_has_all_registered_tools(window: MainWindow) -> None:
    """Every registered tool should appear as a checkable action in the Tools menu."""
    tool_ids = window.tool_manager.tool_ids
    assert len(tool_ids) >= 18  # noqa: PLR2004
    # All tool_ids should have a corresponding action
    for tid in tool_ids:
        assert tid in window._tool_actions, f"Tool '{tid}' missing from Tools menu"  # noqa: SLF001


def test_active_tool_is_checked(window: MainWindow) -> None:
    """The currently active tool should be checked in the Tools menu."""
    active_id = window.tool_manager.active_tool_id
    actions = window._tool_actions  # noqa: SLF001
    for tid, action in actions.items():
        if tid == active_id:
            assert action.isChecked(), f"Active tool '{tid}' should be checked"
        else:
            assert not action.isChecked(), f"Inactive tool '{tid}' should not be checked"


def test_tool_check_updates_on_switch(window: MainWindow) -> None:
    """Switching tools should update the checkmark."""
    window.tool_manager.activate("rectangle")
    actions = window._tool_actions  # noqa: SLF001
    assert actions["rectangle"].isChecked()
    assert not actions["select"].isChecked()

    window.tool_manager.activate("select")
    assert actions["select"].isChecked()
    assert not actions["rectangle"].isChecked()


def test_no_menu_action_is_ever_disabled(window: MainWindow) -> None:
    """Never-disabled controls (General UI PRD 1.3): every menu row stays enabled."""
    window.selection_manager.deselect_all()
    assert window.scene.layer_manager.count == 1
    menu_bar = window.menuBar()
    assert menu_bar is not None

    def _walk(menu: QMenu) -> list[str]:
        disabled: list[str] = []
        for action in menu.actions():
            if action.isSeparator():
                continue
            if not action.isEnabled():
                disabled.append(action.text())
            sub = action.menu()
            if isinstance(sub, QMenu):
                disabled.extend(_walk(sub))
        return disabled

    disabled: list[str] = []
    for top in menu_bar.actions():
        sub = top.menu()
        if isinstance(sub, QMenu):
            disabled.extend(_walk(sub))
    assert disabled == []


def test_arrange_actions_explain_unmet_selection(
    window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    """With nothing selected, Bring to Front says what it needs instead of graying out."""
    window.selection_manager.deselect_all()
    assert window._bring_front_action is not None  # noqa: SLF001
    assert window._bring_front_action.isEnabled()  # noqa: SLF001
    window._bring_front_action.trigger()  # noqa: SLF001
    assert unmet_messages == [
        ("Bring to Front", "Bring to Front needs at least one item selected.")
    ]


def test_layer_delete_explains_with_single_layer(
    window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    """The only layer cannot be deleted; the row says so when triggered."""
    assert window.scene.layer_manager.count == 1
    assert window._layer_delete_action is not None  # noqa: SLF001
    assert window._layer_delete_action.isEnabled()  # noqa: SLF001
    window._layer_delete_action.trigger()  # noqa: SLF001
    assert unmet_messages == [("Delete Layer", "Delete Layer needs more than one layer.")]
    assert window.scene.layer_manager.count == 1


def test_recent_files_placeholder_explains(
    window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    assert window._recent_menu is not None  # noqa: SLF001
    rows = [a for a in window._recent_menu.actions() if not a.isSeparator()]  # noqa: SLF001
    assert len(rows) == 1
    assert rows[0].isEnabled()
    rows[0].trigger()
    assert unmet_messages == [("Open Recent", "Open Recent needs a recently opened file.")]
