"""Tests for SnapScene and SnapView."""

from PyQt6.QtCore import QSizeF

from snapmock.config.constants import DEFAULT_CANVAS_HEIGHT, DEFAULT_CANVAS_WIDTH, ZOOM_MIN
from snapmock.core.scene import SnapScene
from snapmock.core.view import SnapView


def test_scene_default_canvas_size(scene: SnapScene) -> None:
    assert scene.canvas_size.width() == DEFAULT_CANVAS_WIDTH
    assert scene.canvas_size.height() == DEFAULT_CANVAS_HEIGHT


def test_scene_custom_canvas_size() -> None:
    s = SnapScene(width=800, height=600)
    assert s.canvas_size == QSizeF(800, 600)


def test_scene_has_default_layer(scene: SnapScene) -> None:
    assert scene.layer_manager.count == 1
    assert scene.layer_manager.active_layer is not None


def test_scene_has_command_stack(scene: SnapScene) -> None:
    assert scene.command_stack is not None
    assert not scene.command_stack.can_undo


def test_scene_resize_canvas(scene: SnapScene) -> None:
    scene.set_canvas_size(QSizeF(1000, 500))
    assert scene.canvas_size == QSizeF(1000, 500)
    assert scene.sceneRect().width() == 1000


def test_view_default_zoom(view: SnapView) -> None:
    assert view.zoom_percent == 100


def test_view_zoom_clamps(view: SnapView) -> None:
    view.set_zoom(5)
    assert view.zoom_percent == ZOOM_MIN
