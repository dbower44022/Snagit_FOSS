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
    This class is for file export and raster pixel operations.
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

    def render_region(
        self,
        rect: QRectF,
        background: QColor | None = None,
    ) -> QImage:
        """Render a specific rectangular region of the scene to a QImage."""
        w = max(1, int(rect.width()))
        h = max(1, int(rect.height()))

        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        if background is not None:
            image.fill(background)
        else:
            image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._scene.render(
            painter,
            target=QRectF(0, 0, w, h),
            source=rect,
        )
        painter.end()
        return image

    def render_layer_region(
        self,
        layer_id: str,
        rect: QRectF,
    ) -> QImage:
        """Render only items on *layer_id* within *rect* to a QImage."""
        from snapmock.items.base_item import SnapGraphicsItem

        w = max(1, int(rect.width()))
        h = max(1, int(rect.height()))

        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        # Temporarily hide items not on the target layer
        hidden_items: list[SnapGraphicsItem] = []
        for gitem in self._scene.items():
            if isinstance(gitem, SnapGraphicsItem) and gitem.layer_id != layer_id:
                if gitem.isVisible():
                    gitem.setVisible(False)
                    hidden_items.append(gitem)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._scene.render(
            painter,
            target=QRectF(0, 0, w, h),
            source=rect,
        )
        painter.end()

        # Restore visibility
        for gitem in hidden_items:
            gitem.setVisible(True)

        return image
