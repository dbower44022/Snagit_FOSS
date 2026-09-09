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
        scale: float = 1.0,
    ) -> QImage:
        """Render a specific rectangular region of the scene to a QImage.

        *scale* multiplies the output size: 2.0 renders *rect* at twice its
        scene dimensions (an export at 144 DPI when the scene is 72 DPI).
        """
        w = max(1, round(rect.width() * scale))
        h = max(1, round(rect.height() * scale))

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
        scale: float = 1.0,
    ) -> QImage:
        """Render only items on *layer_id* within *rect* to a QImage.

        *scale* multiplies the output size, as in :meth:`render_region`. Items
        on the layer are drawn even when the layer is hidden, so a Layer Panel
        thumbnail shows what the layer holds.
        """
        from snapmock.items.base_item import SnapGraphicsItem

        w = max(1, round(rect.width() * scale))
        h = max(1, round(rect.height() * scale))

        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        # Temporarily hide items not on the target layer, and show the target's
        hidden_items: list[SnapGraphicsItem] = []
        shown_items: list[SnapGraphicsItem] = []
        for gitem in self._scene.items():
            if not isinstance(gitem, SnapGraphicsItem):
                continue
            if gitem.layer_id != layer_id:
                if gitem.isVisible():
                    gitem.setVisible(False)
                    hidden_items.append(gitem)
            elif not gitem.isVisible():
                gitem.setVisible(True)
                shown_items.append(gitem)

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
        for gitem in shown_items:
            gitem.setVisible(False)

        return image
