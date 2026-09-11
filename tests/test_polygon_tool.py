"""The Polygon tool (Basic Shape PRD Section 8; Basic Shape remainder Phase 4)."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QContextMenuEvent, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.config.constants import PolygonMode
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.polygon_item import PolygonItem, regular_vertices
from snapmock.tools.polygon_tool import PolygonTool

NONE = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
LEFT = Qt.MouseButton.LeftButton
RIGHT = Qt.MouseButton.RightButton


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def _setup(qtbot: QtBot, scene: SnapScene) -> tuple[SnapView, PolygonTool]:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(300, 250)
    tool = PolygonTool()
    tool.activate(scene, SelectionManager(scene))
    return view, tool


def _mouse(
    view: SnapView,
    kind: QEvent.Type,
    pos: QPointF,
    button: Qt.MouseButton = LEFT,
    modifiers: Qt.KeyboardModifier = NONE,
) -> QMouseEvent:
    vp = QPointF(view.mapFromScene(pos))
    return QMouseEvent(kind, vp, vp, button, button, modifiers)


def _click(
    tool: PolygonTool,
    view: SnapView,
    pos: QPointF,
    button: Qt.MouseButton = LEFT,
    modifiers: Qt.KeyboardModifier = NONE,
) -> None:
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, pos, button, modifiers))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, pos, button, modifiers))


def _polygons(scene: SnapScene) -> list[PolygonItem]:
    return [i for i in scene.annotation_items() if isinstance(i, PolygonItem)]


def _scene_vertices(item: PolygonItem) -> list[tuple[float, float]]:
    return [(round(p.x(), 3), round(p.y(), 3)) for p in map(item.mapToScene, item.vertices)]


TRIANGLE = [QPointF(100, 100), QPointF(250, 100), QPointF(170, 220)]


def test_clicks_and_a_double_click_make_a_freeform_polygon(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool = _setup(qtbot, scene)
    assert tool.status_hint.startswith("Click to place vertices")
    for p in TRIANGLE:
        _click(tool, view, p)
    assert tool.status_hint.startswith("Vertices: 3 | Click: add vertex")
    preview = tool.preview
    assert preview is not None and not preview.closed  # the open preview path
    tool.mouse_move(
        _mouse(view, QEvent.Type.MouseMove, QPointF(120, 200), Qt.MouseButton.NoButton)
    )
    assert len(preview.vertices) == 4  # the placed vertices and the cursor
    assert tool.mouse_double_click(_mouse(view, QEvent.Type.MouseButtonDblClick, TRIANGLE[-1]))
    polygons = _polygons(scene)
    assert len(polygons) == 1
    polygon = polygons[0]
    assert polygon.closed and polygon.polygon_mode is PolygonMode.FREEFORM
    assert _scene_vertices(polygon) == [(100, 100), (250, 100), (170, 220)]
    assert tool.preview is None
    assert scene.command_stack.undo_text == "Add PolygonItem"


def test_a_click_on_the_first_vertex_or_enter_closes(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool = _setup(qtbot, scene)
    for p in TRIANGLE:
        _click(tool, view, p)
    _click(tool, view, QPointF(106, 104))  # within 10 px of the first vertex
    assert len(_polygons(scene)) == 1 and len(_polygons(scene)[0].vertices) == 3
    for p in [QPointF(400, 100), QPointF(500, 100), QPointF(500, 200), QPointF(400, 200)]:
        _click(tool, view, p)
    assert tool.key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, NONE))
    assert sorted(len(p.vertices) for p in _polygons(scene)) == [3, 4]


def test_fewer_than_three_right_click_and_escape(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool = _setup(qtbot, scene)
    _click(tool, view, QPointF(100, 100))
    _click(tool, view, QPointF(200, 100))
    tool.key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, NONE))
    assert not _polygons(scene) and tool.preview is None  # two vertices cancel
    for p in TRIANGLE:
        _click(tool, view, p)
    _click(tool, view, QPointF(300, 300), RIGHT)  # removes the last vertex
    assert tool.status_hint.startswith("Vertices: 2")
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, view.mapFromScene(QPointF(300, 300)))
    assert tool.context_menu(event)  # no menu while placing
    assert tool.handle_escape()
    assert tool.preview is None and not scene.items()


def test_shift_constrains_the_new_edge(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool = _setup(qtbot, scene)
    _click(tool, view, QPointF(100, 100))
    _click(tool, view, QPointF(300, 111), modifiers=SHIFT)
    preview = tool.preview
    assert preview is not None
    second = preview.mapToScene(preview.vertices[1])
    assert second.y() == pytest.approx(100.0, abs=1e-6)


def test_a_regular_polygon_and_a_star(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool = _setup(qtbot, scene)
    tool.creation_defaults["polygon_mode"] = PolygonMode.REGULAR
    assert tool.status_hint.startswith("Click and drag to draw a regular polygon")
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(300, 300)))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(400, 310), modifiers=SHIFT))
    assert tool.status_hint.startswith("Sides: 5 | R: 100px")
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(400, 310)))
    polygon = _polygons(scene)[0]
    assert polygon.polygon_mode is PolygonMode.REGULAR and len(polygon.vertices) == 5
    first = polygon.mapToScene(polygon.vertices[0])
    assert (first.x(), first.y()) == pytest.approx(
        (300 + math.hypot(100, 10), 300)
    )  # snapped to 0
    tool.creation_defaults["star_enabled"] = True
    tool.creation_defaults["sides"] = 6
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(500, 300)))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(500, 200)))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(500, 200)))
    star = next(p for p in _polygons(scene) if p.star_enabled)
    vertices = star.vertices
    centre = star.center
    assert centre is not None and len(vertices) == 12
    radii = [math.hypot(v.x() - centre.x(), v.y() - centre.y()) for v in vertices]
    assert radii[0] == pytest.approx(100.0) and radii[1] == pytest.approx(50.0)
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(600, 300)))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(600, 301)))
    assert len(_polygons(scene)) == 2  # a click without a drag makes nothing


def test_an_open_polyline_is_not_filled(qapp: QApplication) -> None:
    item = PolygonItem(vertices=[QPointF(0, 0), QPointF(100, 0), QPointF(100, 100)])
    item.fill_color = QColor("#000000")
    assert item.shape().contains(QPointF(70, 30))  # a filled triangle takes the inside
    item.closed = False
    path = item.outline()
    assert path.elementAt(path.elementCount() - 1).x == 100.0  # no closing line
    assert not item.shape().contains(QPointF(70, 30))
    assert item.shape().contains(QPointF(100, 50))


def test_the_regular_arithmetic_and_the_round_trip(qapp: QApplication) -> None:
    square = regular_vertices(QPointF(0, 0), 10.0, 0.0, 4)
    assert [(round(p.x(), 6), round(p.y(), 6)) for p in square] == [
        (10, 0),
        (0, 10),
        (-10, 0),
        (0, -10),
    ]
    assert len(regular_vertices(QPointF(0, 0), 10.0, 0.0, 200)) == 64
    item = PolygonItem()
    item.polygon_mode = PolygonMode.REGULAR
    item.regular_geometry = (QPointF(5, 5), 40.0, 30.0)
    item.sides = 7
    item.star_enabled = True
    item.star_indent = 2.0
    assert item.star_indent == 0.95
    data = item.serialize()
    assert data["polygon_mode"] == "regular" and data["center"] == {"x": 5.0, "y": 5.0}
    assert (data["radius"], data["polygon_rotation"], data["sides"]) == (40.0, 30.0, 7)
    assert len(data["vertices"]) == 14
    restored = PolygonItem.deserialize(data)
    assert restored.regular_geometry == item.regular_geometry
    assert restored.star_enabled and restored.star_indent == 0.95
    free = PolygonItem.deserialize({"type": "PolygonItem", "vertices": [[0, 0], [9, 0], [9, 9]]})
    assert free.polygon_mode is PolygonMode.FREEFORM and len(free.vertices) == 3
    assert free.closed


# --- registration, the bar, Escape, the panel, the file (8.4; decision 3) ---


def test_polygon_is_the_twenty_first_tool_on_g(main_window: object) -> None:
    from PyQt6.QtGui import QKeySequence

    from snapmock.config.shortcuts import SHORTCUTS

    window = main_window
    tm = window.tool_manager  # type: ignore[attr-defined]
    ids = tm.tool_ids
    assert ids.index("polygon") == ids.index("arc") + 1
    assert SHORTCUTS["tool.polygon"] == "G"
    action = window._tool_actions["polygon"]  # type: ignore[attr-defined]  # noqa: SLF001
    assert action.shortcut() == QKeySequence("G") and not action.icon().isNull()
    assert not window._toolbar._buttons["polygon"].icon().isNull()  # type: ignore[attr-defined]  # noqa: SLF001
    tm.activate("polygon")
    bar = window._tool_options  # type: ignore[attr-defined]  # noqa: SLF001
    assert list(bar.shared_widgets) == [
        "stroke_color",
        "fill_color",
        "stroke_width",
        "stroke_style",
        "fill_opacity",
        "stroke_opacity",
        "shadow_enabled",
    ]
    tool = tm.active_tool
    assert isinstance(tool, PolygonTool)
    groups = tool.control_actions()

    def shown(name: str) -> bool:
        return all(a.isVisible() for a in groups[name])

    assert shown("freeform") and not shown("regular") and not shown("indent")
    tool.mode_buttons[PolygonMode.REGULAR].click()
    assert tool.creation_defaults["polygon_mode"] is PolygonMode.REGULAR
    assert shown("regular") and not shown("freeform") and not shown("indent")
    star = tool.star_check
    assert star is not None
    star.setChecked(True)
    assert shown("indent") and tool.creation_defaults["star_enabled"] is True
    sides = tool.sides_spin
    assert sides is not None and (sides.minimum(), sides.maximum()) == (3, 64)


def test_the_window_escape_cancels_a_polygon_in_progress(main_window: object) -> None:
    window = main_window
    tm = window.tool_manager  # type: ignore[attr-defined]
    tm.activate("polygon")
    tool = tm.active_tool
    assert isinstance(tool, PolygonTool)
    view = window.view  # type: ignore[attr-defined]
    for p in (QPointF(20, 20), QPointF(120, 20)):
        vp = QPointF(view.mapFromScene(p))
        tm.handle_mouse_press(QMouseEvent(QEvent.Type.MouseButtonPress, vp, LEFT, LEFT, NONE))
        tm.handle_mouse_release(QMouseEvent(QEvent.Type.MouseButtonRelease, vp, LEFT, LEFT, NONE))
    assert tool.preview is not None
    window._edit_deselect()  # type: ignore[attr-defined]  # noqa: SLF001 — Escape's slot
    assert tool.preview is None


def test_the_panel_polygon_section_edits_a_placed_polygon(qtbot: QtBot) -> None:
    from snapmock.commands.add_item import AddItemCommand
    from snapmock.ui.property_panel import PropertyPanel

    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    regular = PolygonItem()
    regular.polygon_mode = PolygonMode.REGULAR
    regular.regular_geometry = (QPointF(0, 0), 50.0, -90.0)
    free = PolygonItem(vertices=[QPointF(0, 0), QPointF(50, 0), QPointF(0, 50)])
    free.setPos(200, 0)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    for item in (regular, free):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    sm.select(regular)
    assert panel._polygon_section.isVisible()  # noqa: SLF001
    sides = panel._polygon_sides_spin  # noqa: SLF001
    assert not sides.isHidden() and panel._polygon_closed_check.isHidden()  # noqa: SLF001
    sides.setValue(8)
    assert regular.sides == 8 and len(regular.vertices) == 8
    assert scene.command_stack.undo_text == "Change sides"
    scene.command_stack.undo()
    assert regular.sides == 5
    sm.select(free)
    closed = panel._polygon_closed_check  # noqa: SLF001
    assert sides.isHidden() and not closed.isHidden() and closed.isChecked()
    closed.setChecked(False)
    assert not free.closed


def test_a_polygon_survives_a_project_file(qapp: QApplication, tmp_path: object) -> None:
    from pathlib import Path

    from snapmock.commands.add_item import AddItemCommand
    from snapmock.io.project_serializer import load_project, save_project

    scene = SnapScene()
    item = PolygonItem(vertices=[QPointF(0, 0), QPointF(50, 0), QPointF(25, 40)])
    item.closed = False
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    path = Path(str(tmp_path)) / "polygon.smk"
    save_project(scene, path, write_thumbnail=False)
    loaded = [i for i in load_project(path).annotation_items() if isinstance(i, PolygonItem)]
    assert len(loaded) == 1 and not loaded[0].closed
    assert loaded[0].vertices == item.vertices
