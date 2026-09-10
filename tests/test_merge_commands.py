"""MergeLayersCommand: Merge Down, Merge Visible, Flatten All (follow-up step 4, decision 1)."""

from __future__ import annotations

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.merge_commands import FLATTENED_LAYER_NAME, MergeLayersCommand
from snapmock.core.scene import SnapScene
from snapmock.items.group_item import GroupItem
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem


def _rect(scene: SnapScene, layer_id: str, x: float, y: float, colour: str) -> RectangleItem:
    item = RectangleItem(QRectF(0, 0, 100, 100))
    item.setPos(x, y)
    item.fill_color = QColor(colour)
    item.stroke_color = QColor(colour)
    scene.command_stack.push(AddItemCommand(scene, item, layer_id))
    return item


def _regions(scene: SnapScene) -> list[RasterRegionItem]:
    return [i for i in scene.annotation_items() if isinstance(i, RasterRegionItem)]


def test_merge_down_rasterizes_both_layers_into_the_lower_one(scene: SnapScene) -> None:
    lm = scene.layer_manager
    lower = lm.layers[0]
    upper = lm.add_layer("Upper")
    lm.set_active(upper.layer_id)
    lm.rename_layer(lower.layer_id, "Lower")
    lm.set_opacity(lower.layer_id, 0.5)
    lm.set_blend_mode(lower.layer_id, "Screen")
    a = _rect(scene, lower.layer_id, 10, 10, "red")
    b = _rect(scene, upper.layer_id, 200, 10, "blue")
    lm.set_active(upper.layer_id)

    cmd = MergeLayersCommand(scene, [upper.layer_id, lower.layer_id], lower.layer_id)
    scene.command_stack.push(cmd)

    assert lm.count == 1 and lm.layers[0] is lower
    # The result layer keeps its own properties (follow-up decision 1)
    assert lower.name == "Lower" and lower.opacity == 0.5 and lower.blend_mode == "Screen"
    assert lm.active_layer is lower
    regions = _regions(scene)
    assert len(regions) == 1 and scene.annotation_items() == regions
    region = regions[0]
    assert region.layer_id == lower.layer_id and lower.item_ids == [region.item_id]
    assert region.pos().x() == 0 and region.pos().y() == 0
    pixmap = region.pixmap
    assert (pixmap.width(), pixmap.height()) == (
        int(scene.canvas_size.width()),
        int(scene.canvas_size.height()),
    )
    image = pixmap.toImage()
    # The lower layer's items are painted plain: its 50 percent is not baked in
    assert image.pixelColor(50, 50) == QColor("red")
    assert image.pixelColor(250, 50) == QColor("blue")
    assert image.pixelColor(400, 400).alpha() == 0
    assert a.scene() is None and b.scene() is None

    scene.command_stack.undo()
    assert [layer.name for layer in lm.layers] == ["Lower", "Upper"]
    assert lm.active_layer is upper
    assert a.scene() is scene and b.scene() is scene
    assert lower.item_ids == [a.item_id] and upper.item_ids == [b.item_id]
    assert region.scene() is None
    assert b.zValue() == upper.z_base

    scene.command_stack.redo()
    assert lm.count == 1 and _regions(scene) == [region] and lm.active_layer is lower


def test_merge_bakes_the_upper_layers_opacity_and_blend_mode(scene: SnapScene) -> None:
    lm = scene.layer_manager
    lower = lm.layers[0]
    upper = lm.add_layer("Multiply")
    lm.set_blend_mode(upper.layer_id, "Multiply")
    lm.set_opacity(upper.layer_id, 0.5)
    _rect(scene, lower.layer_id, 0, 0, "blue")
    _rect(scene, upper.layer_id, 0, 0, "yellow")
    scene.command_stack.push(
        MergeLayersCommand(scene, [lower.layer_id, upper.layer_id], lower.layer_id)
    )
    image = _regions(scene)[0].pixmap.toImage()
    # Yellow at 50 percent multiplied over blue: blue halved, no red or green
    colour = image.pixelColor(50, 50)
    assert colour.red() == 0 and colour.green() == 0
    assert 100 <= colour.blue() <= 160


def test_merge_visible_leaves_hidden_layers_in_place(scene: SnapScene) -> None:
    lm = scene.layer_manager
    bottom = lm.layers[0]
    hidden = lm.add_layer("Hidden")
    top = lm.add_layer("Top")
    lm.set_visibility(hidden.layer_id, False)
    _rect(scene, bottom.layer_id, 0, 0, "red")
    hidden_item = _rect(scene, hidden.layer_id, 0, 0, "green")
    _rect(scene, top.layer_id, 150, 0, "blue")
    lm.set_active(top.layer_id)
    visible = [layer.layer_id for layer in lm.layers if layer.visible]
    scene.command_stack.push(MergeLayersCommand(scene, visible, bottom.layer_id))
    assert [layer.name for layer in lm.layers] == ["Layer 1", "Hidden"]
    assert hidden_item.scene() is scene and hidden.item_ids == [hidden_item.item_id]
    assert lm.active_layer is bottom
    image = _regions(scene)[0].pixmap.toImage()
    assert image.pixelColor(50, 50) == QColor("red")
    assert image.pixelColor(200, 50) == QColor("blue")
    scene.command_stack.undo()
    assert [layer.name for layer in lm.layers] == ["Layer 1", "Hidden", "Top"]
    assert lm.active_layer is top


def test_flatten_all_leaves_one_background_layer_with_the_canvas_colour(
    scene: SnapScene,
) -> None:
    lm = scene.layer_manager
    scene.set_background_color(QColor("white"))
    first = lm.layers[0]
    second = lm.add_layer("Second")
    hidden = lm.add_layer("Hidden")
    lm.set_visibility(hidden.layer_id, False)
    _rect(scene, first.layer_id, 0, 0, "red")
    _rect(scene, second.layer_id, 150, 0, "blue")
    _rect(scene, hidden.layer_id, 300, 0, "green")
    lm.set_active(second.layer_id)
    scene.command_stack.push(MergeLayersCommand.flatten_all(scene))
    assert lm.count == 1
    result = lm.layers[0]
    assert result.name == FLATTENED_LAYER_NAME and result.is_background
    assert result.opacity == 1.0 and result.blend_mode == "Normal"
    assert lm.active_layer is result and lm.background_layer is result
    image = _regions(scene)[0].pixmap.toImage()
    assert image.pixelColor(50, 50) == QColor("red")
    assert image.pixelColor(200, 50) == QColor("blue")
    assert image.pixelColor(350, 50) == QColor("white")  # the hidden layer is not painted
    assert image.pixelColor(390, 290) == QColor("white")  # the canvas colour
    scene.command_stack.undo()
    assert [layer.name for layer in lm.layers] == ["Layer 1", "Second", "Hidden"]
    assert lm.background_layer is None and lm.active_layer is second
    assert len(scene.annotation_items()) == 3
    scene.command_stack.redo()
    assert lm.count == 1 and lm.layers[0] is result


def test_flatten_all_keeps_a_transparent_canvas_transparent(scene: SnapScene) -> None:
    lm = scene.layer_manager
    scene.set_background_color(QColor(0, 0, 0, 0))
    lm.add_layer("Second")
    _rect(scene, lm.layers[0].layer_id, 0, 0, "red")
    scene.command_stack.push(MergeLayersCommand.flatten_all(scene))
    image = _regions(scene)[0].pixmap.toImage()
    assert image.pixelColor(50, 50) == QColor("red")
    assert image.pixelColor(390, 290).alpha() == 0


def test_a_group_on_a_merged_layer_is_rendered_and_gone(scene: SnapScene) -> None:
    lm = scene.layer_manager
    lower = lm.layers[0]
    upper = lm.add_layer("Upper")
    a = RectangleItem(QRectF(0, 0, 50, 50))
    a.fill_color = QColor("blue")
    a.stroke_color = QColor("blue")
    a.setPos(100, 100)
    group = GroupItem()
    group.add_member(a)
    scene.command_stack.push(AddItemCommand(scene, group, upper.layer_id))
    scene.command_stack.push(
        MergeLayersCommand(scene, [lower.layer_id, upper.layer_id], lower.layer_id)
    )
    assert group.scene() is None and a.scene() is None
    image = _regions(scene)[0].pixmap.toImage()
    assert image.pixelColor(125, 125) == QColor("blue")
    scene.command_stack.undo()
    assert group.scene() is scene and a.parentItem() is group and upper.item_ids == [group.item_id]
