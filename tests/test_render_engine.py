"""Tests for RenderEngine."""

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from snapmock.core.render_engine import RenderEngine
from snapmock.core.scene import SnapScene


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


def test_render_default_size(scene: SnapScene) -> None:
    engine = RenderEngine(scene)
    img = engine.render_to_image()
    assert img.width() == 400
    assert img.height() == 300


def test_render_custom_size(scene: SnapScene) -> None:
    engine = RenderEngine(scene)
    img = engine.render_to_image(width=200, height=150)
    assert img.width() == 200
    assert img.height() == 150


def test_render_with_background(scene: SnapScene) -> None:
    engine = RenderEngine(scene)
    img = engine.render_to_image(background=QColor("blue"))
    assert not img.isNull()


# ---- the layer blend mode reaches every render (follow-up step 3, decision 3) ----


def _yellow_rect_on_multiply_layer(scene: SnapScene) -> str:
    """A blue canvas with a yellow rectangle on a Multiply layer; returns the layer id."""
    from PyQt6.QtCore import QRectF

    from snapmock.commands.add_item import AddItemCommand
    from snapmock.items.rectangle_item import RectangleItem

    scene.set_background_color(QColor("blue"))
    layer = scene.layer_manager.add_layer("Multiply")
    scene.layer_manager.set_blend_mode(layer.layer_id, "Multiply")
    item = RectangleItem(QRectF(0, 0, 100, 100))
    item.setPos(50, 50)
    item.fill_color = QColor("yellow")
    item.stroke_color = QColor("yellow")
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return layer.layer_id


def test_multiply_layer_multiplies_in_the_display_render(scene: SnapScene) -> None:
    from PyQt6.QtCore import QRectF

    layer_id = _yellow_rect_on_multiply_layer(scene)
    engine = RenderEngine(scene)
    # Yellow (255, 255, 0) multiplied by blue (0, 0, 255) is black
    full = engine.render_to_image(background=QColor("blue"))
    assert full.pixelColor(100, 100) == QColor("black")
    assert full.pixelColor(10, 10) == QColor("blue")
    region = engine.render_region(QRectF(50, 50, 100, 100), background=QColor("blue"))
    assert region.pixelColor(50, 50) == QColor("black")
    # Back to Normal the rectangle is yellow again
    scene.layer_manager.set_blend_mode(layer_id, "Normal")
    assert engine.render_to_image(background=QColor("blue")).pixelColor(100, 100) == QColor(
        "yellow"
    )


def test_layer_thumbnail_shows_a_multiply_layers_items(scene: SnapScene) -> None:
    """The Layer Panel thumbnail renders the layer alone on transparency: the item shows."""
    from PyQt6.QtCore import QRectF

    layer_id = _yellow_rect_on_multiply_layer(scene)
    image = RenderEngine(scene).render_layer_region(layer_id, QRectF(0, 0, 400, 300))
    assert image.pixelColor(100, 100) == QColor("yellow")
    assert image.pixelColor(10, 10).alpha() == 0


def test_blend_mode_reaches_items_and_groups(scene: SnapScene) -> None:
    from PyQt6.QtCore import QRectF

    from snapmock.commands.add_item import AddItemCommand
    from snapmock.items.group_item import GroupItem
    from snapmock.items.rectangle_item import RectangleItem

    layer = scene.layer_manager.layers[0]
    a = RectangleItem(QRectF(0, 0, 10, 10))
    b = RectangleItem(QRectF(0, 0, 10, 10))
    group = GroupItem()
    group.add_member(a)
    group.add_member(b)
    scene.command_stack.push(AddItemCommand(scene, group, layer.layer_id))
    assert a.layer_blend_mode == "Normal"
    scene.layer_manager.set_blend_mode(layer.layer_id, "Screen")
    assert group.layer_blend_mode == "Screen" and a.layer_blend_mode == "Screen"
    # An item added to a blended layer takes the mode on entry
    c = RectangleItem(QRectF(0, 0, 10, 10))
    scene.command_stack.push(AddItemCommand(scene, c, layer.layer_id))
    assert c.layer_blend_mode == "Screen"
    assert "layer_blend_mode" not in c.serialize()
