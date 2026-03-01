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


def test_all_eight_menus_exist(window: MainWindow) -> None:
    titles = _menu_titles(window)
    expected = ["&File", "&Edit", "&View", "&Image", "&Layer", "&Arrange", "&Tools", "&Help"]
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


def test_arrange_actions_disabled_with_no_selection(window: MainWindow) -> None:
    """Arrange z-order actions should be disabled when nothing is selected."""
    window.selection_manager.deselect_all()
    window._update_menu_states()  # noqa: SLF001
    assert window._bring_front_action is not None  # noqa: SLF001
    assert not window._bring_front_action.isEnabled()  # noqa: SLF001
    assert window._bring_forward_action is not None  # noqa: SLF001
    assert not window._bring_forward_action.isEnabled()  # noqa: SLF001
    assert window._send_backward_action is not None  # noqa: SLF001
    assert not window._send_backward_action.isEnabled()  # noqa: SLF001
    assert window._send_to_back_action is not None  # noqa: SLF001
    assert not window._send_to_back_action.isEnabled()  # noqa: SLF001


def test_layer_delete_disabled_with_single_layer(window: MainWindow) -> None:
    """Cannot delete the only layer."""
    assert window.scene.layer_manager.count == 1
    window._update_menu_states()  # noqa: SLF001
    assert window._layer_delete_action is not None  # noqa: SLF001
    assert not window._layer_delete_action.isEnabled()  # noqa: SLF001
