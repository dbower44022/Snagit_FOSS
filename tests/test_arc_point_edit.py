"""Arc point editing (Basic Shape PRD 7.5; Basic Shape remainder Phase 3 step 2)."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.arc_item import ArcItem
from snapmock.tools.point_edit import ArcPointSession, HandleKind
from snapmock.tools.select_tool import SelectTool

NONE = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def _setup(qtbot: QtBot, scene: SnapScene) -> tuple[SnapView, SelectTool, ArcItem]:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(300, 200)
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    item = ArcItem(start=QPointF(0, 0), end=QPointF(200, 0), control=QPointF(100, -160))
    item.setPos(100, 250)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return view, tool, item


def _mouse(
    view: SnapView, kind: QEvent.Type, pos: QPointF, modifiers: Qt.KeyboardModifier = NONE
) -> QMouseEvent:
    vp = QPointF(view.mapFromScene(pos))
    button = Qt.MouseButton.LeftButton
    return QMouseEvent(kind, vp, vp, button, button, modifiers)


def _drag(
    tool: SelectTool,
    view: SnapView,
    start: QPointF,
    end: QPointF,
    modifiers: Qt.KeyboardModifier = NONE,
) -> None:
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, start, modifiers))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, end, modifiers))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, end, modifiers))


def test_a_double_click_shows_the_three_handles(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _setup(qtbot, scene)
    on_curve = item.mapToScene(item.peak())
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, on_curve))
    session = tool.point_session
    assert isinstance(session, ArcPointSession)
    handles = session.handles()
    assert [(h.key, h.kind) for h in handles] == [
        ("start", HandleKind.ENDPOINT),
        ("end", HandleKind.ENDPOINT),
        ("control", HandleKind.CONTROL),
    ]
    assert handles[2].pos == QPointF(200, 90)
    assert len(session.guide_lines()) == 2
    assert tool.status_hint == "Drag endpoints or control point to reshape. Escape: exit."


def test_the_control_point_sets_the_curvature_with_undo(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _setup(qtbot, scene)
    tool.enter_point_edit(item)
    _drag(tool, view, QPointF(200, 90), QPointF(200, 170))
    assert item.control_point == QPointF(100, -80)
    assert scene.command_stack.undo_text == "Edit Arc geometry"
    scene.command_stack.undo()
    assert item.control_point == QPointF(100, -160)


def test_shift_constrains_an_endpoint_to_15_degree_chords(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _setup(qtbot, scene)
    tool.enter_point_edit(item)
    _drag(tool, view, QPointF(300, 250), QPointF(290, 150), SHIFT)
    end = item.mapToScene(item.end_point)
    angle = math.degrees(math.atan2(end.y() - 250, end.x() - 100))
    assert angle == pytest.approx(round(angle / 15) * 15, abs=1e-6)
    assert item.start_point == QPointF(0, 0)
    _drag(tool, view, QPointF(100, 250), QPointF(120, 230))
    assert item.start_point == QPointF(20, -20)


def test_escape_leaves(qtbot: QtBot, scene: SnapScene) -> None:
    _view, tool, item = _setup(qtbot, scene)
    tool.enter_point_edit(item)
    assert tool.key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, NONE))
    assert tool.point_session is None
