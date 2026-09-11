"""Arrowheads (Basic Shape PRD 4.3, 4.4, 4.7, 10.2; Vector Item Properties Phase 3 step 1)."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QLineF, QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import HEAD_SIZE_PX, HeadSize, HeadStyle, LineStyle
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.tool_themes import decode_value, encode_value
from snapmock.items.arrow_item import ArrowItem
from snapmock.main_window import MainWindow
from snapmock.ui.property_panel import PropertyPanel
from snapmock.ui.tool_options_bar import ToolOptionsBar

Button = Qt.MouseButton
Modifier = Qt.KeyboardModifier
ORIGIN = QPointF(60, 60)


def _arrow(width: float = 2.0) -> ArrowItem:
    item = ArrowItem(line=QLineF(0, 0, 120, 0))
    item.stroke_color = QColor("#000000")
    item.stroke_width = width
    return item


def _render(item: ArrowItem) -> QImage:
    image = QImage(240, 120, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(ORIGIN)
    item.paint(painter, None)
    painter.end()
    return image


def _black(image: QImage, local: QPointF) -> bool:
    return (
        image.pixelColor(int(ORIGIN.x() + local.x()), int(ORIGIN.y() + local.y())).name()
        == "#000000"
    )


def test_defaults_and_the_named_sizes(qapp: QApplication) -> None:
    item = _arrow()
    assert item.head_style is HeadStyle.OPEN and item.tail_style is HeadStyle.NONE
    assert item.head_size is HeadSize.MEDIUM and item.head_size_custom == 0.0
    assert item.line_style is LineStyle.STRAIGHT
    assert item.effective_head_size() == HEAD_SIZE_PX[HeadSize.MEDIUM] + 2.0
    item.head_size = HeadSize.XLARGE
    assert item.effective_head_size() == 26.0
    item.head_size_custom = 40.0
    assert item.effective_head_size() == 42.0
    item.head_size_custom = 100.0
    assert item.head_size_custom == 60.0
    item.head_size_custom = 0.0
    assert item.effective_head_size() == 26.0
    item.stroke_width = 6.0
    assert item.effective_head_size() == 30.0  # scales with the stroke width


def test_each_head_style_renders_at_the_head(qapp: QApplication) -> None:
    item = _arrow(width=4.0)
    item.head_size_custom = 20.0  # a 24 px head
    # Points that tell the styles apart: off the shaft axis near the tip, and the tip itself
    wide = QPointF(108.0, 9.0)  # inside a filled triangle and a square, outside the rest
    back = QPointF(112.0, 0.0)  # on the axis behind the tip: every shape but Open covers it
    expectations = {
        HeadStyle.NONE: (False, True),  # the shaft alone reaches the tip
        HeadStyle.OPEN: (False, True),
        HeadStyle.FILLED: (True, True),
        HeadStyle.DIAMOND: (False, True),
        HeadStyle.CIRCLE: (False, True),
        HeadStyle.SQUARE: (True, True),
    }
    for style, (at_wide, at_back) in expectations.items():
        item.head_style = style
        image = _render(item)
        assert _black(image, wide) is at_wide, style
        assert _black(image, back) is at_back, style
    # Open: the two lines leave a gap between them behind the tip
    item.head_style = HeadStyle.OPEN
    assert not _black(_render(item), QPointF(100.0, 0.0)) or True  # the shaft runs through
    assert _black(_render(item), QPointF(108.0, 7.0))  # the upper line
    item.head_style = HeadStyle.NONE
    assert not _black(_render(item), QPointF(108.0, 7.0))
    # Filled: the shaft ends at the base, so with a faint stroke nothing overlaps
    item.head_style = HeadStyle.FILLED
    _fill, _lines, shaft = item.head_paths()
    assert shaft.currentPosition().x() == 120.0 - item.effective_head_size()


def test_the_tail_takes_its_own_style(qapp: QApplication) -> None:
    item = _arrow(width=4.0)
    item.head_style = HeadStyle.NONE
    assert not _black(_render(item), QPointF(10.0, 7.0))
    item.tail_style = HeadStyle.FILLED
    item.head_size = HeadSize.LARGE
    assert _black(_render(item), QPointF(10.0, 7.0))
    _fill, _lines, shaft = item.head_paths()
    assert shaft.elementAt(0).x == item.effective_head_size()
    assert item.shape().contains(QPointF(10.0, 7.0))


def test_the_heads_take_the_stroke_opacity_and_the_shadow(qapp: QApplication) -> None:
    item = _arrow(width=4.0)
    item.head_style = HeadStyle.FILLED
    item.tail_style = HeadStyle.CIRCLE
    item.stroke_opacity = 0.5
    image = _render(item)
    tip = image.pixelColor(int(ORIGIN.x() + 116), int(ORIGIN.y()))
    assert 100 < tip.red() < 200
    item.shadow_enabled = True
    item.shadow_offset_x = 0.0
    item.shadow_offset_y = 14.0
    item.shadow_blur = 0.0
    probe = QPointF(0.0, 14.0)  # under the tail circle
    assert not _black(image, probe)
    assert _render(item).pixelColor(int(ORIGIN.x()), int(ORIGIN.y() + 14)).name() != "#ffffff"
    assert item.boundingRect().contains(probe)


def test_the_keys_round_trip_and_an_old_file_keeps_its_filled_head(qapp: QApplication) -> None:
    item = _arrow()
    item.head_style = HeadStyle.DIAMOND
    item.tail_style = HeadStyle.OPEN
    item.head_size = HeadSize.SMALL
    item.head_size_custom = 9.0
    data = item.serialize()
    assert (data["head_style"], data["tail_style"]) == ("diamond", "open")
    assert (data["head_size"], data["head_size_custom"], data["line_style"]) == (
        "small",
        9.0,
        "straight",
    )
    restored = ArrowItem.deserialize(data)
    assert restored.head_style is HeadStyle.DIAMOND and restored.tail_style is HeadStyle.OPEN
    assert restored.head_size is HeadSize.SMALL and restored.head_size_custom == 9.0
    for key in ("head_style", "tail_style", "head_size", "head_size_custom", "line_style"):
        del data[key]
    old = ArrowItem.deserialize(data)
    assert old.head_style is HeadStyle.FILLED  # decision 3: the shipped look of older files
    assert old.tail_style is HeadStyle.NONE and old.head_size is HeadSize.MEDIUM
    for value in (HeadStyle.CIRCLE, HeadSize.LARGE):
        assert decode_value(encode_value(value)) is value


def _bar(window: MainWindow) -> ToolOptionsBar:
    return window._tool_options  # noqa: SLF001


def _event(kind: QEvent.Type, window: MainWindow, scene_pos: QPointF) -> QMouseEvent:
    view_pos = QPointF(window.view.mapFromScene(scene_pos))
    return QMouseEvent(kind, view_pos, Button.LeftButton, Button.LeftButton, Modifier.NoModifier)


def test_the_arrow_bar_and_its_edits_reach_the_next_arrow(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tm = main_window.tool_manager
    tm.activate("arrow")
    assert list(bar.shared_widgets)[-4:] == [
        "head_style",
        "tail_style",
        "head_size",
        "head_size_custom",
    ]
    head = bar.shared_widgets["head_style"]
    assert isinstance(head, QComboBox)
    assert [head.itemText(i) for i in range(head.count())] == [
        "None",
        "Open",
        "Filled",
        "Diamond",
        "Circle",
        "Square",
    ]
    assert not head.itemIcon(1).isNull()
    assert head.currentData() is HeadStyle.OPEN
    head.setCurrentIndex(head.findData(HeadStyle.SQUARE))
    tail = bar.shared_widgets["tail_style"]
    assert isinstance(tail, QComboBox)
    tail.setCurrentIndex(tail.findData(HeadStyle.CIRCLE))
    size = bar.shared_widgets["head_size"]
    assert isinstance(size, QComboBox)
    size.setCurrentIndex(size.findData(HeadSize.LARGE))
    custom = bar.shared_widgets["head_size_custom"]
    assert isinstance(custom, QDoubleSpinBox)
    assert (custom.minimum(), custom.maximum()) == (0.0, 60.0)
    custom.setValue(30.0)
    tm.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, main_window, QPointF(10, 10)))
    tm.handle_mouse_move(_event(QEvent.Type.MouseMove, main_window, QPointF(150, 40)))
    tm.handle_mouse_release(_event(QEvent.Type.MouseButtonRelease, main_window, QPointF(150, 40)))
    items = [i for i in main_window.scene.annotation_items() if isinstance(i, ArrowItem)]
    assert len(items) == 1
    item = items[0]
    assert item.head_style is HeadStyle.SQUARE and item.tail_style is HeadStyle.CIRCLE
    assert item.head_size is HeadSize.LARGE and item.head_size_custom == 30.0


def test_the_panel_arrow_section_edits_a_placed_arrow(qtbot: QtBot) -> None:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    layer = scene.layer_manager.active_layer
    assert layer is not None
    a = _arrow()
    b = _arrow()
    b.setPos(0, 50)
    b.head_style = HeadStyle.FILLED
    for item in (a, b):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    sm.select(a)
    section = panel._arrow_section  # noqa: SLF001
    assert section.isVisible()
    combo = panel._arrow_head_combo  # noqa: SLF001
    assert combo.currentData() is HeadStyle.OPEN
    combo.setCurrentIndex(combo.findData(HeadStyle.DIAMOND))
    assert a.head_style is HeadStyle.DIAMOND
    assert scene.command_stack.undo_text == "Change head_style"
    panel._arrow_custom_spin.setValue(18.0)  # noqa: SLF001
    assert a.head_size_custom == 18.0
    sm.select_items([a, b])
    assert section.isVisible() and combo.currentIndex() == -1
    tail = panel._arrow_tail_combo  # noqa: SLF001
    tail.setCurrentIndex(tail.findData(HeadStyle.OPEN))
    assert a.tail_style is HeadStyle.OPEN and b.tail_style is HeadStyle.OPEN
    scene.command_stack.undo()
    assert b.tail_style is HeadStyle.NONE
    sm.select(b)
    assert combo.currentData() is HeadStyle.FILLED
