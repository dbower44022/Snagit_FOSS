"""The Highlighter's drawing, straightening, and point editing (Blur PRD 3.1 to 3.6, 3.9).

Freeform blur decision 2, option A: a moving average over the last five points while the
stroke is drawn, Ramer-Douglas-Peucker at 2 px on release, and the stroke stored as a point
list under ``path_points``.
"""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.geometry_commands import ModifyGeometryCommand
from snapmock.config.constants import (
    DEFAULT_STRAIGHTEN_THRESHOLD,
    HIGHLIGHT_SMOOTHING_WINDOW,
    STRAIGHTEN_THRESHOLD_MAX,
    STRAIGHTEN_THRESHOLD_MIN,
)
from snapmock.core.path_utils import moving_average, snap_to_axis, straightness
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.highlight_item import HighlightItem
from snapmock.tools.highlight_tool import HighlightTool
from snapmock.tools.point_edit import HighlightPointSession, session_for
from snapmock.tools.select_tool import SelectTool
from snapmock.ui.cursors import marker_tip_cursor, reset_cursor_cache


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


def _view(qtbot: QtBot, scene: SnapScene) -> SnapView:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(200, 150)
    return view


def _mouse(
    view: SnapView,
    kind: QEvent.Type,
    pos: QPointF,
    mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> QMouseEvent:
    vp = QPointF(view.mapFromScene(pos))
    button = Qt.MouseButton.LeftButton
    return QMouseEvent(kind, vp, vp, button, button, mods)


def _highlights(scene: SnapScene) -> set[int]:
    return {id(i) for i in scene.annotation_items() if isinstance(i, HighlightItem)}


def _draw(
    tool: HighlightTool,
    view: SnapView,
    points: list[QPointF],
    mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> HighlightItem | None:
    """Draw one stroke and give back the item it placed, or None when it was discarded."""
    scene = view.scene()
    assert isinstance(scene, SnapScene)
    before = _highlights(scene)
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, points[0], mods))
    for point in points[1:]:
        tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, point, mods))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, points[-1], mods))
    placed = [
        i for i in scene.annotation_items() if isinstance(i, HighlightItem) and id(i) not in before
    ]
    return placed[0] if placed else None


def angle_step(p0: QPointF, p1: QPointF) -> float:
    """How far the line p0 to p1 lies from the nearest 15-degree step, in degrees."""
    angle = math.degrees(math.atan2(p1.y() - p0.y(), p1.x() - p0.x())) % 15.0
    return min(angle, 15.0 - angle)


def _tool(scene: SnapScene) -> HighlightTool:
    tool = HighlightTool()
    tool.activate(scene, SelectionManager(scene))
    return tool


def _wobble(x0: float, x1: float, y: float, amplitude: float, count: int = 40) -> list[QPointF]:
    step = (x1 - x0) / (count - 1)
    return [
        QPointF(x0 + i * step, y + amplitude * math.sin(i * math.pi / 4.0)) for i in range(count)
    ]


def test_a_near_straight_stroke_is_straightened_and_a_curve_is_kept(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view(qtbot, scene)
    tool = _tool(scene)
    item = _draw(tool, view, _wobble(40, 240, 100, 1.0))
    assert item is not None and item.is_straight
    points = item.path_points
    assert len(points) == 2
    assert abs(points[1].y() - points[0].y()) < 1.0  # snapped to horizontal as well

    curved = [QPointF(40 + i * 5, 200 + 40 * math.sin(i * math.pi / 20.0)) for i in range(41)]
    item = _draw(tool, view, curved)
    assert item is not None and not item.is_straight
    assert len(item.path_points) > 2


def test_the_threshold_decides_where_the_line_is_drawn(qtbot: QtBot, scene: SnapScene) -> None:
    view = _view(qtbot, scene)
    tool = _tool(scene)
    wobble = _wobble(40, 240, 100, 6.0)
    # The tool straightens the smoothed stroke, not the raw one (3.2)
    ratio = straightness(moving_average([QPointF(p) for p in wobble], HIGHLIGHT_SMOOTHING_WINDOW))
    assert 1.0 < ratio < STRAIGHTEN_THRESHOLD_MAX
    tool.creation_defaults["straighten_threshold"] = max(STRAIGHTEN_THRESHOLD_MIN, ratio - 0.02)
    item = _draw(tool, view, wobble)
    assert item is not None and not item.is_straight  # too bent for this threshold
    tool.creation_defaults["straighten_threshold"] = min(STRAIGHTEN_THRESHOLD_MAX, ratio + 0.05)
    item = _draw(tool, view, wobble)
    assert item is not None and item.is_straight
    tool.creation_defaults["auto_straighten"] = False
    item = _draw(tool, view, _wobble(40, 240, 250, 6.0))
    assert item is not None and not item.is_straight  # the bend is kept, not straightened


def test_shift_forces_a_straight_line_and_shift_alt_constrains_the_angle(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view(qtbot, scene)
    tool = _tool(scene)
    tool.creation_defaults["auto_straighten"] = False
    tool.creation_defaults["snap_to_axis"] = False
    shift = Qt.KeyboardModifier.ShiftModifier
    item = _draw(tool, view, [QPointF(40, 100), QPointF(120, 60), QPointF(200, 137)], shift)
    assert item is not None and item.is_straight
    points = item.path_points
    assert points[1].x() == pytest.approx(160.0, abs=1.0)  # straight to the last position
    assert points[1].y() == pytest.approx(37.0, abs=1.0)  # the path between is dropped

    both = shift | Qt.KeyboardModifier.AltModifier
    item = _draw(tool, view, [QPointF(40, 200), QPointF(140, 226)], both)
    assert item is not None and item.is_straight
    p0, p1 = item.path_points
    step = angle_step(p0, p1)
    assert step < 0.01  # a 15-degree step


def test_the_snap_to_axis_pulls_a_near_horizontal_stroke_flat(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view(qtbot, scene)
    tool = _tool(scene)
    shift = Qt.KeyboardModifier.ShiftModifier
    item = _draw(tool, view, [QPointF(40, 100), QPointF(240, 108)], shift)  # about 2 degrees
    assert item is not None
    p0, p1 = item.path_points
    assert p0.y() == pytest.approx(p1.y(), abs=0.01)

    tool.creation_defaults["snap_to_axis"] = False
    item = _draw(tool, view, [QPointF(40, 200), QPointF(240, 208)], shift)
    assert item is not None
    p0, p1 = item.path_points
    assert abs(p1.y() - p0.y()) > 5.0

    # The helper itself: far from an axis, nothing moves
    away = snap_to_axis(QPointF(0, 0), QPointF(100, 100), 5.0)
    assert away == QPointF(100, 100)


def test_a_stroke_under_four_pixels_is_discarded(qtbot: QtBot, scene: SnapScene) -> None:
    view = _view(qtbot, scene)
    tool = _tool(scene)
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(100, 100)))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(102, 101)))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(102, 101)))
    assert not [i for i in scene.annotation_items() if isinstance(i, HighlightItem)]


def test_the_moving_average_smooths_while_the_stroke_is_drawn(
    qtbot: QtBot, scene: SnapScene
) -> None:
    raw = [QPointF(0, 0), QPointF(10, 20), QPointF(20, 0), QPointF(30, 20), QPointF(40, 0)]
    smoothed = moving_average(raw, 5)
    assert smoothed[0] == QPointF(0, 0)  # the stroke starts where the press did
    spread_raw = max(p.y() for p in raw) - min(p.y() for p in raw)
    spread_smooth = max(p.y() for p in smoothed) - min(p.y() for p in smoothed)
    assert spread_smooth < spread_raw
    assert moving_average([QPointF(1, 2)], 5) == [QPointF(1, 2)]

    view = _view(qtbot, scene)
    tool = _tool(scene)
    tool.creation_defaults["auto_straighten"] = False
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(100, 100)))
    for point in (QPointF(110, 120), QPointF(120, 100), QPointF(130, 120)):
        tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, point))
    preview = tool.preview
    assert preview is not None
    drawn = preview.path_points
    assert drawn[0] == QPointF(0, 0)
    assert abs(drawn[-1].y() - 20.0) > 1.0  # the peak is pulled in by the average
    tool.cancel()


def test_the_keys_round_trip_and_an_older_file_reads_its_points(qapp: QApplication) -> None:
    item = HighlightItem()
    item.set_points([(0.0, 0.0), (40.0, 10.0)])
    item.auto_straighten = False
    item.straighten_threshold = 1.4
    item.snap_to_axis = False
    data = item.serialize()
    assert data["path_points"] == [{"x": 0.0, "y": 0.0}, {"x": 40.0, "y": 10.0}]
    assert (data["auto_straighten"], data["straighten_threshold"], data["snap_to_axis"]) == (
        False,
        1.4,
        False,
    )
    restored = HighlightItem.deserialize(data)
    assert restored.path_points == [QPointF(0, 0), QPointF(40, 10)]
    assert not restored.auto_straighten and restored.straighten_threshold == 1.4
    assert not restored.snap_to_axis

    old = HighlightItem.deserialize({"type": "HighlightItem", "points": [[0, 0], [5, 5], [9, 1]]})
    assert old.path_points == [QPointF(0, 0), QPointF(5, 5), QPointF(9, 1)]
    assert old.auto_straighten and old.snap_to_axis
    assert old.straighten_threshold == DEFAULT_STRAIGHTEN_THRESHOLD
    # The threshold is clamped to the range of 3.4
    item.straighten_threshold = 9.0
    assert item.straighten_threshold == STRAIGHTEN_THRESHOLD_MAX


def test_the_bar_toggles_and_the_hints_follow_the_state(main_window: object) -> None:
    tm = main_window.tool_manager  # type: ignore[attr-defined]
    tm.activate("highlight")
    tool = tm.active_tool
    assert isinstance(tool, HighlightTool)
    straighten = tool.straighten_button
    snap = tool.snap_button
    assert straighten is not None and snap is not None
    assert straighten.accessibleName() == "Auto-Straighten"
    assert snap.accessibleName() == "Snap to Axis"
    assert straighten.isChecked() and snap.isChecked()
    assert tool.status_hint == (
        "Click and drag to highlight. Shift: straight line. Auto-straighten: ON."
    )
    straighten.click()
    assert tool.creation_defaults["auto_straighten"] is False
    assert tool.status_hint.endswith("Auto-straighten: OFF.")
    snap.click()
    assert tool.creation_defaults["snap_to_axis"] is False


def test_the_drawing_hints_and_the_marker_tip_cursor(qtbot: QtBot, scene: SnapScene) -> None:
    reset_cursor_cache()
    view = _view(qtbot, scene)
    tool = _tool(scene)
    cursor = tool.cursor
    assert not isinstance(cursor, Qt.CursorShape)
    assert cursor.hotSpot() == marker_tip_cursor().hotSpot()
    assert cursor.pixmap().width() == 24
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(100, 100)))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(150, 100)))
    assert tool.status_hint == "Highlighting... Release to finish. Shift: force straight."
    tool.mouse_move(
        _mouse(view, QEvent.Type.MouseMove, QPointF(160, 100), Qt.KeyboardModifier.ShiftModifier)
    )
    assert tool.status_hint == "Straight highlight. Release to finish."
    tool.cancel()
    assert tool.status_hint.startswith("Click and drag to highlight.")


def test_the_panel_shows_the_straightening_for_the_tool_defaults(main_window: object) -> None:
    window = main_window
    panel = window._property_panel  # type: ignore[attr-defined]  # noqa: SLF001
    tm = window.tool_manager  # type: ignore[attr-defined]
    tm.activate("highlight")
    window.selection_manager.deselect_all()  # type: ignore[attr-defined]
    panel._refresh_from_selection()  # noqa: SLF001
    assert panel._highlight_section.isVisibleTo(panel)  # noqa: SLF001
    assert panel._highlight_straighten_check.isChecked()  # noqa: SLF001
    panel._highlight_straighten_check.setChecked(False)  # noqa: SLF001
    assert tm.tool("highlight").creation_defaults["auto_straighten"] is False
    panel._highlight_threshold_spin.setValue(1.30)  # noqa: SLF001
    assert tm.tool("highlight").creation_defaults["straighten_threshold"] == pytest.approx(1.30)
    panel._highlight_snap_check.setChecked(False)  # noqa: SLF001
    assert tm.tool("highlight").creation_defaults["snap_to_axis"] is False


# --- point editing (3.6) ---


def _placed(scene: SnapScene, points: list[tuple[float, float]]) -> HighlightItem:
    item = HighlightItem()
    item.set_points(points)
    item.setPos(50, 50)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def test_a_straightened_stroke_shows_two_handles_and_a_freeform_one_its_points(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view(qtbot, scene)
    straight = _placed(scene, [(0.0, 0.0), (100.0, 0.0)])
    session = session_for(straight)
    assert isinstance(session, HighlightPointSession)
    assert [h.key for h in session.handles()] == ["p0", "p1"]
    assert session.handles()[1].pos == QPointF(150, 50)

    freeform = _placed(scene, [(0.0, 0.0), (30.0, 20.0), (60.0, 0.0), (90.0, 25.0)])
    freeform.setPos(50, 150)
    session = session_for(freeform)
    assert isinstance(session, HighlightPointSession)
    assert len(session.handles()) == 4

    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(100, 50)))
    assert isinstance(tool.point_session, HighlightPointSession)
    assert tool.status_hint == "Drag points to reshape. Escape: exit."
    assert tool.handle_escape()


def test_dragging_an_endpoint_is_one_undoable_geometry_edit(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view(qtbot, scene)
    item = _placed(scene, [(0.0, 0.0), (100.0, 0.0)])
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    assert tool.enter_point_edit(item)
    depth = len(scene.command_stack._commands)  # noqa: SLF001
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(150, 50)))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(190, 90)))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(190, 90)))
    assert len(scene.command_stack._commands) == depth + 1  # noqa: SLF001
    assert isinstance(scene.command_stack._commands[-1], ModifyGeometryCommand)  # noqa: SLF001
    assert item.path_points[1] == QPointF(140, 40)
    scene.command_stack.undo()
    assert item.path_points[1] == QPointF(100, 0)


def test_shift_constrains_an_endpoint_drag_of_a_straightened_stroke(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view(qtbot, scene)
    item = _placed(scene, [(0.0, 0.0), (100.0, 0.0)])
    tool = SelectTool()
    tool.activate(scene, SelectionManager(scene))
    assert tool.enter_point_edit(item)
    shift = Qt.KeyboardModifier.ShiftModifier
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(150, 50), shift))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(190, 96), shift))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(190, 96), shift))
    assert angle_step(*item.path_points) < 0.01
