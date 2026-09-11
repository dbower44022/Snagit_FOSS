"""The Rectangle's individual corner radii (Basic Shape PRD 5.3, 5.4, 5.5, 10.3; Basic Shape
remainder Phase 2 step 1)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import CORNER_KEYS, CornerRadiusMode
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.tool_themes import decode_value, encode_value
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.tools.rectangle_tool import RectangleTool
from snapmock.ui.property_panel import PropertyPanel

OFFSET = QPointF(40, 40)
# A pixel just inside each corner of a 100 by 60 rectangle drawn at OFFSET
CORNER_PIXELS = {
    "corner_radius_tl": (41, 41),
    "corner_radius_tr": (138, 41),
    "corner_radius_bl": (41, 98),
    "corner_radius_br": (138, 98),
}


def _filled() -> RectangleItem:
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.fill_color = QColor("#000000")
    item.stroke_width = 0.0
    return item


def _white_corners(item: RectangleItem) -> set[str]:
    image = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(OFFSET)
    item.paint(painter, None)
    painter.end()
    return {k for k, (x, y) in CORNER_PIXELS.items() if image.pixelColor(x, y).name() == "#ffffff"}


@pytest.mark.parametrize("key", CORNER_KEYS)
def test_each_corner_rounds_alone(qapp: QApplication, key: str) -> None:
    item = _filled()
    item.corner_radius_mode = CornerRadiusMode.INDIVIDUAL
    assert _white_corners(item) == set()
    setattr(item, key, 20.0)
    assert _white_corners(item) == {key}
    assert not item.shape().contains(
        QPointF(*(c - o for c, o in zip(CORNER_PIXELS[key], (40, 40))))
    )


def test_the_radii_are_stored_as_set_and_drawn_clamped(qapp: QApplication) -> None:
    item = _filled()
    item.corner_radius_mode = CornerRadiusMode.INDIVIDUAL
    item.corner_radius_tl = 500.0
    assert item.corner_radius_tl == 200.0  # the control's range
    assert item.effective_corner_radii()[0] == 30.0  # half the smaller side
    item.rect = QRectF(0, 0, 300, 300)
    assert item.effective_corner_radii()[0] == 150.0
    item.corner_radius_mode = CornerRadiusMode.UNIFORM
    item.corner_radius = 10.0
    assert item.effective_corner_radii() == (10.0, 10.0, 10.0, 10.0)
    item.scale_geometry(2.0, 2.0)
    assert item.corner_radius == 20.0 and item.corner_radius_tl == 400.0


def test_switching_to_individual_keeps_the_look(qapp: QApplication) -> None:
    item = _filled()
    item.corner_radius = 12.0
    item.corner_radius_mode = CornerRadiusMode.INDIVIDUAL
    assert [getattr(item, k) for k in CORNER_KEYS] == [12.0] * 4
    item.corner_radius_br = 0.0
    item.corner_radius_mode = CornerRadiusMode.UNIFORM
    item.corner_radius_mode = CornerRadiusMode.INDIVIDUAL
    assert item.corner_radius_br == 0.0  # set radii are never overwritten


def test_the_mode_and_radii_round_trip(qapp: QApplication) -> None:
    item = _filled()
    item.corner_radius_mode = CornerRadiusMode.INDIVIDUAL
    item.corner_radius_tr = 7.0
    data = item.serialize()
    assert data["corner_radius_mode"] == "individual"
    assert [data[k] for k in CORNER_KEYS] == [0.0, 7.0, 0.0, 0.0]
    restored = RectangleItem.deserialize(data)
    assert restored.corner_radius_mode is CornerRadiusMode.INDIVIDUAL
    assert restored.corner_radius_tr == 7.0
    for key in ("corner_radius_mode", *CORNER_KEYS):
        del data[key]
    old = RectangleItem.deserialize(data)
    assert old.corner_radius_mode is CornerRadiusMode.UNIFORM
    assert decode_value(encode_value(CornerRadiusMode.INDIVIDUAL)) is CornerRadiusMode.INDIVIDUAL


def _event(kind: QEvent.Type, window: MainWindow, scene_pos: QPointF) -> QMouseEvent:
    vp = QPointF(window.view.mapFromScene(scene_pos))
    button = Qt.MouseButton.LeftButton
    return QMouseEvent(kind, vp, button, button, Qt.KeyboardModifier.NoModifier)


def test_the_bar_toggle_swaps_the_slider_for_four_spin_boxes(main_window: MainWindow) -> None:
    bar = main_window._tool_options  # noqa: SLF001
    tm = main_window.tool_manager
    tm.activate("rectangle")
    tool = tm.active_tool
    assert isinstance(tool, RectangleTool)
    uniform_actions = bar._control_actions["corner_radius"]  # noqa: SLF001
    spins = tool.corner_spins
    button = tool.mode_button
    assert button is not None and button.accessibleName() == "Individual corner radii"
    assert list(spins) == list(CORNER_KEYS)
    assert all(a.isVisible() for a in uniform_actions)
    assert not any(a.isVisible() for a in tool._corner_actions)  # noqa: SLF001
    bar.shared_widgets["corner_radius"].setValue(6)  # type: ignore[attr-defined]
    button.click()
    assert tool.creation_defaults["corner_radius_mode"] is CornerRadiusMode.INDIVIDUAL
    assert not any(a.isVisible() for a in uniform_actions)
    assert all(a.isVisible() for a in tool._corner_actions)  # noqa: SLF001
    assert [s.value() for s in spins.values()] == [6, 6, 6, 6]  # seeded from the uniform
    spins["corner_radius_tl"].setValue(25)
    assert tool.creation_defaults["corner_radius_tl"] == 25.0
    tm.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, main_window, QPointF(10, 10)))
    tm.handle_mouse_move(_event(QEvent.Type.MouseMove, main_window, QPointF(210, 130)))
    tm.handle_mouse_release(_event(QEvent.Type.MouseButtonRelease, main_window, QPointF(210, 130)))
    rects = [i for i in main_window.scene.annotation_items() if isinstance(i, RectangleItem)]
    assert len(rects) == 1
    placed = rects[0]
    assert placed.corner_radius_mode is CornerRadiusMode.INDIVIDUAL
    assert [getattr(placed, k) for k in CORNER_KEYS] == [25.0, 6.0, 6.0, 6.0]


def test_the_panel_edits_the_mode_and_each_corner(qtbot: QtBot) -> None:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = _filled()
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    sm.select(item)
    check = panel._corner_mode_check  # noqa: SLF001
    spins = panel._corner_spins  # noqa: SLF001
    assert not check.isChecked()
    assert all(s.isHidden() for s in spins.values())
    assert not panel._corner_radius_row.isHidden()  # noqa: SLF001
    check.setChecked(True)
    assert item.corner_radius_mode is CornerRadiusMode.INDIVIDUAL
    assert not any(s.isHidden() for s in spins.values())
    assert panel._corner_radius_row.isHidden()  # noqa: SLF001
    spins["corner_radius_bl"].setValue(15.0)
    assert item.corner_radius_bl == 15.0
    assert scene.command_stack.undo_text == "Change corner_radius_bl"
    scene.command_stack.undo()
    assert item.corner_radius_bl == 0.0
    scene.command_stack.undo()
    assert item.corner_radius_mode is CornerRadiusMode.UNIFORM
