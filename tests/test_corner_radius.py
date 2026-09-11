"""The Rectangle's Corner Radius control (Basic Shape PRD 5.3, 5.4; Vector Item Properties
Phase 3 step 2)."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication, QSpinBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.ui.property_panel import MIXED_TEXT, PropertyPanel

Button = Qt.MouseButton
Modifier = Qt.KeyboardModifier


def _corner_is_white(item: RectangleItem) -> bool:
    image = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(QPointF(40, 40))
    item.paint(painter, None)
    painter.end()
    return image.pixelColor(41, 41).name() == "#ffffff"


def test_the_radius_is_stored_as_set_and_drawn_clamped_to_half_the_smaller_side(
    qapp: QApplication,
) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 100, 40))
    item.fill_color = QColor("#000000")
    assert not _corner_is_white(item)
    item.corner_radius = 150.0
    assert item.corner_radius == 150.0
    assert item.effective_corner_radius() == 20.0
    assert _corner_is_white(item)
    item.corner_radius = 500.0
    assert item.corner_radius == 200.0  # the control's range
    item.rect = QRectF(0, 0, 500, 500)
    assert item.effective_corner_radius() == 200.0  # a resize restores the rounding
    assert RectangleItem.deserialize(item.serialize()).corner_radius == 200.0


def _event(kind: QEvent.Type, window: MainWindow, scene_pos: QPointF) -> QMouseEvent:
    view_pos = QPointF(window.view.mapFromScene(scene_pos))
    return QMouseEvent(kind, view_pos, Button.LeftButton, Button.LeftButton, Modifier.NoModifier)


def test_the_bar_control_reaches_a_new_rectangle(main_window: MainWindow) -> None:
    bar = main_window._tool_options  # noqa: SLF001
    tm = main_window.tool_manager
    tm.activate("rectangle")
    assert list(bar.shared_widgets)[-1] == "corner_radius"
    spin = bar.shared_widgets["corner_radius"]
    assert isinstance(spin, QSpinBox)
    assert (spin.minimum(), spin.maximum(), spin.value()) == (0, 200, 0)
    spin.setValue(12)
    tool = tm.tool("rectangle")
    assert tool is not None and tool.creation_defaults["corner_radius"] == 12
    tm.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, main_window, QPointF(10, 10)))
    tm.handle_mouse_move(_event(QEvent.Type.MouseMove, main_window, QPointF(110, 70)))
    tm.handle_mouse_release(_event(QEvent.Type.MouseButtonRelease, main_window, QPointF(110, 70)))
    items = [i for i in main_window.scene.annotation_items() if isinstance(i, RectangleItem)]
    assert len(items) == 1 and items[0].corner_radius == 12.0


def test_the_panel_row_edits_placed_rectangles(qtbot: QtBot) -> None:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    layer = scene.layer_manager.active_layer
    assert layer is not None
    a = RectangleItem(rect=QRectF(0, 0, 100, 60))
    b = RectangleItem(rect=QRectF(0, 0, 100, 60), corner_radius=8.0)
    b.setPos(150, 0)
    for item in (a, b):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    sm.select(a)
    section = panel._rectangle_section  # noqa: SLF001
    assert section.isVisible()
    spin = panel._corner_radius_spin  # noqa: SLF001
    assert spin.value() == 0.0
    spin.setValue(20.0)
    assert a.corner_radius == 20.0
    assert scene.command_stack.undo_text == "Change corner_radius"
    sm.select_items([a, b])
    assert spin.text() == MIXED_TEXT
    panel._corner_radius_slider.setValue(5)  # noqa: SLF001
    assert a.corner_radius == 5.0 and b.corner_radius == 5.0
    scene.command_stack.undo()
    assert a.corner_radius == 20.0 and b.corner_radius == 8.0
    sm.select_items([a, RectangleItem()])
    assert not panel._arrow_section.isVisible()  # noqa: SLF001
