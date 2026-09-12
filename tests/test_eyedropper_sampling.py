"""What the Eyedropper reads, and the four sample sizes (Blur PRD 4.2, 4.4).

Decision 2 of the Eyedropper and Blur performance work, option A: the sample is the canvas
composite — the canvas colour and every visible annotation item — built by an item walk, so
no grid line, guide, selection handle, or tool overlay can be sampled, and the area beyond
the canvas edge is transparent.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.render_engine import RenderEngine
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.tools.eyedropper_tool import EyedropperTool, average_color, sample_rect


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


def _add(scene: SnapScene, rect: QRectF, color: str) -> RectangleItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(QRectF(0, 0, rect.width(), rect.height()))
    item.setPos(rect.topLeft())
    item.fill_color = QColor(color)
    item.stroke_width = 0
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _raster(scene: SnapScene, image: QImage, at: QPointF) -> RasterRegionItem:
    """A raster item's pixels land one for one on the canvas, so a sample over them is
    exact where an antialiased vector edge is not."""
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RasterRegionItem(QPixmap.fromImage(image))
    item.setPos(at)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _squares(side: int, half: str, other: str) -> QImage:
    """*side* by *side* pixels: the left half *half*, the right half *other*."""
    image = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    painter.fillRect(0, 0, side // 2, side, QColor(half))
    painter.fillRect(side // 2, 0, side - side // 2, side, QColor(other))
    painter.end()
    return image


def _tool(scene: SnapScene) -> EyedropperTool:
    tool = EyedropperTool()
    tool.activate(scene, SelectionManager(scene))
    return tool


# ---- the sample area ----


def test_the_sample_area_is_centred_on_the_pixel_under_the_cursor() -> None:
    assert sample_rect(QPointF(10.7, 20.2), 1) == QRectF(10, 20, 1, 1)
    assert sample_rect(QPointF(10.7, 20.2), 3) == QRectF(9, 19, 3, 3)
    assert sample_rect(QPointF(10.0, 20.0), 5) == QRectF(8, 18, 5, 5)
    assert sample_rect(QPointF(10.0, 20.0), 11) == QRectF(5, 15, 11, 11)


def test_each_sample_size_reads_its_own_area(scene: SnapScene) -> None:
    """A known image: a white canvas under a 40 px black square, sampled at its corner.

    4.2's four sizes each average a different area, so the mean lightens as the square's
    corner takes up less of it. The square is a raster item, so every pixel is exact.
    """
    scene.set_background_color(QColor("#FFFFFF"))
    black = QImage(40, 40, QImage.Format.Format_ARGB32_Premultiplied)
    black.fill(QColor("#000000"))
    _raster(scene, black, QPointF(100, 100))
    tool = _tool(scene)
    at = QPointF(100.5, 100.5)  # the square's top-left pixel

    tool.creation_defaults["sample_size"] = 1
    assert tool.sample_at(at) == QColor(0, 0, 0)

    # Each area is centred on (100, 100), so a quarter of it lies inside the square.
    for size, inside in ((3, 4), (5, 9), (11, 36)):
        tool.creation_defaults["sample_size"] = size
        color = tool.sample_at(at)
        assert color.red() == color.green() == color.blue()
        assert color.red() == round(255 * (size * size - inside) / (size * size))
        assert color.alpha() == 255  # noqa: PLR2004


def test_the_average_over_a_boundary_is_the_arithmetic_mean(scene: SnapScene) -> None:
    """Two flat colours meeting under the cursor: the mean of the two, channel by channel."""
    scene.set_background_color(QColor("#FFFFFF"))
    _raster(scene, _squares(40, "#FF0000", "#0000FF"), QPointF(80, 130))
    tool = _tool(scene)
    tool.creation_defaults["sample_size"] = 5
    # Centred on x = 100, the first blue column: two red columns and three blue.
    color = tool.sample_at(QPointF(100.4, 150.0))
    assert color == QColor(round(255 * 2 / 5), 0, round(255 * 3 / 5))


def test_an_unknown_sample_size_falls_back_to_one_pixel(scene: SnapScene) -> None:
    tool = _tool(scene)
    tool.creation_defaults["sample_size"] = 4
    assert tool.sample_size == 1
    tool.creation_defaults["sample_size"] = "wide"
    assert tool.sample_size == 1


# ---- what is and is not canvas content ----


def test_a_transparent_area_is_reported_transparent(scene: SnapScene) -> None:
    """Over a transparent canvas, and beyond the canvas edge, the sample is transparent."""
    scene.set_background_color(QColor(0, 0, 0, 0))
    tool = _tool(scene)
    assert tool.sample_at(QPointF(50, 50)).alpha() == 0
    scene.set_background_color(QColor("#FFFFFF"))
    assert tool.sample_at(QPointF(50, 50)) == QColor("#FFFFFF")
    # Beyond the canvas the pasteboard is never sampled, whatever hangs over it there.
    _add(scene, QRectF(420, 40, 60, 60), "#00FF00")
    assert tool.sample_at(QPointF(450, 70)).alpha() == 0
    # Half over the edge: only part of the area carries alpha.
    tool.creation_defaults["sample_size"] = 5
    edge = tool.sample_at(QPointF(399.0, 150.0))
    assert 0 < edge.alpha() < 255  # noqa: PLR2004


def test_the_canvas_colour_is_sampled_where_nothing_covers_it(scene: SnapScene) -> None:
    """The fix for the sample that read through QGraphicsScene.render (notes 2.3)."""
    scene.set_background_color(QColor("#123456"))
    tool = _tool(scene)
    assert tool.sample_at(QPointF(200, 150)) == QColor("#123456")


def test_a_hidden_layers_items_are_not_sampled(scene: SnapScene) -> None:
    scene.set_background_color(QColor("#FFFFFF"))
    item = _add(scene, QRectF(100, 100, 100, 100), "#000000")
    tool = _tool(scene)
    assert tool.sample_at(QPointF(150, 150)) == QColor("#000000")
    item.setVisible(False)
    assert tool.sample_at(QPointF(150, 150)) == QColor("#FFFFFF")


def test_the_sample_leaves_the_tool_overlays_out(scene: SnapScene) -> None:
    """A raster selection's marching ants and a crop overlay are scene items with a
    z-value near a million; neither is a SnapGraphicsItem, so neither is sampled."""
    from snapmock.ui.crop_overlay import CropOverlay
    from snapmock.ui.selection_overlay import SelectionOverlay

    scene.set_background_color(QColor("#FFFFFF"))
    tool = _tool(scene)
    crop = CropOverlay(scene)
    crop.update_crop_rect(QRectF(0, 0, 400, 300))
    scene.addItem(crop)
    ants = SelectionOverlay(scene)
    ants.set_selection_rect(QRectF(0, 0, 400, 300))
    scene.addItem(ants)
    assert tool.sample_at(QPointF(200, 150)) == QColor("#FFFFFF")
    scene.removeItem(crop)
    scene.removeItem(ants)


def test_render_sample_is_the_size_of_the_area(scene: SnapScene) -> None:
    image = RenderEngine(scene).render_sample(QRectF(10, 20, 11, 11))
    assert image.width() == 11
    assert image.height() == 11


def test_an_empty_area_averages_to_transparent(scene: SnapScene) -> None:
    image = RenderEngine(scene).render_sample(QRectF(-50, -50, 5, 5))
    assert average_color(image) == QColor(0, 0, 0, 0)


# ---- the press, the drag, and the release ----


def _mouse(scene: SnapScene, kind: QMouseEvent.Type, scene_pos: QPointF) -> QMouseEvent:
    view = scene.views()[0]
    return QMouseEvent(
        kind,
        QPointF(view.mapFromScene(scene_pos)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_a_drag_previews_as_it_moves_and_applies_the_release_position(
    qapp: QApplication,
) -> None:
    """4.2: the colour display follows the cursor, and the release applies what is under it."""
    from snapmock.core.view import SnapView

    scene = SnapScene(width=400, height=300)
    scene.set_background_color(QColor("#FFFFFF"))
    view = SnapView(scene)
    view.resize(500, 400)
    _add(scene, QRectF(0, 0, 100, 300), "#FF0000")
    _add(scene, QRectF(200, 0, 100, 300), "#0000FF")
    tool = _tool(scene)
    previews: list[QColor] = []
    applied: list[QColor] = []
    tool.set_preview_callback(previews.append)
    tool.set_pick_callback(applied.append)

    assert tool.mouse_press(_mouse(scene, QMouseEvent.Type.MouseButtonPress, QPointF(50, 150)))
    assert tool.is_active_operation
    assert previews[-1] == QColor("#FF0000")
    assert not applied  # the press applies nothing

    assert tool.mouse_move(_mouse(scene, QMouseEvent.Type.MouseMove, QPointF(150, 150)))
    assert previews[-1] == QColor("#FFFFFF")
    assert tool.mouse_move(_mouse(scene, QMouseEvent.Type.MouseMove, QPointF(250, 150)))
    assert previews[-1] == QColor("#0000FF")
    assert not applied

    assert tool.mouse_release(
        _mouse(scene, QMouseEvent.Type.MouseButtonRelease, QPointF(250, 150))
    )
    assert applied == [QColor("#0000FF")]
    assert tool.picked_color == QColor("#0000FF")
    assert tool.pick_serial == 1
    assert not tool.is_active_operation
    view.deleteLater()


def test_a_move_without_a_press_samples_nothing(qapp: QApplication) -> None:
    from snapmock.core.view import SnapView

    scene = SnapScene(width=400, height=300)
    view = SnapView(scene)
    tool = _tool(scene)
    seen: list[QColor] = []
    tool.set_preview_callback(seen.append)
    assert not tool.mouse_move(_mouse(scene, QMouseEvent.Type.MouseMove, QPointF(10, 10)))
    assert not seen
    view.deleteLater()


def test_cancel_drops_the_drag_without_applying(qapp: QApplication) -> None:
    from snapmock.core.view import SnapView

    scene = SnapScene(width=400, height=300)
    scene.set_background_color(QColor("#FFFFFF"))
    view = SnapView(scene)
    tool = _tool(scene)
    applied: list[QColor] = []
    tool.set_pick_callback(applied.append)
    tool.mouse_press(_mouse(scene, QMouseEvent.Type.MouseButtonPress, QPointF(50, 50)))
    tool.cancel()
    assert not tool.is_active_operation
    assert not tool.mouse_release(
        _mouse(scene, QMouseEvent.Type.MouseButtonRelease, QPointF(50, 50))
    )
    assert not applied
    assert tool.pick_serial == 0
    view.deleteLater()
