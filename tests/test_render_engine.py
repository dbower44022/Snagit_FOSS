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
