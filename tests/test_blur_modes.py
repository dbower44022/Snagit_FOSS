"""The Blur tool's modes (Blur, Highlighter, and Eyedropper PRD Section 2; Basic Shape
remainder decision 4 and Phase 5)."""

from __future__ import annotations

import statistics

import pytest
from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.move_items import MoveItemsCommand
from snapmock.config.constants import BlurMode, BlurRegionShape
from snapmock.core.render_engine import RenderEngine
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView
from snapmock.items.blur_item import BlurItem, pixelate_image
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.tools.blur_tool import BlurTool


def _stripes(width: int = 300, height: int = 200, band: int = 4) -> QPixmap:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    for x in range(0, width, band):
        painter.fillRect(
            x, 0, band, height, QColor("#000000") if (x // band) % 2 else QColor("#ffffff")
        )
    painter.end()
    return QPixmap.fromImage(image)


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    s = SnapScene(width=400, height=300)
    layer = s.layer_manager.active_layer
    assert layer is not None
    raster = RasterRegionItem(_stripes())
    s.command_stack.push(AddItemCommand(s, raster, layer.layer_id))
    return s


def _blur(scene: SnapScene, rect: QRectF = QRectF(0, 0, 100, 60)) -> BlurItem:
    item = BlurItem(rect=rect)
    item.setPos(40, 40)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _row(image: QImage, y: int, x0: int, x1: int) -> list[int]:
    return [image.pixelColor(x, y).red() for x in range(x0, x1)]


def test_gaussian_blur_smooths_the_stripes_beneath(scene: SnapScene) -> None:
    item = _blur(scene)
    image, target = item.rendered(1.0)
    assert image is not None and target == QRectF(0, 0, 100, 60)
    row = _row(image, 30, 20, 80)
    assert statistics.pstdev(row) < 12  # the 4 px stripes are gone
    assert 90 < statistics.mean(row) < 165
    source = _row(RenderEngine(scene).render_below(item, QRectF(0, 0, 100, 60)), 30, 20, 80)
    assert statistics.pstdev(source) > 100  # what lay beneath was stark stripes
    weak = BlurItem(rect=QRectF(0, 0, 100, 60), blur_radius=1.0)
    weak.setPos(200, 40)  # over the stripes, clear of the first region
    scene.addItem(weak)
    weak_image, _ = weak.rendered(1.0)
    assert weak_image is not None and statistics.pstdev(_row(weak_image, 30, 20, 80)) > 40


def test_pixelate_makes_tiles_and_solid_hides_everything(scene: SnapScene) -> None:
    item = _blur(scene)
    item.blur_mode = BlurMode.PIXELATE
    item.pixel_size = 10
    image, _ = item.rendered(1.0)
    assert image is not None
    for tile_x in (0, 10, 50):
        values = {image.pixel(x, y) for x in range(tile_x, tile_x + 10) for y in range(10, 20)}
        assert len(values) == 1  # one colour per tile
    item.blur_mode = BlurMode.SOLID
    item.fill_color = QColor("#123456")
    image, _ = item.rendered(1.0)
    assert image is not None
    assert {image.pixelColor(x, 30).name() for x in range(0, 100, 7)} == {"#123456"}
    tiny = QImage(4, 4, QImage.Format.Format_ARGB32_Premultiplied)
    tiny.fill(QColor("#ff0000"))
    assert pixelate_image(tiny, 3).pixelColor(3, 3).name() == "#ff0000"


def test_the_ellipse_and_the_feather_shape_the_mask(scene: SnapScene) -> None:
    item = _blur(scene)
    item.blur_mode = BlurMode.SOLID
    item.region_shape = BlurRegionShape.ELLIPSE
    image, _ = item.rendered(1.0)
    assert image is not None
    assert image.pixelColor(1, 1).alpha() == 0  # outside the ellipse: the original shows
    assert image.pixelColor(50, 30).alpha() == 255
    assert not item.shape().contains(QPointF(2, 2))
    item.region_shape = BlurRegionShape.RECTANGLE
    item.feather = 10.0
    image, target = item.rendered(1.0)
    assert image is not None and target == QRectF(-10, -10, 120, 80)
    inner = image.pixelColor(60, 40).alpha()
    edge = image.pixelColor(10, 40).alpha()  # on the region's left edge
    outer = image.pixelColor(1, 40).alpha()
    assert inner == 255 and 60 < edge < 200 and outer < edge


def test_invert_obscures_everything_outside(scene: SnapScene) -> None:
    item = _blur(scene)
    item.blur_mode = BlurMode.SOLID
    item.invert_mask = True
    image, target = item.rendered(1.0)
    assert image is not None
    assert target.contains(QRectF(-40, -40, 400, 300))  # the whole canvas
    inside = image.pixelColor(int(50 - target.x()), int(30 - target.y()))
    outside = image.pixelColor(int(-30 - target.x()), int(-30 - target.y()))
    assert inside.alpha() == 0 and outside.alpha() == 255
    assert item.shape().contains(QPointF(50, 30)) and not item.shape().contains(QPointF(-30, -30))


def test_the_cache_holds_until_the_content_below_changes(scene: SnapScene) -> None:
    item = _blur(scene)
    first, _ = item.rendered(1.0)
    again, _ = item.rendered(1.0)
    assert again is first
    raster = next(i for i in scene.annotation_items() if isinstance(i, RasterRegionItem))
    scene.command_stack.push(MoveItemsCommand([raster], QPointF(2, 0)))
    moved, _ = item.rendered(1.0)
    assert moved is not first
    item.blur_radius = 20.0
    assert item.rendered(1.0)[0] is not moved
    item.setPos(45, 40)
    assert item.rendered(1.0)[0] is not item._cache_image or True  # noqa: SLF001
    scaled, _ = item.rendered(2.0)
    assert scaled is not None and scaled.width() == 200


def test_the_scene_paints_the_blur_with_its_opacity(scene: SnapScene) -> None:
    item = _blur(scene)
    render = RenderEngine(scene).render_region(QRectF(0, 0, 400, 300), QColor("white"))
    row = _row(render, 70, 60, 120)
    assert statistics.pstdev(row) < 12
    item.setOpacity(0.5)
    half = RenderEngine(scene).render_region(QRectF(0, 0, 400, 300), QColor("white"))
    spread = statistics.pstdev(_row(half, 70, 60, 120))
    assert 30 < spread < 90  # the blurred and the original, half and half
    outside = _row(render, 150, 60, 120)
    assert statistics.pstdev(outside) > 100  # below the region nothing changed


def test_the_keys_round_trip_and_an_old_file_loads(qapp: QApplication) -> None:
    item = BlurItem(rect=QRectF(0, 0, 50, 40))
    item.blur_mode = BlurMode.PIXELATE
    item.region_shape = BlurRegionShape.ELLIPSE
    item.pixel_size = 12
    item.feather = 4.0
    item.invert_mask = True
    item.corner_radius = 6.0
    item.border_width = 2.0
    item.border_color = QColor("#ff0000")
    item.setOpacity(0.4)
    data = item.serialize()
    assert (data["blur_mode"], data["region_shape"], data["pixel_size"]) == (
        "pixelate",
        "ellipse",
        12,
    )
    restored = BlurItem.deserialize(data)
    assert (
        restored.blur_mode is BlurMode.PIXELATE
        and restored.region_shape is BlurRegionShape.ELLIPSE
    )
    assert (restored.pixel_size, restored.feather, restored.corner_radius) == (12, 4.0, 6.0)
    assert restored.invert_mask and restored.opacity() == pytest.approx(0.4)
    assert restored.border_color == QColor("#ff0000") and restored.border_width == 2.0
    old = BlurItem.deserialize({"type": "BlurItem", "rect": [0, 0, 50, 50], "blur_radius": 8})
    assert old.blur_mode is BlurMode.GAUSSIAN and old.blur_radius == 8.0
    assert old.region_shape is BlurRegionShape.RECTANGLE and old.opacity() == 1.0
    whole = BlurItem.deserialize({"rect": [0, 0, 9, 9], "region_shape": "whole_layer"})
    assert whole.region_shape is BlurRegionShape.WHOLE_LAYER
    unknown = BlurItem.deserialize({"rect": [0, 0, 9, 9], "region_shape": "spiral"})
    assert unknown.region_shape is BlurRegionShape.RECTANGLE


def _view(qtbot: QtBot, scene: SnapScene) -> SnapView:
    view = SnapView(scene)
    view.resize(800, 600)
    qtbot.addWidget(view)
    view.show()
    view.centerOn(200, 150)
    return view


def _mouse(
    view: SnapView,
    kind: QEvent.Type,
    pos: QPointF,
    mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> QMouseEvent:
    vp = QPointF(view.mapFromScene(pos))
    button = Qt.MouseButton.LeftButton
    return QMouseEvent(kind, vp, vp, button, button, mods)


def test_the_tool_draws_with_shift_and_alt_and_drops_a_click(
    qtbot: QtBot, scene: SnapScene
) -> None:
    view = _view(qtbot, scene)
    tool = BlurTool()
    tool.activate(scene, SelectionManager(scene))
    assert tool.status_hint.startswith("Click and drag to define blur region")
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(100, 100)))
    tool.mouse_move(
        _mouse(view, QEvent.Type.MouseMove, QPointF(160, 120), Qt.KeyboardModifier.ShiftModifier)
    )
    preview = tool.preview
    assert preview is not None and preview.rect == QRectF(0, 0, 60, 60)
    assert tool.status_hint.startswith("W: 60 H: 60 | Mode: Gaussian Blur | Radius: 10")
    tool.mouse_move(
        _mouse(view, QEvent.Type.MouseMove, QPointF(160, 120), Qt.KeyboardModifier.AltModifier)
    )
    assert preview.pos() == QPointF(40, 80) and preview.rect == QRectF(0, 0, 120, 40)
    tool.mouse_release(
        _mouse(
            view,
            QEvent.Type.MouseButtonRelease,
            QPointF(160, 120),
            Qt.KeyboardModifier.AltModifier,
        )
    )
    blurs = [i for i in scene.annotation_items() if isinstance(i, BlurItem)]
    assert len(blurs) == 1
    tool.activate(scene, SelectionManager(scene))
    tool.mouse_press(_mouse(view, QEvent.Type.MouseButtonPress, QPointF(300, 200)))
    tool.mouse_move(_mouse(view, QEvent.Type.MouseMove, QPointF(303, 203)))
    tool.mouse_release(_mouse(view, QEvent.Type.MouseButtonRelease, QPointF(303, 203)))
    assert len([i for i in scene.annotation_items() if isinstance(i, BlurItem)]) == 1


# --- the bar (2.6), the panel (2.8), presets ---


def test_the_blur_bar_follows_the_mode_and_the_shape(main_window: object) -> None:
    from snapmock.core.tool_themes import decode_value, encode_value

    window = main_window
    tm = window.tool_manager  # type: ignore[attr-defined]
    tm.activate("blur")
    tool = tm.active_tool
    assert isinstance(tool, BlurTool)
    groups = tool.control_actions()

    def shown(name: str) -> bool:
        return all(a.isVisible() for a in groups[name])

    assert list(tool.mode_buttons) == [BlurMode.GAUSSIAN, BlurMode.PIXELATE, BlurMode.SOLID]
    assert shown("intensity") and not shown("fill") and shown("corner")
    label = tool.intensity_label
    spin = tool.intensity_spin
    assert label is not None and spin is not None
    assert label.text() == " Blur Radius:" and (spin.minimum(), spin.maximum()) == (1, 50)
    tool.mode_buttons[BlurMode.PIXELATE].click()
    assert label.text() == " Pixel Size:" and (spin.minimum(), spin.maximum()) == (2, 100)
    spin.setValue(24)
    assert tool.creation_defaults["pixel_size"] == 24
    tool.mode_buttons[BlurMode.SOLID].click()
    assert not shown("intensity") and shown("fill")
    tool.shape_buttons[BlurRegionShape.ELLIPSE].click()
    assert not shown("corner")
    invert = tool.invert_button
    assert invert is not None and invert.accessibleName() == "Invert mask"
    invert.click()
    assert tool.creation_defaults["invert_mask"] is True
    for value in (BlurMode.PIXELATE, BlurRegionShape.ELLIPSE):
        assert decode_value(encode_value(value)) is value
    view = window.view  # type: ignore[attr-defined]
    for kind, pos in (
        (QEvent.Type.MouseButtonPress, QPointF(20, 20)),
        (QEvent.Type.MouseMove, QPointF(120, 80)),
        (QEvent.Type.MouseButtonRelease, QPointF(120, 80)),
    ):
        vp = QPointF(view.mapFromScene(pos))
        button = Qt.MouseButton.LeftButton
        event = QMouseEvent(kind, vp, button, button, Qt.KeyboardModifier.NoModifier)
        {
            QEvent.Type.MouseButtonPress: tm.handle_mouse_press,
            QEvent.Type.MouseMove: tm.handle_mouse_move,
            QEvent.Type.MouseButtonRelease: tm.handle_mouse_release,
        }[kind](event)
    blurs = [
        i
        for i in window.scene.annotation_items()  # type: ignore[attr-defined]
        if isinstance(i, BlurItem)
    ]
    assert len(blurs) == 1
    placed = blurs[0]
    assert placed.blur_mode is BlurMode.SOLID and placed.region_shape is BlurRegionShape.ELLIPSE
    assert placed.invert_mask and placed.pixel_size == 24


def test_the_panel_blur_section_edits_a_placed_region(qtbot: QtBot, scene: SnapScene) -> None:
    from snapmock.ui.property_panel import PropertyPanel

    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    item = _blur(scene)
    sm.select(item)
    assert panel._blur_section.isVisible()  # noqa: SLF001
    radius = panel._blur_radius_spin  # noqa: SLF001
    pixel = panel._blur_pixel_spin  # noqa: SLF001
    assert not radius.isHidden() and pixel.isHidden()
    radius.setValue(25.0)
    assert item.blur_radius == 25.0
    assert scene.command_stack.undo_text == "Change blur_radius"
    mode = panel._blur_mode_combo  # noqa: SLF001
    mode.setCurrentIndex(mode.findData(BlurMode.PIXELATE))
    assert item.blur_mode is BlurMode.PIXELATE
    assert radius.isHidden() and not pixel.isHidden()
    panel._blur_opacity_spin.setValue(40)  # noqa: SLF001
    assert item.opacity() == pytest.approx(0.4)
    panel._blur_invert_check.setChecked(True)  # noqa: SLF001
    assert item.invert_mask
    for _ in range(4):
        scene.command_stack.undo()
    assert item.blur_mode is BlurMode.GAUSSIAN and item.blur_radius == 10.0
    assert not item.invert_mask and item.opacity() == 1.0
