"""Tests for PropertyPanel, property shims, ScaleGeometryCommand, and background_color."""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPixmap
from pytestqt.qtbot import QtBot

from snapmock.commands.scale_geometry_command import ScaleGeometryCommand
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.ui.property_panel import PropertyPanel


def _make_panel(qtbot: QtBot) -> tuple[PropertyPanel, SnapScene, SelectionManager]:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    return panel, scene, sm


def _add_rect(scene: SnapScene) -> RectangleItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.layer_id = layer.layer_id
    layer.item_ids.append(item.item_id)
    scene.addItem(item)
    return item


def _add_raster(scene: SnapScene) -> RasterRegionItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RasterRegionItem(pixmap=QPixmap(50, 50))
    item.layer_id = layer.layer_id
    layer.item_ids.append(item.item_id)
    scene.addItem(item)
    return item


# --- Canvas mode (no selection) ---


def test_canvas_mode_when_empty(qtbot: QtBot) -> None:
    panel, _scene, _sm = _make_panel(qtbot)
    assert panel._canvas_section.isVisible()
    assert not panel._transform_section.isVisible()
    assert not panel._appearance_section.isVisible()
    assert not panel._info_section.isVisible()


# --- Item mode (item selected) ---


def test_item_mode_when_selected(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_rect(scene)
    sm.select(item)
    assert panel._transform_section.isVisible()
    assert panel._info_section.isVisible()
    assert not panel._canvas_section.isVisible()


# --- Appearance section visibility ---


def test_appearance_visible_for_vector_item(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_rect(scene)
    sm.select(item)
    assert panel._appearance_section.isVisible()


def test_appearance_hidden_for_non_vector_item(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_raster(scene)
    sm.select(item)
    assert not panel._appearance_section.isVisible()


# --- Transform spinboxes reflect item state ---


def test_transform_reflects_item_position(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_rect(scene)
    item.setPos(42.0, 73.0)
    sm.select(item)
    assert panel._x_spin.value() == 42.0
    assert panel._y_spin.value() == 73.0


def test_transform_reflects_item_size(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_rect(scene)
    sm.select(item)
    # RectangleItem default is 100x60, but boundingRect includes stroke_width/2
    br = item.boundingRect()
    assert panel._w_spin.value() == br.width()
    assert panel._h_spin.value() == br.height()


# --- Layer combo lists all layers ---


def test_layer_combo_lists_layers(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    scene.layer_manager.add_layer("Layer 2")
    item = _add_rect(scene)
    sm.select(item)
    assert panel._layer_combo.count() == 2


# --- ScaleGeometryCommand ---


def test_scale_geometry_command_redo_undo(qtbot: QtBot) -> None:
    scene = SnapScene()
    item = RectangleItem(rect=QRectF(0, 0, 100, 50))
    scene.addItem(item)

    cmd = ScaleGeometryCommand(item, 2.0, 3.0)
    cmd.redo()
    assert abs(item.boundingRect().width() - 100 * 2.0 - item._stroke_width) < 1.0
    assert abs(item.boundingRect().height() - 50 * 3.0 - item._stroke_width) < 1.0

    cmd.undo()
    # Should be back to roughly original size
    assert abs(item.boundingRect().width() - 100 - item._stroke_width) < 1.0
    assert abs(item.boundingRect().height() - 50 - item._stroke_width) < 1.0


# --- Background color ---


def test_scene_background_color_default() -> None:
    scene = SnapScene()
    assert scene.background_color == QColor("white")


def test_scene_set_background_color() -> None:
    scene = SnapScene()
    scene.set_background_color(QColor("red"))
    assert scene.background_color == QColor("red")


def test_background_changed_signal(qtbot: QtBot) -> None:
    scene = SnapScene()
    with qtbot.waitSignal(scene.background_changed, timeout=1000):
        scene.set_background_color(QColor("blue"))


# --- Property shims ---


def test_pos_x_property_shim() -> None:
    scene = SnapScene()
    item = RectangleItem()
    scene.addItem(item)
    item.pos_x = 55.0
    assert item.pos_x == 55.0
    assert item.pos().x() == 55.0


def test_pos_y_property_shim() -> None:
    scene = SnapScene()
    item = RectangleItem()
    scene.addItem(item)
    item.pos_y = 33.0
    assert item.pos_y == 33.0
    assert item.pos().y() == 33.0


def test_rotation_deg_property_shim() -> None:
    scene = SnapScene()
    item = RectangleItem()
    scene.addItem(item)
    item.rotation_deg = 45.0
    assert item.rotation_deg == 45.0
    assert item.rotation() == 45.0


def test_opacity_pct_property_shim() -> None:
    scene = SnapScene()
    item = RectangleItem()
    scene.addItem(item)
    item.opacity_pct = 50.0
    assert item.opacity_pct == 50.0
    assert abs(item.opacity() - 0.5) < 0.01


def test_opacity_pct_clamps() -> None:
    scene = SnapScene()
    item = RectangleItem()
    scene.addItem(item)
    item.opacity_pct = 150.0
    assert item.opacity_pct == 100.0
    item.opacity_pct = -10.0
    assert item.opacity_pct == 0.0
