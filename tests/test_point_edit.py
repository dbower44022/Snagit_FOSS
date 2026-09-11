"""Point-editing mode of the Select tool (Basic Shape PRD 3.5, 4.8, 11.3; Basic Shape
remainder decision 1) and the 15-degree constraint of 3.2 while drawing."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.geometry_commands import ModifyGeometryCommand
from snapmock.core.path_utils import constrain_angle
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.line_item import LineItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.tools.arrow_tool import ArrowTool
from snapmock.tools.line_tool import LineTool
from snapmock.tools.point_edit import ArrowPointSession, LinePointSession
from snapmock.tools.select_tool import SelectTool

SHIFT = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def _view_for(qtbot: QtBot, scene: SnapScene) -> SnapView:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(300, 200)
    return view


def _mouse(
    view: SnapView,
    kind: QEvent.Type,
    scene_pos: QPointF,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
) -> QMouseEvent:
    vp_pos = QPointF(view.mapFromScene(scene_pos))
    return QMouseEvent(kind, vp_pos, vp_pos, button, button, modifiers)


def _add(scene: SnapScene, item: SnapGraphicsItem) -> SnapGraphicsItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _line(scene: SnapScene) -> LineItem:
    line = LineItem(QLineF(0, 0, 200, 0))
    line.setPos(100, 100)
    _add(scene, line)
    return line


def _tool(scene: SnapScene) -> tuple[SelectTool, SelectionManager]:
    sm = SelectionManager(scene)
    tool = SelectTool()
    tool.activate(scene, sm)
    return tool, sm


def _drag(
    tool: SelectTool,
    view: SnapView,
    start: QPointF,
    end: QPointF,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, start, modifiers))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, end, modifiers))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, end, modifiers))


def _handle_positions(tool: SelectTool) -> list[tuple[float, float]]:
    assert tool.point_handles is not None
    return [(round(h.pos.x(), 1), round(h.pos.y(), 1)) for h in tool.point_handles.handles]


def test_a_double_click_on_a_line_enters_point_editing(qtbot: QtBot, scene: SnapScene) -> None:
    view = _view_for(qtbot, scene)
    tool, sm = _tool(scene)
    line = _line(scene)
    assert tool.mouse_double_click(
        _mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(200, 100))
    )
    assert isinstance(tool.point_session, LinePointSession)
    assert sm.items == [line]
    assert _handle_positions(tool) == [(100.0, 100.0), (300.0, 100.0)]
    handles = tool.point_handles
    assert handles is not None and handles.scene() is scene
    assert handles.zValue() > 999997  # above the transform handles' layer of the scene
    assert tool._handles is not None and tool._handles.scene() is None  # noqa: SLF001
    assert tool.status_hint == "Drag endpoints to reshape. Shift: constrain angle. Escape: exit."


def test_an_item_without_points_does_not_enter(qtbot: QtBot, scene: SnapScene) -> None:
    view = _view_for(qtbot, scene)
    tool, sm = _tool(scene)
    rect = RectangleItem(rect=QRectF(0, 0, 100, 60))
    rect.fill_color = rect.stroke_color
    rect.setPos(100, 100)
    _add(scene, rect)
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(150, 130)))
    assert tool.point_session is None
    assert sm.items == [rect]


def test_dragging_an_endpoint_is_one_undoable_geometry_edit(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view_for(qtbot, scene)
    tool, _sm = _tool(scene)
    line = _line(scene)
    assert tool.enter_point_edit(line)
    _drag(tool, view, QPointF(300, 100), QPointF(300, 180))
    assert line.line.p2() == QPointF(200, 80)
    assert line.line.p1() == QPointF(0, 0)
    assert scene.command_stack.undo_text == "Edit Line geometry"
    assert _handle_positions(tool)[1] == (300.0, 180.0)
    scene.command_stack.undo()
    assert line.line.p2() == QPointF(200, 0)
    assert _handle_positions(tool)[1] == (300.0, 100.0)  # the handles follow an undo
    scene.command_stack.redo()
    assert line.line.p2() == QPointF(200, 80)
    assert tool.point_session is not None  # the mode survives the edits


def test_shift_constrains_the_drag_to_15_degree_steps(qtbot: QtBot, scene: SnapScene) -> None:
    view = _view_for(qtbot, scene)
    tool, _sm = _tool(scene)
    line = _line(scene)
    tool.enter_point_edit(line)
    _drag(tool, view, QPointF(300, 100), QPointF(300, 250), SHIFT)
    end = line.mapToScene(line.line.p2())
    angle = math.degrees(math.atan2(end.y() - 100, end.x() - 100))
    assert angle == pytest.approx(30.0, abs=0.01)  # 36.9 degrees snaps to 30
    assert math.hypot(end.x() - 100, end.y() - 100) == pytest.approx(250.0, abs=1.0)


def test_drags_of_one_point_within_300_ms_merge(scene: SnapScene) -> None:
    line = _line(scene)
    stack = scene.command_stack
    before = stack.count
    a, b, c = QLineF(0, 0, 200, 0), QLineF(0, 0, 200, 10), QLineF(0, 0, 200, 20)
    stack.push(ModifyGeometryCommand(line, "line", a, b, point="end", timestamp=10.0))
    stack.push(ModifyGeometryCommand(line, "line", b, c, point="end", timestamp=10.2))
    assert stack.count == before + 1
    stack.push(ModifyGeometryCommand(line, "line", c, a, point="start", timestamp=10.3))
    stack.push(ModifyGeometryCommand(line, "line", a, b, point="start", timestamp=10.9))
    assert stack.count == before + 3  # another point, then the same point 600 ms later
    stack.undo()
    stack.undo()
    stack.undo()
    assert line.line == a


def test_escape_a_click_away_and_a_new_selection_leave_the_mode(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view_for(qtbot, scene)
    tool, sm = _tool(scene)
    line = _line(scene)
    other = _add(scene, LineItem(QLineF(0, 0, 100, 0)))
    other.setPos(100, 300)

    tool.enter_point_edit(line)
    assert tool.key_press(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    )
    assert tool.point_session is None
    assert sm.items == [line]
    assert tool._handles is not None and tool._handles.scene() is scene  # noqa: SLF001

    tool.enter_point_edit(line)
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(200, 100)))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(200, 100)))
    assert tool.point_session is not None  # a press on the item keeps the mode
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(500, 500)))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(500, 500)))
    assert tool.point_session is None
    assert tool.point_handles is None

    tool.enter_point_edit(line)
    sm.select(other)
    assert tool.point_session is None


def test_deleting_the_item_leaves_the_mode(qtbot: QtBot, scene: SnapScene) -> None:
    _view_for(qtbot, scene)
    tool, _sm = _tool(scene)
    line = _line(scene)
    tool.enter_point_edit(line)
    tool.key_press(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    )
    assert line.scene() is None
    assert tool.point_session is None


def test_the_window_escape_leaves_the_mode_and_keeps_the_selection(
    main_window: MainWindow,
) -> None:
    main_window.tool_manager.activate("select")
    tool = main_window.tool_manager.active_tool
    assert isinstance(tool, SelectTool)
    line = _line(main_window.scene)
    assert tool.enter_point_edit(line)
    main_window._edit_deselect()  # noqa: SLF001 — the Escape shortcut's slot
    assert tool.point_session is None
    assert main_window.selection_manager.items == [line]
    main_window._edit_deselect()  # noqa: SLF001
    assert main_window.selection_manager.items == []


def test_an_arrow_edits_its_endpoints(qtbot: QtBot, scene: SnapScene) -> None:
    view = _view_for(qtbot, scene)
    tool, _sm = _tool(scene)
    arrow = ArrowItem(QLineF(0, 0, 200, 0))
    arrow.setPos(100, 100)
    _add(scene, arrow)
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(200, 100)))
    assert isinstance(tool.point_session, ArrowPointSession)
    _drag(tool, view, QPointF(100, 100), QPointF(120, 40))
    assert arrow.line.p1() == QPointF(20, -60)
    assert scene.command_stack.undo_text == "Edit Arrow geometry"


def test_a_flipped_line_shows_its_handles_where_it_paints(qtbot: QtBot, scene: SnapScene) -> None:
    _view_for(qtbot, scene)
    tool, _sm = _tool(scene)
    line = LineItem(QLineF(0, 0, 200, 40))
    line.setPos(100, 100)
    line.flip_vertical = True
    _add(scene, line)
    tool.enter_point_edit(line)
    start, end = _handle_positions(tool)
    assert start[1] > end[1]  # mirrored top to bottom, as the paint mirrors it


def test_constrain_angle_keeps_the_distance() -> None:
    point = constrain_angle(QPointF(0, 0), QPointF(100, 8))
    assert point.y() == pytest.approx(0.0, abs=1e-9)
    assert point.x() == pytest.approx(math.hypot(100, 8))
    assert constrain_angle(QPointF(5, 5), QPointF(5, 5)) == QPointF(5, 5)


@pytest.mark.parametrize("tool_class", [LineTool, ArrowTool])
def test_shift_constrains_the_line_and_arrow_tools_while_drawing(
    qtbot: QtBot, scene: SnapScene, tool_class: type[LineTool] | type[ArrowTool]
) -> None:
    view = _view_for(qtbot, scene)
    sm = SelectionManager(scene)
    tool = tool_class()
    tool.activate(scene, sm)
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(100, 100)))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(300, 112), SHIFT))
    preview = tool._item  # noqa: SLF001
    assert preview is not None
    assert preview.line.p2().y() == pytest.approx(0.0, abs=1e-6)
    assert preview.line.p2().x() == pytest.approx(math.hypot(200, 12), abs=0.01)
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(300, 112)))
    assert preview.line.p2().y() == pytest.approx(12.0, abs=0.6)
