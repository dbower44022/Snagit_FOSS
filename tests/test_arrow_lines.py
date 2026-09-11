"""Curved and elbow arrows (Basic Shape PRD 4.5, 4.6, 4.7, 10.2; Basic Shape remainder
Phase 1 step 3)."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import HeadStyle, LineStyle
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.tool_themes import decode_value, encode_value
from snapmock.core.view import SnapView
from snapmock.items.arrow_item import ArrowItem
from snapmock.main_window import MainWindow
from snapmock.tools.arrow_tool import ArrowTool
from snapmock.tools.point_edit import HandleKind
from snapmock.tools.select_tool import SelectTool
from snapmock.ui.property_panel import PropertyPanel

ORIGIN = QPointF(60, 140)


def _arrow(style: LineStyle, line: QLineF | None = None) -> ArrowItem:
    item = ArrowItem(line=line if line is not None else QLineF(0, 0, 200, 0))
    item.stroke_color = QColor("#000000")
    item.stroke_width = 4.0
    item.head_style = HeadStyle.NONE
    item.line_style = style
    return item


def _render(item: ArrowItem) -> QImage:
    image = QImage(340, 300, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(ORIGIN)
    item.paint(painter, None)
    painter.end()
    return image


def _dark(image: QImage, local: QPointF) -> bool:
    color = image.pixelColor(round(ORIGIN.x() + local.x()), round(ORIGIN.y() + local.y()))
    return color.lightness() < 100


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def test_a_curve_bends_through_its_control_point(qapp: QApplication) -> None:
    item = _arrow(LineStyle.CURVED)
    assert item.control_point is None  # the midpoint: straight until it is moved
    mid = item.line_path().pointAtPercent(0.5)
    assert (round(mid.x(), 3), round(mid.y(), 3)) == (100.0, 0.0)
    item.control_point = QPointF(100, -80)
    image = _render(item)
    assert _dark(image, QPointF(100, -40))  # the quadratic's apex: a quarter of the way
    assert not _dark(image, QPointF(100, 0))  # the chord is no longer drawn
    assert item.boundingRect().contains(QPointF(100, -40))
    assert item.shape().contains(QPointF(100, -40))
    item.line_style = LineStyle.STRAIGHT
    assert _dark(_render(item), QPointF(100, 0))  # the control point is kept but unused


def test_the_heads_follow_the_tangent_and_the_shaft_stops_at_the_base(
    qapp: QApplication,
) -> None:
    item = _arrow(LineStyle.CURVED)
    item.control_point = QPointF(100, -80)
    head, tail = item.end_directions()
    assert (head.x(), head.y()) == pytest.approx(_unit(100, 80))
    assert (tail.x(), tail.y()) == pytest.approx(_unit(-100, 80))
    item.head_style = HeadStyle.FILLED
    size = item.effective_head_size()
    filled, _lines, shaft = item.head_paths()
    end = shaft.currentPosition()
    assert math.hypot(200 - end.x(), 0 - end.y()) == pytest.approx(size, abs=0.05)
    inside = QPointF(200 - head.x() * size / 2, -head.y() * size / 2)
    assert filled.contains(inside)
    assert _dark(_render(item), inside)
    beside = QPointF(186, 12)  # inside a head along the chord, outside the tangent's
    assert not filled.contains(beside)


def test_an_elbow_keeps_right_angles(qapp: QApplication) -> None:
    item = _arrow(LineStyle.ELBOW, QLineF(0, 0, 200, 100))
    points = [(p.x(), p.y()) for p in item.elbow_points()]
    assert points == [(0, 0), (100, 0), (100, 100), (200, 100)]
    pts = item.elbow_points()
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        dot = (b.x() - a.x()) * (c.x() - b.x()) + (b.y() - a.y()) * (c.y() - b.y())
        assert dot == 0
    head, tail = item.end_directions()
    assert (head.x(), head.y()) == (1.0, 0.0) and (tail.x(), tail.y()) == (-1.0, 0.0)
    image = _render(item)
    assert _dark(image, QPointF(100, 50)) and not _dark(image, QPointF(50, 50))
    item.bend_point = QPointF(40, 999)  # only its x counts
    assert [(p.x(), p.y()) for p in item.elbow_points()][1:3] == [(40, 0), (40, 100)]
    assert item.bend_handle_point() == QPointF(40, 50)
    item.bend_point = QPointF(0, 0)  # the first segment vanishes: an L of two segments
    assert [(p.x(), p.y()) for p in item.elbow_points()] == [(0, 0), (0, 100), (200, 100)]
    head, tail = item.end_directions()
    assert (tail.x(), tail.y()) == (0.0, -1.0)
    item.bend_point = None
    item.head_style = HeadStyle.FILLED
    _filled, _lines, shaft = item.head_paths()
    end = shaft.currentPosition()
    assert (end.x(), end.y()) == pytest.approx((200 - item.effective_head_size(), 100))


def test_the_keys_round_trip_and_scale(qapp: QApplication) -> None:
    item = _arrow(LineStyle.CURVED)
    item.control_point = QPointF(10, 20)
    item.bend_point = QPointF(30, 40)
    data = item.serialize()
    assert data["line_style"] == "curved"
    assert data["control_point"] == {"x": 10.0, "y": 20.0}
    assert data["bend_point"] == {"x": 30.0, "y": 40.0}
    restored = ArrowItem.deserialize(data)
    assert restored.line_style is LineStyle.CURVED
    assert restored.control_point == QPointF(10, 20) and restored.bend_point == QPointF(30, 40)
    data["control_point"] = [5, 6]  # a list reads too
    assert ArrowItem.deserialize(data).control_point == QPointF(5, 6)
    for key in ("control_point", "bend_point", "line_style"):
        del data[key]
    old = ArrowItem.deserialize(data)
    assert old.line_style is LineStyle.STRAIGHT
    assert old.control_point is None and old.bend_point is None
    item.scale_geometry(2.0, 3.0)
    assert item.control_point == QPointF(20, 60) and item.bend_point == QPointF(60, 120)
    assert decode_value(encode_value(LineStyle.ELBOW)) is LineStyle.ELBOW


# --- point editing (4.5, 4.6) ---


def _view(qtbot: QtBot, scene: SnapScene) -> SnapView:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(300, 200)
    return view


def _mouse(view: SnapView, kind: QEvent.Type, scene_pos: QPointF) -> QMouseEvent:
    vp = QPointF(view.mapFromScene(scene_pos))
    button = Qt.MouseButton.LeftButton
    return QMouseEvent(kind, vp, vp, button, button, Qt.KeyboardModifier.NoModifier)


def _place(scene: SnapScene, item: ArrowItem) -> None:
    item.setPos(100, 100)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))


def _drag(tool: SelectTool, view: SnapView, start: QPointF, end: QPointF) -> None:
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, start))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, end))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, end))


def test_point_editing_drags_a_curve_by_its_control_point(
    qtbot: QtBot, qapp: QApplication
) -> None:
    scene = SnapScene(width=800, height=600)
    view = _view(qtbot, scene)
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    item = _arrow(LineStyle.CURVED)
    _place(scene, item)
    assert tool.enter_point_edit(item)
    handles = tool.point_handles
    assert handles is not None
    kinds = [(h.key, h.kind) for h in handles.handles]
    assert kinds[-1] == ("control", HandleKind.CONTROL)
    assert handles.handles[-1].pos == QPointF(200, 100)  # the midpoint
    session = tool.point_session
    assert session is not None and len(session.guide_lines()) == 2
    assert tool.status_hint == "Drag endpoints or control point to reshape. Escape: exit."
    _drag(tool, view, QPointF(200, 100), QPointF(200, 20))
    assert item.control_point == QPointF(100, -80)
    assert scene.command_stack.undo_text == "Edit Arrow geometry"
    scene.command_stack.undo()
    assert item.control_point is None


def test_point_editing_moves_an_elbow_bend_across_only(qtbot: QtBot, qapp: QApplication) -> None:
    scene = SnapScene(width=800, height=600)
    view = _view(qtbot, scene)
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    item = _arrow(LineStyle.ELBOW, QLineF(0, 0, 200, 100))
    _place(scene, item)
    tool.enter_point_edit(item)
    assert tool.status_hint == "Drag endpoints or bend point to reshape. Escape: exit."
    _drag(tool, view, QPointF(200, 150), QPointF(160, 190))
    assert item.bend_point == QPointF(60, 50)
    assert [(p.x(), p.y()) for p in item.elbow_points()][1:3] == [(60, 0), (60, 100)]


# --- the bar (4.7) and the Property Panel ---


def test_the_line_style_toggles_reach_the_next_arrow(main_window: MainWindow) -> None:
    tm = main_window.tool_manager
    tm.activate("arrow")
    tool = tm.active_tool
    assert isinstance(tool, ArrowTool)
    buttons = tool.line_style_buttons
    assert list(buttons) == [LineStyle.STRAIGHT, LineStyle.CURVED, LineStyle.ELBOW]
    assert all(not b.icon().isNull() and b.accessibleName() for b in buttons.values())
    assert buttons[LineStyle.STRAIGHT].isChecked()
    buttons[LineStyle.CURVED].click()
    assert buttons[LineStyle.CURVED].isChecked() and not buttons[LineStyle.STRAIGHT].isChecked()
    assert tool.creation_defaults["line_style"] is LineStyle.CURVED

    def event(kind: QEvent.Type, pos: QPointF) -> QMouseEvent:
        vp = QPointF(main_window.view.mapFromScene(pos))
        button = Qt.MouseButton.LeftButton
        return QMouseEvent(kind, vp, button, button, Qt.KeyboardModifier.NoModifier)

    tm.handle_mouse_press(event(QEvent.Type.MouseButtonPress, QPointF(10, 10)))
    tm.handle_mouse_move(event(QEvent.Type.MouseMove, QPointF(150, 40)))
    tm.handle_mouse_release(event(QEvent.Type.MouseButtonRelease, QPointF(150, 40)))
    arrows = [i for i in main_window.scene.annotation_items() if isinstance(i, ArrowItem)]
    assert len(arrows) == 1 and arrows[0].line_style is LineStyle.CURVED


def test_the_panel_line_style_row_edits_placed_arrows(qtbot: QtBot) -> None:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    item = _arrow(LineStyle.STRAIGHT)
    _place(scene, item)
    sm.select(item)
    combo = panel._arrow_line_style_combo  # noqa: SLF001
    assert combo.currentData() is LineStyle.STRAIGHT
    combo.setCurrentIndex(combo.findData(LineStyle.ELBOW))
    assert item.line_style is LineStyle.ELBOW
    assert scene.command_stack.undo_text == "Change line_style"
    scene.command_stack.undo()
    assert item.line_style is LineStyle.STRAIGHT
