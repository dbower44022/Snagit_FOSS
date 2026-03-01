"""ClipboardManager — internal and system clipboard operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QMimeData, QObject, QRectF, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.items.base_item import SnapGraphicsItem

INTERNAL_MIME = "application/x-snapmock-items"


class ClipboardManager(QObject):
    """Handles copy/paste of items within SnapMock and to the system clipboard.

    Signals
    -------
    clipboard_changed()
        Emitted when the internal clipboard content changes.
    """

    clipboard_changed = pyqtSignal()

    def __init__(self, scene: SnapScene, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._scene = scene
        self._internal_data: list[dict[str, Any]] = []
        self._raster_data: QImage | None = None
        self._raster_source_rect: QRectF | None = None

    @property
    def has_internal(self) -> bool:
        return len(self._internal_data) > 0

    def copy_items(self, items: list[SnapGraphicsItem]) -> None:
        """Serialize items to the internal clipboard and put a PNG on the system clipboard."""
        if not items:
            return
        self._internal_data = [item.serialize() for item in items]

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            mime = QMimeData()
            mime.setData(INTERNAL_MIME, json.dumps(self._internal_data).encode())

            # Also render selected items to PNG for system clipboard
            image = self._render_items_to_image(items)
            if image is not None and not image.isNull():
                mime.setImageData(image)

            clipboard.setMimeData(mime)
        self.clipboard_changed.emit()

    def _render_items_to_image(self, items: list[SnapGraphicsItem]) -> QImage | None:
        """Render the given items to a QImage."""
        if not items:
            return None
        # Compute bounding rect of all items
        rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        if rect.isEmpty():
            return None

        w = max(1, int(rect.width()))
        h = max(1, int(rect.height()))
        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        from PyQt6.QtCore import Qt

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

    def paste_items(self) -> list[dict[str, Any]]:
        """Return serialized item data from the internal clipboard."""
        return list(self._internal_data)

    def paste_image_from_system(self) -> QImage | None:
        """If the system clipboard has an image, return it."""
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return None
        image = clipboard.image()
        if image is not None and not image.isNull():
            return image
        return None

    # --- raster clipboard ---

    @property
    def has_raster(self) -> bool:
        return self._raster_data is not None

    def copy_raster_region(self, image: QImage, source_rect: QRectF) -> None:
        """Store a raster region and put PNG on the system clipboard."""
        self._raster_data = QImage(image)
        self._raster_source_rect = QRectF(source_rect)
        # Clear internal item data (raster takes priority)
        self._internal_data.clear()

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setImage(image)
        self.clipboard_changed.emit()

    def paste_raster(self) -> tuple[QImage | None, QRectF | None]:
        """Return stored raster data and its source rect."""
        if self._raster_data is not None:
            src = QRectF(self._raster_source_rect) if self._raster_source_rect else None
            return QImage(self._raster_data), src
        return None, None

    def clear(self) -> None:
        self._internal_data.clear()
        self._raster_data = None
        self._raster_source_rect = None
        self.clipboard_changed.emit()
