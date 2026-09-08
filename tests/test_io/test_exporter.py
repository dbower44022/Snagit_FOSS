"""Tests for export functions."""

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from snapmock.core.scene import SnapScene
from snapmock.io.exporter import export_jpg, export_png, fit_to_page, print_scene


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


def test_export_png(scene: SnapScene, tmp_path: Path) -> None:
    path = tmp_path / "test.png"
    export_png(scene, path)
    assert path.exists()
    assert path.stat().st_size > 0


def test_export_jpg(scene: SnapScene, tmp_path: Path) -> None:
    path = tmp_path / "test.jpg"
    export_jpg(scene, path)
    assert path.exists()
    assert path.stat().st_size > 0


def test_fit_to_page_keeps_aspect_and_centres() -> None:
    from PyQt6.QtCore import QRectF, QSizeF

    # Landscape canvas on a portrait page: width-limited, centred vertically.
    target = fit_to_page(QSizeF(1920, 1080), QRectF(0, 0, 800, 1000))
    assert target.width() == pytest.approx(800)
    assert target.height() == pytest.approx(450)
    assert target.top() == pytest.approx(275)
    # Portrait canvas on the same page: height-limited, centred horizontally.
    target = fit_to_page(QSizeF(500, 1000), QRectF(0, 0, 800, 1000))
    assert target.height() == pytest.approx(1000)
    assert target.left() == pytest.approx(150)
    # Page offset is honoured.
    target = fit_to_page(QSizeF(100, 100), QRectF(50, 60, 200, 100))
    assert (target.left(), target.top(), target.width()) == (100, 60, 100)
    assert fit_to_page(QSizeF(0, 0), QRectF(0, 0, 10, 10)).isNull()


def test_print_scene_paints_the_flattened_canvas(scene: SnapScene) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QImage

    scene.set_background_color(QColor("red"))
    page = QImage(400, 400, QImage.Format.Format_ARGB32)
    page.fill(QColor("white"))
    target = print_scene(scene, page)
    assert target == fit_to_page(scene.canvas_size, QRectF(0, 0, 400, 400))
    inside = page.pixelColor(200, 200)
    assert inside == QColor("red")
    assert page.pixelColor(200, 5) == QColor("white")
