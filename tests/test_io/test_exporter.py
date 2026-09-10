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


# --- Export dialog engine (General UI PRD 11.2) ---


def _png_header_depth(path: Path) -> int:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return data[24]  # IHDR bit depth


def test_export_settings_round_trip_and_tolerant_load() -> None:
    from snapmock.io.exporter import ExportFormat, ExportRegion, ExportSettings, PdfPageSize

    settings = ExportSettings(
        format=ExportFormat.PDF,
        region=ExportRegion.SELECTION,
        dpi=300,
        png_transparency=False,
        png_color_depth=16,
        jpeg_quality=55,
        svg_embed_raster=False,
        pdf_page_size=PdfPageSize.A4,
    )
    assert ExportSettings.from_dict(settings.to_dict()) == settings
    loaded = ExportSettings.from_dict(
        {"format": "bogus", "dpi": "not a number", "png_color_depth": 12, "jpeg_quality": 500}
    )
    assert loaded.format is ExportFormat.PNG
    assert loaded.dpi == 72
    assert loaded.png_color_depth == 8
    assert loaded.jpeg_quality == 100
    assert ExportFormat.from_suffix(".JPEG") is ExportFormat.JPEG
    assert ExportFormat.from_suffix(".txt") is None


def test_resolve_region_clips_to_canvas_and_falls_back(scene: SnapScene) -> None:
    from PyQt6.QtCore import QRectF

    from snapmock.io.exporter import ExportRegion, resolve_region

    canvas = scene.canvas_rect
    assert resolve_region(scene, ExportRegion.CANVAS) == canvas
    sel = QRectF(300, 200, 400, 400)
    assert resolve_region(scene, ExportRegion.SELECTION, selection=sel) == QRectF(
        300, 200, 100, 100
    )
    assert resolve_region(scene, ExportRegion.SELECTION, selection=None) == canvas
    assert resolve_region(scene, ExportRegion.VISIBLE, visible=QRectF(900, 900, 5, 5)) == canvas


def test_selection_rect_unites_items(scene: SnapScene) -> None:
    from PyQt6.QtCore import QPointF, QRectF

    from snapmock.io.exporter import selection_rect
    from snapmock.items.rectangle_item import RectangleItem

    a = RectangleItem(QRectF(0, 0, 10, 10))
    a.setPos(QPointF(10, 10))
    b = RectangleItem(QRectF(0, 0, 10, 10))
    b.setPos(QPointF(50, 60))
    scene.addItem(a)
    scene.addItem(b)
    united = selection_rect([a, b])
    assert united.contains(QRectF(10, 10, 50, 60))
    assert selection_rect([]).isNull()


def test_export_png_dpi_depth_and_transparency(scene: SnapScene, tmp_path: Path) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QImage

    from snapmock.io.exporter import ExportFormat, ExportSettings, export_scene

    scene.set_background_color(QColor(0, 0, 0, 0))
    region = QRectF(0, 0, 100, 50)
    settings = ExportSettings(format=ExportFormat.PNG, dpi=144, png_color_depth=16)
    out = tmp_path / "a.png"
    export_scene(scene, out, settings, region)
    image = QImage(str(out))
    assert (image.width(), image.height()) == (200, 100)
    assert image.dotsPerMeterX() == round(144 * 39.3701)
    assert _png_header_depth(out) == 16
    assert image.pixelColor(5, 5).alpha() == 0

    opaque = ExportSettings(format=ExportFormat.PNG, png_transparency=False)
    out2 = tmp_path / "b.png"
    export_scene(scene, out2, opaque, region)
    image2 = QImage(str(out2))
    assert _png_header_depth(out2) == 8
    assert image2.pixelColor(5, 5) == QColor("white")


def test_export_jpeg_quality_changes_size(scene: SnapScene, tmp_path: Path) -> None:
    from PyQt6.QtCore import QPointF, QRectF
    from PyQt6.QtGui import QColor

    from snapmock.io.exporter import (
        ExportFormat,
        ExportSettings,
        estimate_export_size,
        export_scene,
    )
    from snapmock.items.ellipse_item import EllipseItem

    for i in range(6):
        item = EllipseItem(QRectF(0, 0, 90, 70))
        item.setPos(QPointF(20 * i, 30 * i))
        item.stroke_color = QColor(40 * i, 200 - 30 * i, 90)
        scene.addItem(item)
    high = ExportSettings(format=ExportFormat.JPEG, jpeg_quality=95)
    low = ExportSettings(format=ExportFormat.JPEG, jpeg_quality=10)
    export_scene(scene, tmp_path / "h.jpg", high)
    export_scene(scene, tmp_path / "l.jpg", low)
    assert (tmp_path / "h.jpg").stat().st_size > (tmp_path / "l.jpg").stat().st_size
    assert estimate_export_size(scene, high) == (tmp_path / "h.jpg").stat().st_size


def test_export_svg_viewbox_and_raster_embedding(scene: SnapScene, tmp_path: Path) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QPixmap

    from snapmock.io.exporter import ExportFormat, ExportSettings, export_scene
    from snapmock.items.raster_region_item import RasterRegionItem

    pixmap = QPixmap(20, 20)
    pixmap.fill(QColor("blue"))
    scene.addItem(RasterRegionItem(pixmap))
    region = QRectF(0, 0, 120, 80)
    export_scene(scene, tmp_path / "e.svg", ExportSettings(format=ExportFormat.SVG), region)
    embedded = (tmp_path / "e.svg").read_text()
    assert 'viewBox="0 0 120 80"' in embedded
    assert "<image" in embedded
    export_scene(
        scene,
        tmp_path / "v.svg",
        ExportSettings(format=ExportFormat.SVG, svg_embed_raster=False),
        region,
    )
    assert "<image" not in (tmp_path / "v.svg").read_text()
    assert scene.items()[0].isVisible()


def test_export_pdf_page_sizes(scene: SnapScene, tmp_path: Path) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QPageLayout

    from snapmock.io.exporter import (
        ExportFormat,
        ExportSettings,
        PdfPageSize,
        estimate_export_size,
        export_scene,
        pdf_page_layout,
    )

    wide = QRectF(0, 0, 400, 300)
    canvas_layout = pdf_page_layout(ExportSettings(format=ExportFormat.PDF), wide)
    size = canvas_layout.pageSize().size(canvas_layout.pageSize().Unit.Point)
    assert (round(size.width()), round(size.height())) == (400, 300)
    a4 = pdf_page_layout(
        ExportSettings(format=ExportFormat.PDF, pdf_page_size=PdfPageSize.A4), wide
    )
    assert a4.orientation() == QPageLayout.Orientation.Landscape
    tall = QRectF(0, 0, 300, 400)
    letter = pdf_page_layout(
        ExportSettings(format=ExportFormat.PDF, pdf_page_size=PdfPageSize.LETTER), tall
    )
    assert letter.orientation() == QPageLayout.Orientation.Portrait
    assert letter.pageSize().id() == letter.pageSize().PageSizeId.Letter

    out = tmp_path / "p.pdf"
    export_scene(scene, out, ExportSettings(format=ExportFormat.PDF, pdf_page_size=PdfPageSize.A4))
    assert out.read_bytes()[:5] == b"%PDF-"
    assert estimate_export_size(scene, ExportSettings(format=ExportFormat.PDF)) > 0


def test_export_smk_copies_the_project_file(scene: SnapScene, tmp_path: Path) -> None:
    from snapmock.io.exporter import (
        ExportFormat,
        ExportSettings,
        estimate_export_size,
        export_scene,
    )

    source = tmp_path / "source.smk"
    source.write_bytes(b"not really a zip")
    settings = ExportSettings(format=ExportFormat.SMK)
    export_scene(scene, tmp_path / "copy.smk", settings, source_file=source)
    assert (tmp_path / "copy.smk").read_bytes() == b"not really a zip"
    assert estimate_export_size(scene, settings, source_file=source) == len(b"not really a zip")
    with pytest.raises(ValueError):
        export_scene(scene, tmp_path / "x.smk", settings)


def test_format_byte_size() -> None:
    from snapmock.io.exporter import format_byte_size

    assert format_byte_size(512) == "512 B"
    assert format_byte_size(2048) == "2.0 KB"
    assert format_byte_size(150 * 1024) == "150 KB"
    assert format_byte_size(3 * 1024 * 1024) == "3.0 MB"


def test_app_settings_remember_export_settings_per_format() -> None:
    from snapmock.config.settings import AppSettings
    from snapmock.io.exporter import ExportFormat, ExportSettings

    settings = AppSettings()
    assert settings.export_settings("png") is None
    assert settings.export_last_directory("png") is None
    assert settings.export_last_format() == "png"
    saved = ExportSettings(format=ExportFormat.JPEG, jpeg_quality=42)
    settings.set_export_settings("jpeg", saved.to_dict())
    settings.set_export_last_directory("jpeg", Path("/tmp/out"))
    settings.set_export_last_format("jpeg")
    stored = settings.export_settings("jpeg")
    assert stored is not None
    assert ExportSettings.from_dict(stored) == saved
    assert settings.export_last_directory("jpeg") == Path("/tmp/out")
    assert settings.export_last_format() == "jpeg"


# ---- the layer blend mode in every export (follow-up step 3, decision 3) ----


def _multiply_scene(scene: SnapScene) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor

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


def test_png_and_jpeg_exports_carry_the_blend_mode(scene: SnapScene, tmp_path: Path) -> None:
    from PyQt6.QtGui import QColor, QImage

    from snapmock.io.exporter import ExportFormat, ExportSettings, export_scene

    _multiply_scene(scene)
    export_scene(scene, tmp_path / "m.png", ExportSettings(format=ExportFormat.PNG))
    png = QImage(str(tmp_path / "m.png"))
    assert png.pixelColor(100, 100) == QColor("black")
    assert png.pixelColor(10, 10) == QColor("blue")
    export_scene(scene, tmp_path / "m.jpg", ExportSettings(format=ExportFormat.JPEG))
    jpg = QImage(str(tmp_path / "m.jpg"))
    dark = jpg.pixelColor(100, 100)
    assert max(dark.red(), dark.green(), dark.blue()) < 40


def test_pdf_export_paints_the_canvas_and_draws_a_blended_layer_as_normal(
    scene: SnapScene, tmp_path: Path
) -> None:
    """Qt's PDF engine writes no blend mode (Technical Architecture PRD 1.15 row); the page
    carries the canvas colour, which the PDF export did not paint before this work."""
    import shutil
    import subprocess

    from PyQt6.QtGui import QImage

    from snapmock.io.exporter import ExportFormat, ExportSettings, export_scene

    if shutil.which("pdftoppm") is None:
        pytest.skip("pdftoppm is not installed")
    _multiply_scene(scene)
    out = tmp_path / "m.pdf"
    export_scene(scene, out, ExportSettings(format=ExportFormat.PDF, dpi=72))
    assert b"/BM" not in out.read_bytes()
    subprocess.run(
        ["pdftoppm", "-png", "-r", "72", "-singlefile", str(out), str(tmp_path / "page")],
        check=True,
    )
    page = QImage(str(tmp_path / "page.png"))
    assert (page.width(), page.height()) == (400, 300)
    blue = page.pixelColor(10, 10)
    assert blue.blue() > 200 and blue.red() < 40 and blue.green() < 40
    yellow = page.pixelColor(100, 100)
    assert yellow.red() > 200 and yellow.green() > 200 and yellow.blue() < 40


def test_svg_export_draws_a_blended_layer_as_normal(scene: SnapScene, tmp_path: Path) -> None:
    """Qt's SVG generator carries no composition mode (Technical Architecture PRD 1.15 row)."""
    from snapmock.io.exporter import ExportFormat, ExportSettings, export_scene

    _multiply_scene(scene)
    out = tmp_path / "m.svg"
    export_scene(scene, out, ExportSettings(format=ExportFormat.SVG))
    text = out.read_text().lower()
    assert "#ffff00" in text
    assert "multiply" not in text
    # The canvas colour is painted first, as a rectangle the size of the canvas
    assert 'fill="#0000ff"' in text and '<rect x="0" y="0" width="400" height="300"/>' in text
