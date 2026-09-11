"""Shadow helper — the five shadow properties and their painting, shared by the marker items.

Numbered Steps, Stamps & Emoji PRD Sections 2.4, 3.5, and 4.4 give the numbered step, the
stamp, and the emoji a drop shadow; implementation decision 1 (option B) builds it once
here and mixes it into those three items. The shadow is an offset, blurred copy of the
item's shape painted inside the item's own ``paint``, never a Qt graphics effect, so the
display, the raster exports, the layer thumbnails, and the clipboard agree. The blurred
copy is rendered into an image at the painter's current scale and cached until the shape,
the colour, the blur, or the scale changes.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath

from snapmock.config.constants import (
    DEFAULT_SHADOW_BLUR,
    DEFAULT_SHADOW_COLOR,
    DEFAULT_SHADOW_OFFSET,
)

SHADOW_KEYS: tuple[str, ...] = (
    "shadow_enabled",
    "shadow_color",
    "shadow_offset_x",
    "shadow_offset_y",
    "shadow_blur",
)
"""The five properties, in the order the PRD lists them; also the serialization keys."""

_MAX_SHADOW_IMAGE = 4096
"""Longest side of a cached shadow image, so a huge zoom does not allocate without bound."""


def _box_blur(channel: np.ndarray, radius: int) -> np.ndarray:
    """One horizontal-and-vertical box blur of *radius* over a float array."""
    if radius <= 0:
        return channel
    size = 2 * radius + 1
    padded = np.pad(channel, ((radius, radius), (radius, radius)), mode="constant")
    summed = np.cumsum(padded, axis=0)
    summed = np.vstack([np.zeros((1, summed.shape[1])), summed])
    vertical = (summed[size:, :] - summed[:-size, :]) / size
    summed = np.cumsum(vertical, axis=1)
    summed = np.hstack([np.zeros((summed.shape[0], 1)), summed])
    result: np.ndarray = (summed[:, size:] - summed[:, :-size]) / size
    return result


def blur_image(image: QImage, radius: float) -> QImage:
    """*image* (ARGB32 premultiplied) blurred by three box passes, a close Gaussian.

    *radius* is in the image's pixels. A radius under half a pixel returns a copy.
    """
    if radius < 0.5 or image.isNull():
        return image.copy()
    box = max(1, int(round(radius / 1.7)))
    width, height = image.width(), image.height()
    image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    pointer = image.bits()
    if pointer is None:
        return image.copy()
    pointer.setsize(image.sizeInBytes())
    stride = image.bytesPerLine()
    buffer = pointer.asstring(image.sizeInBytes())
    raw = np.frombuffer(buffer, dtype=np.uint8).reshape(height, stride)[:, : width * 4]
    pixels = raw.reshape(height, width, 4).astype(np.float64)
    for channel in range(4):
        plane = pixels[:, :, channel]
        for _pass in range(3):
            plane = _box_blur(plane, box)
        pixels[:, :, channel] = plane
    out = np.clip(np.rint(pixels), 0, 255).astype(np.uint8)
    result = QImage(
        out.tobytes(), width, height, width * 4, QImage.Format.Format_ARGB32_Premultiplied
    )
    return result.copy()


class ShadowMixin:
    """The shadow properties, their keys, and the painting.

    A class mixes this in ahead of its item base class and calls :meth:`_init_shadow`
    from ``__init__``. ``prepareGeometryChange`` and ``update`` are the item's.
    """

    _shadow_enabled: bool
    _shadow_color: QColor
    _shadow_offset_x: float
    _shadow_offset_y: float
    _shadow_blur: float
    _shadow_cache_key: tuple[Any, ...] | None
    _shadow_cache_image: QImage | None
    _shadow_cache_rect: QRectF

    def _init_shadow(self, enabled: bool = False) -> None:
        self._shadow_enabled = enabled
        self._shadow_color = QColor(DEFAULT_SHADOW_COLOR)
        self._shadow_offset_x = DEFAULT_SHADOW_OFFSET
        self._shadow_offset_y = DEFAULT_SHADOW_OFFSET
        self._shadow_blur = DEFAULT_SHADOW_BLUR
        self._shadow_cache_key = None
        self._shadow_cache_image = None
        self._shadow_cache_rect = QRectF()

    # The item's own methods, named here for the type checker.
    def prepareGeometryChange(self) -> None: ...  # noqa: N802
    def update(self, *args: Any) -> None: ...

    def _shadow_changed(self) -> None:
        self._shadow_cache_key = None
        self.prepareGeometryChange()
        self.update()

    @property
    def shadow_enabled(self) -> bool:
        return self._shadow_enabled

    @shadow_enabled.setter
    def shadow_enabled(self, value: bool) -> None:
        self._shadow_enabled = bool(value)
        self._shadow_changed()

    @property
    def shadow_color(self) -> QColor:
        return QColor(self._shadow_color)

    @shadow_color.setter
    def shadow_color(self, value: QColor) -> None:
        self._shadow_color = QColor(value)
        self._shadow_changed()

    @property
    def shadow_offset_x(self) -> float:
        return self._shadow_offset_x

    @shadow_offset_x.setter
    def shadow_offset_x(self, value: float) -> None:
        self._shadow_offset_x = float(value)
        self._shadow_changed()

    @property
    def shadow_offset_y(self) -> float:
        return self._shadow_offset_y

    @shadow_offset_y.setter
    def shadow_offset_y(self, value: float) -> None:
        self._shadow_offset_y = float(value)
        self._shadow_changed()

    @property
    def shadow_blur(self) -> float:
        return self._shadow_blur

    @shadow_blur.setter
    def shadow_blur(self, value: float) -> None:
        self._shadow_blur = max(0.0, float(value))
        self._shadow_changed()

    # --- geometry ---

    def shadow_rect(self, shape_rect: QRectF) -> QRectF:
        """The area the shadow of *shape_rect* covers; *shape_rect* itself when disabled."""
        if not self._shadow_enabled:
            return QRectF(shape_rect)
        spread = self._shadow_blur * 2.0
        return shape_rect.translated(self._shadow_offset_x, self._shadow_offset_y).adjusted(
            -spread, -spread, spread, spread
        )

    # --- painting ---

    def paint_shadow(self, painter: QPainter, path: QPainterPath) -> None:
        """Draw the shadow of *path* (item coordinates) if the shadow is enabled."""
        if not self._shadow_enabled or self._shadow_color.alpha() == 0 or path.isEmpty():
            return
        transform = painter.worldTransform()
        scale = math.sqrt(abs(transform.determinant())) or 1.0
        bounds = path.boundingRect()
        spread = self._shadow_blur * 2.0
        local_rect = bounds.adjusted(-spread, -spread, spread, spread)
        width = min(_MAX_SHADOW_IMAGE, max(1, math.ceil(local_rect.width() * scale)))
        height = min(_MAX_SHADOW_IMAGE, max(1, math.ceil(local_rect.height() * scale)))
        key = (
            _path_signature(path),
            self._shadow_color.rgba(),
            round(self._shadow_blur, 3),
            round(scale, 3),
        )
        if key != self._shadow_cache_key or self._shadow_cache_image is None:
            image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            image_painter = QPainter(image)
            image_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            image_painter.scale(width / local_rect.width(), height / local_rect.height())
            image_painter.translate(-local_rect.topLeft())
            image_painter.fillPath(path, self._shadow_color)
            image_painter.end()
            self._shadow_cache_image = blur_image(image, self._shadow_blur * scale)
            self._shadow_cache_rect = QRectF(local_rect)
            self._shadow_cache_key = key
        target = self._shadow_cache_rect.translated(
            QPointF(self._shadow_offset_x, self._shadow_offset_y)
        )
        painter.drawImage(target, self._shadow_cache_image)

    # --- serialization ---

    def _shadow_data(self) -> dict[str, Any]:
        return {
            "shadow_enabled": self._shadow_enabled,
            "shadow_color": self._shadow_color.name(QColor.NameFormat.HexArgb),
            "shadow_offset_x": self._shadow_offset_x,
            "shadow_offset_y": self._shadow_offset_y,
            "shadow_blur": self._shadow_blur,
        }

    def _apply_shadow_data(self, data: dict[str, Any]) -> None:
        self._shadow_enabled = bool(data.get("shadow_enabled", self._shadow_enabled))
        if "shadow_color" in data:
            self._shadow_color = QColor(str(data["shadow_color"]))
        self._shadow_offset_x = float(data.get("shadow_offset_x", self._shadow_offset_x))
        self._shadow_offset_y = float(data.get("shadow_offset_y", self._shadow_offset_y))
        self._shadow_blur = max(0.0, float(data.get("shadow_blur", self._shadow_blur)))
        self._shadow_cache_key = None


def _path_signature(path: QPainterPath) -> tuple[Any, ...]:
    """A hashable summary of *path*: its element count, types, and rounded points."""
    parts: list[Any] = [path.elementCount()]
    for index in range(path.elementCount()):
        element = path.elementAt(index)
        parts.append((element.type.name, round(element.x, 2), round(element.y, 2)))
    return tuple(parts)
