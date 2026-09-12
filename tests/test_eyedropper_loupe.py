"""The Eyedropper's preview loupe (Blur PRD 4.3).

Decision 1 of the Eyedropper and Blur performance work, option B: the loupe is a widget
over the canvas view's viewport, so its geometry is screen-pixel arithmetic on the viewport
rectangle and it can never reach a render of the scene.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.render_engine import RenderEngine
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.theme_manager import current_theme
from snapmock.core.view import SnapView
from snapmock.items.rectangle_item import RectangleItem
from snapmock.tools.eyedropper_tool import EyedropperTool
from snapmock.ui.loupe_overlay import (
    LOUPE_CAPTURE_SIDE,
    LOUPE_DIAMETER,
    LOUPE_MAGNIFICATION,
    LOUPE_SWATCH_HEIGHT,
    LoupeOverlay,
    circle_rect,
    loupe_position,
    loupe_size,
    swatch_rect,
)

VIEWPORT = QRect(0, 0, 800, 600)


@pytest.fixture()
def canvas(qapp: QApplication) -> tuple[SnapScene, SnapView, EyedropperTool]:
    """A white canvas with a red square, a view, and the tool active on it."""
    scene = SnapScene(width=400, height=300)
    scene.set_background_color(QColor("#FFFFFF"))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(QRectF(0, 0, 200, 200))
    item.setPos(QPointF(100, 50))
    item.fill_color = QColor("#FF0000")
    item.stroke_width = 0
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    view = SnapView(scene)
    view.resize(800, 600)
    tool = EyedropperTool()
    tool.activate(scene, SelectionManager(scene))
    return scene, view, tool


# ---- geometry (4.3) ----


def test_the_loupe_is_a_120_px_circle_at_8_times_magnification() -> None:
    assert LOUPE_DIAMETER == 120  # noqa: PLR2004
    assert LOUPE_MAGNIFICATION == 8  # noqa: PLR2004
    assert LOUPE_CAPTURE_SIDE == 15  # noqa: PLR2004
    width, height = loupe_size()
    assert width >= LOUPE_DIAMETER
    assert height >= LOUPE_DIAMETER + LOUPE_SWATCH_HEIGHT


def test_the_loupe_sits_above_and_right_of_the_cursor() -> None:
    width, height = loupe_size()
    at = loupe_position(QPoint(400, 400), VIEWPORT)
    assert at.x() == 420  # noqa: PLR2004
    assert at.y() == 400 - 20 - height


def test_the_loupe_flips_rather_than_leaving_the_viewport() -> None:
    width, height = loupe_size()
    # Near the right edge it goes to the left of the cursor.
    right = loupe_position(QPoint(790, 400), VIEWPORT)
    assert right.x() == 790 - 20 - width
    # Near the top it goes below the cursor.
    top = loupe_position(QPoint(400, 10), VIEWPORT)
    assert top.y() == 30  # noqa: PLR2004
    # In a corner it stays wholly inside the viewport either way.
    corner = loupe_position(QPoint(5, 5), VIEWPORT)
    assert corner.x() >= 0
    assert corner.y() >= 0
    assert corner.x() + width <= VIEWPORT.width()
    assert corner.y() + height <= VIEWPORT.height()
    # A viewport smaller than the loupe clamps to its top-left rather than going negative.
    tiny = loupe_position(QPoint(10, 10), QRect(0, 0, 60, 60))
    assert tiny == QPoint(0, 0)


# ---- what it shows ----


def _shown(tool: EyedropperTool, view: SnapView, scene_pos: QPointF) -> LoupeOverlay:
    tool.update_loupe(view.mapFromScene(scene_pos))
    loupe = tool.loupe
    assert loupe is not None
    assert not loupe.isHidden()
    return loupe


def test_the_magnified_content_is_what_would_be_sampled(
    canvas: tuple[SnapScene, SnapView, EyedropperTool],
) -> None:
    """The loupe magnifies the Eyedropper's own capture, so the two cannot disagree."""
    scene, view, tool = canvas
    loupe = _shown(tool, view, QPointF(150, 100))
    image = loupe.sampled_image
    assert image is not None
    assert image.width() == LOUPE_CAPTURE_SIDE
    assert image.height() == LOUPE_CAPTURE_SIDE
    centre = LOUPE_CAPTURE_SIDE // 2
    assert image.pixelColor(centre, centre) == QColor("#FF0000")
    assert loupe.sampled_color == tool.sample_at(QPointF(150, 100))
    assert loupe.sampled_color == QColor("#FF0000")
    # The magnified block of one canvas pixel is 8 by 8 screen pixels.
    assert image.width() * LOUPE_MAGNIFICATION == LOUPE_DIAMETER


def test_the_outline_follows_the_sample_size(
    canvas: tuple[SnapScene, SnapView, EyedropperTool],
) -> None:
    scene, view, tool = canvas
    tool.creation_defaults["sample_size"] = 11
    loupe = _shown(tool, view, QPointF(150, 100))
    assert loupe.sample_size == 11  # noqa: PLR2004
    assert loupe.sampled_color == QColor("#FF0000")  # the whole area is inside the square


def _painted(loupe: LoupeOverlay) -> QImage:
    pixmap = QPixmap(loupe.size())
    pixmap.fill(Qt.GlobalColor.transparent)
    loupe.render(pixmap)
    return pixmap.toImage()


def test_the_swatch_and_the_hex_value_show_the_sampled_colour(
    canvas: tuple[SnapScene, SnapView, EyedropperTool],
) -> None:
    scene, view, tool = canvas
    loupe = _shown(tool, view, QPointF(150, 100))
    assert loupe.value_text() == "#FF0000"
    painted = _painted(loupe)
    # The magnified content and the swatch below it are both the sampled colour. The very
    # centre of the circle is the crosshair, so the content is read a little above it.
    circle = circle_rect()
    assert painted.pixelColor(int(circle.center().x()), int(circle.top()) + 25) == QColor(
        "#FF0000"
    )
    swatch = swatch_rect()
    assert painted.pixelColor(swatch.center().x(), swatch.center().y()) == QColor("#FF0000")


def test_over_transparent_canvas_the_swatch_is_the_checkerboard(
    canvas: tuple[SnapScene, SnapView, EyedropperTool],
) -> None:
    """4.3: the loupe shows the transparency pattern and the swatch reads "transparent"."""
    scene, view, tool = canvas
    scene.set_background_color(QColor(0, 0, 0, 0))
    loupe = _shown(tool, view, QPointF(20, 20))
    assert loupe.sampled_color.alpha() == 0
    assert loupe.value_text() == "transparent"
    painted = _painted(loupe)
    theme = current_theme()
    swatch = swatch_rect()
    assert painted.pixelColor(swatch.left() + 2, swatch.top() + 2) in (
        theme.checkerboard_a,
        theme.checkerboard_b,
    )
    circle = circle_rect()
    assert painted.pixelColor(int(circle.center().x()), int(circle.top()) + 25) in (
        theme.checkerboard_a,
        theme.checkerboard_b,
    )


# ---- lifetime ----


def test_the_loupe_follows_a_hover_and_hides_on_leave(
    canvas: tuple[SnapScene, SnapView, EyedropperTool],
) -> None:
    scene, view, tool = canvas
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(view.mapFromScene(QPointF(150, 100))),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # A hover with no button down shows the loupe and is not consumed as a drag.
    assert not tool.mouse_move(move)
    loupe = tool.loupe
    assert loupe is not None and not loupe.isHidden()
    viewport = view.viewport()
    assert viewport is not None
    QApplication.sendEvent(viewport, QEvent(QEvent.Type.Leave))
    assert loupe.isHidden()


def test_the_loupe_hides_when_the_tool_goes_away(
    canvas: tuple[SnapScene, SnapView, EyedropperTool],
) -> None:
    scene, view, tool = canvas
    loupe = _shown(tool, view, QPointF(150, 100))
    tool.cancel()
    assert loupe.isHidden()
    _shown(tool, view, QPointF(150, 100))
    tool.deactivate()
    assert loupe.isHidden()


def test_the_loupe_never_reaches_a_render_of_the_scene(
    canvas: tuple[SnapScene, SnapView, EyedropperTool],
) -> None:
    """4.3: the loupe is an overlay on the viewport, not a scene item."""
    scene, view, tool = canvas
    before = len(scene.items())
    loupe = _shown(tool, view, QPointF(150, 100))
    assert len(scene.items()) == before
    assert loupe.parentWidget() is view.viewport()
    export = RenderEngine(scene).render_to_image()
    assert export.pixelColor(150, 100) == QColor("#FF0000")
    assert export.pixelColor(20, 20) == QColor("#FFFFFF")  # where the loupe was drawn
