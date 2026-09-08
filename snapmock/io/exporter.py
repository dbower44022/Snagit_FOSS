"""Exporter — export scene to PNG, JPG, SVG, PDF, and print the flattened canvas."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QMarginsF, QRectF, QSize, QSizeF
from PyQt6.QtGui import QColor, QPageLayout, QPageSize, QPaintDevice, QPainter

from snapmock.core.render_engine import RenderEngine

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


def export_png(scene: SnapScene, path: Path, background: QColor | None = None) -> None:
    """Export the scene to a PNG file."""
    engine = RenderEngine(scene)
    img = engine.render_to_image(background=background)
    img.save(str(path), "PNG")


def export_jpg(
    scene: SnapScene, path: Path, quality: int = 90, background: QColor | None = None
) -> None:
    """Export the scene to a JPG file."""
    engine = RenderEngine(scene)
    bg = background if background is not None else QColor("white")
    img = engine.render_to_image(background=bg)
    img.save(str(path), "JPEG", quality)


def export_pdf(scene: SnapScene, path: Path) -> None:
    """Export the scene to a PDF file."""
    from PyQt6.QtPrintSupport import QPrinter

    canvas = scene.canvas_size
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    page_size = QPageSize(QSize(int(canvas.width()), int(canvas.height())))
    printer.setPageLayout(
        QPageLayout(page_size, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0))
    )
    painter = QPainter(printer)
    scene.render(
        painter,
        target=QRectF(0, 0, painter.device().width(), painter.device().height()),  # type: ignore[union-attr]
        source=QRectF(0, 0, canvas.width(), canvas.height()),
    )
    painter.end()


def export_svg(scene: SnapScene, path: Path) -> None:
    """Export the scene to an SVG file using QSvgGenerator."""
    from PyQt6.QtCore import QSize
    from PyQt6.QtSvg import QSvgGenerator

    canvas = scene.canvas_size
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(QSize(int(canvas.width()), int(canvas.height())))
    generator.setViewBox(QRectF(0, 0, canvas.width(), canvas.height()))
    painter = QPainter(generator)
    scene.render(
        painter,
        target=QRectF(0, 0, canvas.width(), canvas.height()),
        source=QRectF(0, 0, canvas.width(), canvas.height()),
    )
    painter.end()


def fit_to_page(content: QSizeF, page: QRectF) -> QRectF:
    """The largest rectangle of *content*'s aspect ratio centred inside *page* (PRD 3.1 Print)."""
    if content.width() <= 0 or content.height() <= 0 or page.isEmpty():
        return QRectF()
    scale = min(page.width() / content.width(), page.height() / content.height())
    w = content.width() * scale
    h = content.height() * scale
    return QRectF(page.left() + (page.width() - w) / 2, page.top() + (page.height() - h) / 2, w, h)


def print_scene(scene: SnapScene, device: QPaintDevice, page: QRectF | None = None) -> QRectF:
    """Paint the flattened canvas onto a printer or any paint device, scaled to fit the page.

    Returns the rectangle the canvas was painted into, in device pixels.
    """
    engine = RenderEngine(scene)
    image = engine.render_to_image(background=scene.background_color)
    target_page = page if page is not None else QRectF(0, 0, device.width(), device.height())
    target = fit_to_page(QSizeF(image.size()), target_page)
    painter = QPainter(device)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage(target, image)
    painter.end()
    return target
