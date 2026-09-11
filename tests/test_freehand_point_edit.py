"""Freehand point editing (Basic Shape PRD 9.7; Basic Shape remainder Phase 2 step 3)."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPoint, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.freehand_item import FreehandItem
from snapmock.main_window import MainWindow
from snapmock.tools.point_edit import FreehandPointSession, HandleKind, split_cubic
from snapmock.tools.select_tool import SelectTool

ALT = Qt.KeyboardModifier.AltModifier
NONE = Qt.KeyboardModifier.NoModifier


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def _view(qtbot: QtBot, scene: SnapScene) -> SnapView:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(300, 200)
    return view


def _mouse(
    view: SnapView, kind: QEvent.Type, scene_pos: QPointF, modifiers: Qt.KeyboardModifier = NONE
) -> QMouseEvent:
    vp = QPointF(view.mapFromScene(scene_pos))
    button = Qt.MouseButton.LeftButton
    return QMouseEvent(kind, vp, vp, button, button, modifiers)


def _stroke(scene: SnapScene) -> FreehandItem:
    item = FreehandItem()
    for x in range(0, 301, 2):
        item.add_point(QPointF(x, 40 * math.sin(x / 50.0)))
    item.smooth(0.5)
    item.setPos(100, 150)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _editing(qtbot: QtBot, scene: SnapScene) -> tuple[SnapView, SelectTool, FreehandItem]:
    view = _view(qtbot, scene)
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    item = _stroke(scene)
    assert tool.enter_point_edit(item)
    return view, tool, item


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


def _close(a: QPointF, b: QPointF, tol: float = 0.51) -> bool:
    return QLineF(a, b).length() <= tol


def test_a_double_click_enters_with_the_bezier_handles(qtbot: QtBot, scene: SnapScene) -> None:
    view = _view(qtbot, scene)
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    item = _stroke(scene)
    on_path = item.mapToScene(item.path.pointAtPercent(0.5))
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, on_path))
    session = tool.point_session
    assert isinstance(session, FreehandPointSession)
    n = len(item.bezier_segments)
    handles = session.handles()
    assert len(handles) == 3 * n + 1
    assert [h.kind for h in handles[: 2 * n]] == [HandleKind.OFF_CURVE] * (2 * n)
    assert [h.kind for h in handles[2 * n :]] == [HandleKind.ON_CURVE] * (n + 1)
    assert len(session.guide_lines()) == 2 * n
    assert "Alt+drag: corner" in tool.status_hint


def test_an_on_curve_point_carries_its_handles_and_alt_makes_a_corner(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view, tool, item = _editing(qtbot, scene)
    before = item.bezier_segments
    assert len(before) >= 2
    point = item.mapToScene(before[1][0])
    _drag(tool, view, point, point + QPointF(0, 30))
    after = item.bezier_segments
    shift = QPointF(0, 30)
    assert _close(after[1][0], before[1][0] + shift) and _close(after[0][3], before[1][0] + shift)
    assert _close(after[0][2], before[0][2] + shift) and _close(after[1][1], before[1][1] + shift)
    assert scene.command_stack.undo_text == "Edit Freehand geometry"
    scene.command_stack.undo()
    assert item.bezier_segments == before
    _drag(tool, view, point, point + QPointF(0, 30), ALT)
    cornered = item.bezier_segments
    assert _close(cornered[1][0], before[1][0] + shift)
    assert cornered[0][2] == before[0][2] and cornered[1][1] == before[1][1]


def test_a_handle_turns_its_opposite_and_alt_leaves_it(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _editing(qtbot, scene)
    before = item.bezier_segments
    anchor = before[1][0]
    handle = item.mapToScene(before[1][1])
    target = handle + QPointF(-10, -25)
    _drag(tool, view, handle, target)
    after = item.bezier_segments
    moved = after[1][1] - anchor
    opposite = after[0][2] - anchor
    cross = moved.x() * opposite.y() - moved.y() * opposite.x()
    dot = moved.x() * opposite.x() + moved.y() * opposite.y()
    assert abs(cross) < 1e-6 * max(1.0, abs(dot)) and dot < 0  # in line, pointing away
    assert QLineF(anchor, after[0][2]).length() == pytest.approx(
        QLineF(anchor, before[0][2]).length()
    )
    scene.command_stack.undo()
    _drag(tool, view, handle, target, ALT)
    assert item.bezier_segments[0][2] == before[0][2]


def test_a_double_click_inserts_a_point_without_changing_the_curve(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view, tool, item = _editing(qtbot, scene)
    count = len(item.bezier_segments)
    samples = [item.path.pointAtPercent(k / 20) for k in range(21)]
    where = item.mapToScene(item.path.pointAtPercent(0.37))
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, where))
    assert len(item.bezier_segments) == count + 1
    dense = [item.path.pointAtPercent(k / 800) for k in range(801)]
    for sample in samples:  # every old point still lies on the new path
        assert min(QLineF(sample, p).length() for p in dense) <= 0.6
    scene.command_stack.undo()
    assert len(item.bezier_segments) == count
    left, right = split_cubic(
        (QPointF(0, 0), QPointF(0, 10), QPointF(10, 10), QPointF(10, 0)), 0.5
    )
    assert left[3] == right[0] == QPointF(5, 7.5)


def _right_click(tool: SelectTool, view: SnapView, scene_pos: QPointF) -> bool:
    vp = view.mapFromScene(scene_pos)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, vp, QPoint(0, 0))
    return tool.context_menu(event)


def test_a_right_click_deletes_an_on_curve_point_keeping_two(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view, tool, item = _editing(qtbot, scene)
    segs = item.bezier_segments
    count = len(segs)
    assert _right_click(tool, view, item.mapToScene(segs[1][0]))
    after = item.bezier_segments
    assert len(after) == count - 1
    assert after[0][0] == segs[0][0] and after[0][3] == segs[1][3]  # the two segments merged
    scene.command_stack.undo()
    assert item.bezier_segments == segs
    item.bezier_segments = segs[:1]
    assert _right_click(tool, view, item.mapToScene(segs[0][0]))  # no menu opens...
    assert len(item.bezier_segments) == 1  # ...and two points remain


def test_a_resmooth_replaces_a_hand_edit(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _editing(qtbot, scene)
    fitted = item.bezier_segments
    point = item.mapToScene(fitted[1][0])
    _drag(tool, view, point, point + QPointF(0, 30))
    assert item.bezier_segments != fitted
    item.smooth(item.smoothing)
    assert item.bezier_segments == fitted


def test_alt_does_not_start_the_eyedropper_while_editing_points(main_window: MainWindow) -> None:
    main_window.tool_manager.activate("select")
    tool = main_window.tool_manager.active_tool
    assert isinstance(tool, SelectTool)
    item = _stroke(main_window.scene)
    assert tool.enter_point_edit(item)
    main_window.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Alt, ALT))
    assert main_window.tool_manager.active_tool_id == "select"
    assert tool.point_session is not None
