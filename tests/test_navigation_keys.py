"""Navigation shortcuts of General UI PRD 12.2 and 12.3: Tab cycling, Home/End, Alt eyedropper."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QRectF, Qt
from PyQt6.QtGui import QKeyEvent
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.tools.select_tool import SelectTool


@pytest.fixture()
def window(qtbot: QtBot) -> MainWindow:
    w = MainWindow()
    qtbot.addWidget(w)
    w.tool_manager.activate("select")
    return w


def _key(
    key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)


def _release(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier)


def _add(window: MainWindow, x: float) -> RectangleItem:
    layer = window.scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 10, 10))
    item.setPos(x, 0)
    window.scene.command_stack.push(AddItemCommand(window.scene, item, layer.layer_id))
    return item


def _selected(window: MainWindow) -> list[str]:
    return [i.item_id for i in window.selection_manager.items if isinstance(i, RectangleItem)]


def test_tab_cycles_selection_through_the_active_layer(window: MainWindow) -> None:
    a, b, c = _add(window, 0), _add(window, 20), _add(window, 40)
    tool = window.tool_manager.active_tool
    assert isinstance(tool, SelectTool)
    assert tool.key_press(_key(Qt.Key.Key_Tab))
    assert _selected(window) == [a.item_id]
    tool.key_press(_key(Qt.Key.Key_Tab))
    assert _selected(window) == [b.item_id]
    tool.key_press(_key(Qt.Key.Key_Tab))
    tool.key_press(_key(Qt.Key.Key_Tab))
    assert _selected(window) == [a.item_id]  # wraps
    tool.key_press(_key(Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier))
    assert _selected(window) == [c.item_id]
    window.scene.command_stack.mark_clean()


def test_tab_on_an_empty_layer_is_not_consumed(window: MainWindow) -> None:
    tool = window.tool_manager.active_tool
    assert isinstance(tool, SelectTool)
    assert tool.key_press(_key(Qt.Key.Key_Tab)) is False


def test_view_routes_tab_to_the_tool_before_focus_changes(window: MainWindow) -> None:
    a = _add(window, 0)
    assert window.view.event(_key(Qt.Key.Key_Tab)) is True
    assert _selected(window) == [a.item_id]
    window.scene.command_stack.mark_clean()


def test_home_and_end_pan_to_the_canvas_corners(window: MainWindow) -> None:
    window.resize(1200, 800)
    window.show()
    view = window.view
    view.set_zoom(100)
    window.keyPressEvent(_key(Qt.Key.Key_Home))
    origin = view.mapFromScene(0, 0)
    assert abs(origin.x()) <= 2 and abs(origin.y()) <= 2
    window.keyPressEvent(_key(Qt.Key.Key_End))
    canvas = window.scene.canvas_size
    corner = view.mapFromScene(canvas.width(), canvas.height())
    viewport = view.viewport()
    assert viewport is not None
    assert abs(corner.x() - viewport.width()) <= 2
    assert abs(corner.y() - viewport.height()) <= 2


def test_alt_is_a_momentary_eyedropper(window: MainWindow) -> None:
    window.tool_manager.activate("rectangle")
    window.keyPressEvent(_key(Qt.Key.Key_Alt, Qt.KeyboardModifier.AltModifier))
    assert window.tool_manager.active_tool_id == "eyedropper"
    window.keyReleaseEvent(_release(Qt.Key.Key_Alt))
    assert window.tool_manager.active_tool_id == "rectangle"
