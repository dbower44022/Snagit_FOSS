"""The item blend mode on every item (Technical Architecture PRD 3.1.4, 3.9; General UI
PRD 8.3; Vector Item Properties decision 4, option A)."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.layer import ITEM_BLEND_MODES, composition_mode
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.io.project_serializer import ITEM_REGISTRY
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.blur_item import BlurItem
from snapmock.items.callout_item import CalloutItem
from snapmock.items.ellipse_item import EllipseItem
from snapmock.items.emoji_item import EmojiItem
from snapmock.items.freehand_item import FreehandItem
from snapmock.items.group_item import GroupItem
from snapmock.items.highlight_item import HighlightItem
from snapmock.items.line_item import LineItem
from snapmock.items.numbered_step_item import NumberedStepItem
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.stamp_item import StampItem
from snapmock.items.text_item import TextItem
from snapmock.ui.property_panel import PropertyPanel


def _every_item() -> list[SnapGraphicsItem]:
    image = QImage(4, 4, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.red)
    return [
        RectangleItem(),
        EllipseItem(),
        LineItem(),
        ArrowItem(),
        FreehandItem(),
        HighlightItem(),
        NumberedStepItem(),
        TextItem("t"),
        CalloutItem("c"),
        StampItem(),
        EmojiItem("🙂"),
        BlurItem(),
        RasterRegionItem(image),
        GroupItem(),
    ]


def test_every_item_round_trips_its_blend_mode(qapp: QApplication) -> None:
    for item in _every_item():
        expected = "Multiply" if isinstance(item, HighlightItem) else "Normal"
        assert item.blend_mode == expected, type(item).__name__
        item.blend_mode = "Screen"
        data = item.serialize()
        assert data["blend_mode"] == "Screen", type(item).__name__
        restored: Any = ITEM_REGISTRY[data["type"]].deserialize(data)
        assert restored.blend_mode == "Screen", type(item).__name__
        del data["blend_mode"]
        assert ITEM_REGISTRY[data["type"]].deserialize(data).blend_mode == "Normal"


def test_the_list_is_the_layers_seven_plus_soft_light() -> None:
    assert ITEM_BLEND_MODES == (
        "Normal",
        "Multiply",
        "Screen",
        "Overlay",
        "Soft Light",
        "Darken",
        "Lighten",
        "Difference",
    )
    assert composition_mode("Soft Light") == QPainter.CompositionMode.CompositionMode_SoftLight


def test_a_rectangle_in_multiply_darkens_what_is_beneath(qapp: QApplication) -> None:
    item = RectangleItem(rect=QRectF(0, 0, 60, 40))
    item.fill_color = QColor("#ffff00")
    item.stroke_width = 0.0
    background = QColor("#4060c0")

    def render() -> QColor:
        image = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(background)
        painter = QPainter(image)
        painter.translate(QPointF(20, 20))
        item.paint(painter, None)
        painter.end()
        return image.pixelColor(50, 40)

    assert render().name() == "#ffff00"
    item.blend_mode = "Multiply"
    multiplied = render()
    assert multiplied.blue() == 0 and multiplied.red() == background.red()


def test_the_panel_row_reaches_every_selected_item(qtbot: QtBot) -> None:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    layer = scene.layer_manager.active_layer
    assert layer is not None
    rect = RectangleItem(rect=QRectF(0, 0, 50, 50))
    stamp = StampItem()
    stamp.setPos(100, 100)
    for item in (rect, stamp):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    sm.select(rect)
    combo = panel._blend_combo  # noqa: SLF001
    assert panel._info_section.isVisible()  # noqa: SLF001
    assert combo.currentData() == "Normal"
    combo.setCurrentIndex(combo.findData("Overlay"))
    assert rect.blend_mode == "Overlay"
    assert scene.command_stack.undo_text == "Change blend_mode"
    sm.select_items([rect, stamp])
    assert combo.currentIndex() == -1  # mixed
    combo.setCurrentIndex(combo.findData("Darken"))
    assert rect.blend_mode == "Darken" and stamp.blend_mode == "Darken"
    scene.command_stack.undo()
    assert rect.blend_mode == "Overlay" and stamp.blend_mode == "Normal"
