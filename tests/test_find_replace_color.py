"""Edit > Select All Text and Edit > Find/Replace Color (General UI PRD 3.2)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.callout_item import CalloutItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem
from snapmock.main_window import MainWindow
from snapmock.ui.find_replace_color_dialog import (
    FindReplaceColorDialog,
    color_matches,
    replace_color_command,
)


@pytest.fixture()
def window(qtbot: QtBot) -> MainWindow:
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def _add(window: MainWindow, item: RectangleItem | TextItem | CalloutItem) -> None:
    layer = window.scene.layer_manager.active_layer
    assert layer is not None
    window.scene.command_stack.push(AddItemCommand(window.scene, item, layer.layer_id))


def test_select_all_text_selects_text_and_callouts_only(window: MainWindow) -> None:
    _add(window, RectangleItem(rect=QRectF(0, 0, 10, 10)))
    text = TextItem(text="hello")
    callout = CalloutItem()
    _add(window, text)
    _add(window, callout)
    window.tool_manager.activate("rectangle")
    window._edit_select_all_text()  # noqa: SLF001
    assert set(window.selection_manager.items) == {text, callout}
    assert window.tool_manager.active_tool_id == "select"
    window.scene.command_stack.mark_clean()


def test_select_all_text_skips_locked_layers_and_explains_when_none(
    window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    window._edit_select_all_text()  # noqa: SLF001
    assert unmet_messages == [
        ("Select All Text", "Select All Text needs at least one text-containing item.")
    ]
    _add(window, TextItem(text="hello"))
    layer = window.scene.layer_manager.active_layer
    assert layer is not None
    layer.locked = True
    window._edit_select_all_text()  # noqa: SLF001
    assert window.selection_manager.count == 0
    layer.locked = False
    window.scene.command_stack.mark_clean()


def test_color_matches_and_replace_are_undoable(window: MainWindow) -> None:
    red = QColor("#FF0000")
    blue = QColor("#0000FF")
    a = RectangleItem(rect=QRectF(0, 0, 10, 10))
    a.stroke_color = red
    a.fill_color = red
    b = RectangleItem(rect=QRectF(20, 0, 10, 10))
    b.stroke_color = QColor("#00FF00")
    t = TextItem(text="x")
    t.text_color = red
    for item in (a, b, t):
        _add(window, item)
    matches = color_matches(window.scene, red)
    assert sorted((type(i).__name__, p) for i, p in matches) == [
        ("RectangleItem", "fill_color"),
        ("RectangleItem", "stroke_color"),
        ("TextItem", "text_color"),
    ]
    window.scene.command_stack.push(replace_color_command(matches, red, blue))
    assert a.stroke_color.rgba() == blue.rgba()
    assert a.fill_color.rgba() == blue.rgba()
    assert t.text_color.rgba() == blue.rgba()
    assert b.stroke_color.name() == "#00ff00"
    window.scene.command_stack.undo()
    assert a.stroke_color.rgba() == red.rgba()
    assert t.text_color.rgba() == red.rgba()
    window.scene.command_stack.mark_clean()


def test_dialog_counts_and_replaces(window: MainWindow, qtbot: QtBot) -> None:
    a = RectangleItem(rect=QRectF(0, 0, 10, 10))
    a.stroke_color = QColor("#123456")
    _add(window, a)
    dlg = FindReplaceColorDialog(window.scene, window)
    qtbot.addWidget(dlg)
    dlg.find_color = QColor("#123456")
    assert dlg.match_count == 1
    assert dlg._count_label.text() == "1 colour in 1 item"  # noqa: SLF001
    dlg.replace_color = QColor("#654321")
    dlg.replace_all()
    assert a.stroke_color.name() == "#654321"
    assert dlg.match_count == 0
    window.scene.command_stack.mark_clean()
