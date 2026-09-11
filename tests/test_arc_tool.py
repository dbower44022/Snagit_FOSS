"""The Arc tool (Basic Shape PRD Section 7; Basic Shape remainder Phase 3)."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.config.constants import ArcType, HeadStyle
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.arc_item import ArcItem, circumcentre
from snapmock.tools.arc_tool import ArcTool

NONE = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
LEFT = Qt.MouseButton.LeftButton


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def _setup(qtbot: QtBot, scene: SnapScene) -> tuple[SnapView, ArcTool]:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(300, 200)
    tool = ArcTool()
    tool.activate(scene, SelectionManager(scene))
    return view, tool


def _mouse(
    view: SnapView,
    kind: QEvent.Type,
    pos: QPointF,
    buttons: Qt.MouseButton = LEFT,
    modifiers: Qt.KeyboardModifier = NONE,
) -> QMouseEvent:
    vp = QPointF(view.mapFromScene(pos))
    return QMouseEvent(kind, vp, vp, LEFT, buttons, modifiers)


def _chord(
    tool: ArcTool, view: SnapView, start: QPointF, end: QPointF, mods: Qt.KeyboardModifier = NONE
) -> None:
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, start))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, end, modifiers=mods))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, end, modifiers=mods))


def _arcs(scene: SnapScene) -> list[ArcItem]:
    return [i for i in scene.annotation_items() if isinstance(i, ArcItem)]


def test_the_three_steps_make_an_arc(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool = _setup(qtbot, scene)
    assert "Click and drag to define the arc chord" in tool.status_hint
    _chord(tool, view, QPointF(100, 200), QPointF(300, 200))
    preview = tool.preview
    assert preview is not None and preview.end_point == QPointF(200, 0)
    assert tool.status_hint.startswith("Arc: 200px Bulge: 0px")
    # Step 2: no button held; the peak follows the cursor's distance from the chord
    tool.mouse_move(
        _mouse(view, QEvent.Type.MouseMove, QPointF(230, 120), Qt.MouseButton.NoButton)
    )
    assert preview.control_point == QPointF(100, -160)
    assert preview.peak() == QPointF(100, -80)
    assert "Bulge: 80px" in tool.status_hint
    tool.mouse_move(
        _mouse(view, QEvent.Type.MouseMove, QPointF(200, 250), Qt.MouseButton.NoButton)
    )
    assert preview.control_point == QPointF(100, 100)  # the other side of the chord
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(200, 250)))
    arcs = _arcs(scene)
    assert len(arcs) == 1 and arcs[0].control_point == QPointF(100, 100)
    assert tool.preview is None
    scene.command_stack.undo()
    assert not _arcs(scene)


def test_escape_cancels_at_any_step_and_enter_or_a_double_click_confirms(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view, tool = _setup(qtbot, scene)
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(100, 200)))
    assert tool.handle_escape()
    assert tool.preview is None and not scene.items()
    _chord(tool, view, QPointF(100, 200), QPointF(300, 200))
    assert tool.key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, NONE))
    assert tool.preview is None and not _arcs(scene)
    _chord(tool, view, QPointF(100, 200), QPointF(300, 200))
    assert tool.key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, NONE))
    assert len(_arcs(scene)) == 1
    _chord(tool, view, QPointF(100, 300), QPointF(300, 300))
    assert tool.mouse_double_click(
        _mouse(view, QEvent.Type.MouseButtonDblClick, QPointF(200, 260))
    )
    assert len(_arcs(scene)) == 2
    assert not tool.handle_escape()  # nothing in progress


def test_a_click_is_not_a_chord_and_shift_constrains_it(qtbot: QtBot, scene: SnapScene) -> None:
    view, tool = _setup(qtbot, scene)
    _chord(tool, view, QPointF(100, 200), QPointF(101, 200))
    assert tool.preview is None and not scene.items()
    _chord(tool, view, QPointF(100, 200), QPointF(300, 213), SHIFT)
    preview = tool.preview
    assert preview is not None
    assert preview.end_point.y() == pytest.approx(0.0, abs=1e-6)
    assert preview.end_point.x() == pytest.approx(math.hypot(200, 13), abs=0.01)


def _render(item: ArcItem) -> QImage:
    image = QImage(300, 300, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(50, 200)
    item.paint(painter, None)
    painter.end()
    return image


def test_the_three_arc_types_and_their_fill(qapp: QApplication) -> None:
    item = ArcItem(start=QPointF(0, 0), end=QPointF(200, 0), control=QPointF(100, -160))
    item.fill_color = QColor("#000000")
    inside = (150, 160)  # below the peak, above the chord, in image pixels
    assert _render(item).pixelColor(*inside).name() == "#ffffff"  # Open: no fill
    assert not item.shape().contains(QPointF(100, -40))
    item.arc_type = ArcType.CHORD
    assert _render(item).pixelColor(*inside).name() == "#000000"
    assert item.shape().contains(QPointF(100, -40))
    item.arc_type = ArcType.PIE
    centre = item.virtual_centre()
    assert centre is not None
    # The circle through both ends and the peak (100, -80): centre on the chord's bisector
    assert centre.x() == pytest.approx(100.0)
    assert math.hypot(centre.x(), centre.y()) == pytest.approx(
        math.hypot(centre.x() - 100, centre.y() + 80)
    )
    assert item.outline().elementCount() > item.curve_path().elementCount()
    straight = ArcItem(start=QPointF(0, 0), end=QPointF(200, 0))
    straight.arc_type = ArcType.PIE
    assert straight.virtual_centre() is None  # a straight pie closes as a chord
    assert circumcentre(QPointF(0, 0), QPointF(1, 1), QPointF(2, 2)) is None


def test_the_heads_follow_the_tangent(qapp: QApplication) -> None:
    item = ArcItem(start=QPointF(0, 0), end=QPointF(200, 0), control=QPointF(100, -160))
    head, tail = item.end_directions()
    length = math.hypot(100, 160)
    assert (head.x(), head.y()) == pytest.approx((100 / length, 160 / length))
    assert (tail.x(), tail.y()) == pytest.approx((-100 / length, 160 / length))
    item.head_style = HeadStyle.FILLED
    filled, _lines, shaft = item.head_paths()
    size = item.effective_head_size()
    tip_inside = QPointF(200 - head.x() * size / 2, -head.y() * size / 2)
    assert filled.contains(tip_inside)
    end = shaft.currentPosition()
    assert math.hypot(200 - end.x(), end.y()) == pytest.approx(size, abs=0.05)


def test_the_keys_round_trip(qapp: QApplication) -> None:
    item = ArcItem(start=QPointF(1, 2), end=QPointF(30, 4), control=QPointF(15, -20))
    item.arc_type = ArcType.PIE
    item.tail_style = HeadStyle.OPEN
    data = item.serialize()
    assert data["type"] == "ArcItem"
    assert data["start_point"] == {"x": 1.0, "y": 2.0}
    assert data["control_point"] == {"x": 15.0, "y": -20.0}
    assert (data["arc_type"], data["head_style"], data["tail_style"]) == ("pie", "none", "open")
    restored = ArcItem.deserialize(data)
    assert restored.arc_type is ArcType.PIE and restored.tail_style is HeadStyle.OPEN
    assert restored.end_point == QPointF(30, 4) and restored.control_point == QPointF(15, -20)
    item.scale_geometry(2.0, 1.0)
    assert item.control_point == QPointF(30, -20)


# --- registration, the bar, Escape, the panel, the file (7.4; decision 3) ---


def _window_event(window: object, kind: QEvent.Type, pos: QPointF) -> QMouseEvent:
    view = window.view  # type: ignore[attr-defined]
    vp = QPointF(view.mapFromScene(pos))
    return QMouseEvent(kind, vp, LEFT, LEFT, NONE)


def test_arc_is_the_twentieth_tool_on_shift_a(main_window: object) -> None:
    from PyQt6.QtGui import QKeySequence

    from snapmock.config.shortcuts import SHORTCUTS

    window = main_window
    tm = window.tool_manager  # type: ignore[attr-defined]
    ids = tm.tool_ids
    assert ids.index("arc") == ids.index("line") + 1
    assert SHORTCUTS["tool.arc"] == "Shift+A"
    action = window._tool_actions["arc"]  # type: ignore[attr-defined]  # noqa: SLF001
    assert action.shortcut() == QKeySequence("Shift+A") and not action.icon().isNull()
    button = window._toolbar._buttons["arc"]  # type: ignore[attr-defined]  # noqa: SLF001
    assert not button.icon().isNull()
    tm.activate("arc")
    bar = window._tool_options  # type: ignore[attr-defined]  # noqa: SLF001
    assert list(bar.shared_widgets) == [
        "stroke_color",
        "fill_color",
        "stroke_width",
        "stroke_style",
        "fill_opacity",
        "stroke_opacity",
        "shadow_enabled",
        "head_style",
        "tail_style",
        "head_size",
    ]
    tool = tm.active_tool
    assert isinstance(tool, ArcTool)
    buttons = tool.arc_type_buttons
    assert list(buttons) == [ArcType.OPEN, ArcType.CHORD, ArcType.PIE]
    assert all(not b.icon().isNull() and b.accessibleName() for b in buttons.values())
    buttons[ArcType.CHORD].click()
    assert tool.creation_defaults["arc_type"] is ArcType.CHORD


def test_the_window_escape_cancels_an_arc_in_progress(main_window: object) -> None:
    window = main_window
    tm = window.tool_manager  # type: ignore[attr-defined]
    tm.activate("arc")
    tool = tm.active_tool
    assert isinstance(tool, ArcTool)
    tm.handle_mouse_press(_window_event(window, QEvent.Type.MouseButtonPress, QPointF(20, 20)))
    tm.handle_mouse_move(_window_event(window, QEvent.Type.MouseMove, QPointF(200, 20)))
    tm.handle_mouse_release(
        _window_event(window, QEvent.Type.MouseButtonRelease, QPointF(200, 20))
    )
    assert tool.preview is not None
    window._edit_deselect()  # type: ignore[attr-defined]  # noqa: SLF001 — Escape's slot
    assert tool.preview is None
    assert not _arcs(window.scene)  # type: ignore[attr-defined]


def test_the_panel_arc_section_edits_a_placed_arc(qtbot: QtBot) -> None:
    from snapmock.commands.add_item import AddItemCommand
    from snapmock.ui.property_panel import PropertyPanel

    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    item = ArcItem(start=QPointF(0, 0), end=QPointF(100, 0), control=QPointF(50, -60))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    sm.select(item)
    assert panel._arc_section.isVisible()  # noqa: SLF001
    combo = panel._arc_type_combo  # noqa: SLF001
    assert combo.currentData() is ArcType.OPEN
    combo.setCurrentIndex(combo.findData(ArcType.PIE))
    assert item.arc_type is ArcType.PIE
    assert scene.command_stack.undo_text == "Change arc_type"
    head = panel._arc_head_combo  # noqa: SLF001
    head.setCurrentIndex(head.findData(HeadStyle.FILLED))
    assert item.head_style is HeadStyle.FILLED
    scene.command_stack.undo()
    scene.command_stack.undo()
    assert item.arc_type is ArcType.OPEN and item.head_style is HeadStyle.NONE


def test_an_arc_survives_a_project_file(qapp: QApplication, tmp_path: object) -> None:
    from pathlib import Path

    from snapmock.commands.add_item import AddItemCommand
    from snapmock.io.project_serializer import load_project, save_project

    scene = SnapScene()
    item = ArcItem(start=QPointF(0, 0), end=QPointF(100, 0), control=QPointF(50, -60))
    item.arc_type = ArcType.CHORD
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    path = Path(str(tmp_path)) / "arc.smk"
    save_project(scene, path, write_thumbnail=False)
    loaded = [i for i in load_project(path).annotation_items() if isinstance(i, ArcItem)]
    assert len(loaded) == 1
    assert loaded[0].control_point == QPointF(50, -60) and loaded[0].arc_type is ArcType.CHORD
