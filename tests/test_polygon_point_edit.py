"""Polygon point editing (Basic Shape PRD 8.5, 11.4, 11.5; Basic Shape remainder Phase 4
step 2)."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import PolygonMode
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.polygon_item import PolygonItem
from snapmock.tools.point_edit import HandleKind, PolygonPointSession
from snapmock.tools.select_tool import SelectTool

NONE = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
SQUARE = [QPointF(0, 0), QPointF(200, 0), QPointF(200, 150), QPointF(0, 150)]


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def _setup(
    qtbot: QtBot, scene: SnapScene, item: PolygonItem
) -> tuple[SnapView, SelectTool, PolygonItem]:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(300, 250)
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    item.setPos(100, 100)
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


def _right_click(tool: SelectTool, view: SnapView, pos: QPointF) -> bool:
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, view.mapFromScene(pos), QPoint())
    return tool.context_menu(event)


def test_a_freeform_polygon_drags_its_vertices(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _setup(qtbot, scene, PolygonItem(vertices=list(SQUARE)))
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(200, 100)))
    session = tool.point_session
    assert isinstance(session, PolygonPointSession)
    assert len(session.handles()) == 4
    assert tool.status_hint.startswith("Drag vertices to reshape.")
    _drag(tool, view, QPointF(300, 250), QPointF(330, 280))
    assert item.vertices[2] == QPointF(230, 180)
    assert scene.command_stack.undo_text == "Edit Polygon geometry"
    scene.command_stack.undo()
    assert item.vertices[2] == QPointF(200, 150)
    _drag(tool, view, QPointF(300, 250), QPointF(330, 200), SHIFT)  # from vertex 1 at (300, 100)
    third = item.mapToScene(item.vertices[2])
    angle = math.degrees(math.atan2(third.y() - 100, third.x() - 300))
    assert angle == pytest.approx(round(angle / 15) * 15, abs=1e-6)


def test_a_double_click_on_an_edge_inserts_a_vertex(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _setup(qtbot, scene, PolygonItem(vertices=list(SQUARE)))
    tool.enter_point_edit(item)
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(200, 101)))
    assert len(item.vertices) == 5
    assert item.vertices[1] == QPointF(100, 0)
    assert scene.command_stack.undo_text == "Insert polygon vertex"
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(100, 175)))
    assert len(item.vertices) == 6 and item.vertices[5] == QPointF(0, 75)  # the closing edge
    scene.command_stack.undo()
    scene.command_stack.undo()
    assert item.vertices == SQUARE


def test_a_right_click_deletes_a_vertex_while_three_remain(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool, item = _setup(qtbot, scene, PolygonItem(vertices=list(SQUARE)))
    tool.enter_point_edit(item)
    assert _right_click(tool, view, QPointF(300, 250))
    assert item.vertices == [QPointF(0, 0), QPointF(200, 0), QPointF(0, 150)]
    assert scene.command_stack.undo_text == "Remove polygon vertex"
    assert _right_click(tool, view, QPointF(300, 100))  # no menu opens...
    assert len(item.vertices) == 3  # ...and three remain
    scene.command_stack.undo()
    assert item.vertices == SQUARE


def test_a_regular_polygon_has_a_centre_and_a_radius_handle(
    qtbot: QtBot, scene: SnapScene
) -> None:
    polygon = PolygonItem()
    polygon.polygon_mode = PolygonMode.REGULAR
    polygon.regular_geometry = (QPointF(0, 0), 100.0, 0.0)
    view, tool, item = _setup(qtbot, scene, polygon)
    tool.enter_point_edit(item)
    session = tool.point_session
    assert session is not None
    assert [(h.key, h.kind) for h in session.handles()] == [
        ("center", HandleKind.ENDPOINT),
        ("radius", HandleKind.CONTROL),
    ]
    assert "radius point" in tool.status_hint
    _drag(tool, view, QPointF(100, 100), QPointF(150, 120))
    assert item.center == QPointF(50, 20)
    _drag(tool, view, QPointF(250, 120), QPointF(150, 200), SHIFT)
    _center, radius, rotation = item.regular_geometry
    assert radius == pytest.approx(80.0) and rotation == pytest.approx(90.0)
    scene.command_stack.undo()
    assert item.regular_geometry == (QPointF(50, 20), 100.0, 0.0)
    assert _right_click(tool, view, QPointF(150, 120))  # no vertex deletion for a regular one
    assert len(item.vertices) == 5
