"""RenderEngine — layer compositing for display and export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene


class RenderEngine:
    """Composites visible layers into a final QImage for export.

    For on-screen rendering, QGraphicsView handles it directly.
    This class is for file export.
    """

    def __init__(self, scene: SnapScene) -> None:
        self._scene = scene

    def render_to_image(
        self,
        width: int | None = None,
        height: int | None = None,
        background: QColor | None = None,
    ) -> QImage:
        """Render the full scene to a QImage.

        If *width*/*height* are not specified, uses the canvas size.
        """
        canvas = self._scene.canvas_size
        w = width if width is not None else int(canvas.width())
        h = height if height is not None else int(canvas.height())

        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        if background is not None:
            image.fill(background)
        else:
            image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._scene.render(
            painter,
            target=QRectF(0, 0, w, h),
            source=QRectF(0, 0, canvas.width(), canvas.height()),
        )
        painter.end()
        return image
