"""Alpha masks for the Blur tool's freeform regions (Blur PRD 2.5, 7.1).

A mask is a ``QImage`` in canvas pixels aligned to the blur region's rectangle: opaque
white where the region obscures what lies beneath it, transparent where it does not
(freeform blur decision 1, option A). The mask is written to the project file under
``alpha_mask_data`` as a base64 PNG inline in ``items.json`` while the PNG is under
100 KB, and past that as a ``file:`` reference to an entry in the archive's ``raster/``
directory, which the serializer writes and reads (7.1).
"""

from __future__ import annotations

import base64

from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QImage

MASK_FORMAT = QImage.Format.Format_ARGB32_Premultiplied
"""Masks are premultiplied ARGB, so a painter can clip with ``DestinationIn`` directly."""

INLINE_LIMIT = 100 * 1024
"""A PNG of this many bytes or more goes into the archive instead of ``items.json`` (7.1)."""

FILE_PREFIX = "file:"


def blank_mask(width: int, height: int) -> QImage:
    """An empty mask *width* by *height* canvas pixels: nothing is obscured yet."""
    mask = QImage(max(1, int(width)), max(1, int(height)), MASK_FORMAT)
    mask.fill(Qt.GlobalColor.transparent)
    return mask


def scaled_mask(mask: QImage, width: int, height: int) -> QImage:
    """*mask* resampled to *width* by *height*, as a resize of the region resamples it."""
    if mask.isNull():
        return mask
    scaled = mask.scaled(
        max(1, int(width)),
        max(1, int(height)),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return scaled.convertToFormat(MASK_FORMAT)


def encode_mask_png(mask: QImage) -> bytes:
    """*mask* as PNG bytes; empty when there is no mask."""
    if mask.isNull():
        return b""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    mask.save(buffer, "PNG")
    return bytes(buffer.data().data())


def decode_mask_png(data: bytes) -> QImage | None:
    """The mask a PNG holds, or None when the bytes are not readable as an image."""
    if not data:
        return None
    image = QImage()
    if not image.loadFromData(data, "PNG"):
        return None
    return image.convertToFormat(MASK_FORMAT)


def mask_entry_name(item_id: str) -> str:
    """The archive entry a large mask is written to (7.1)."""
    return f"raster/blur_mask_{item_id}.png"


def encode_mask_field(mask: QImage | None, item_id: str) -> tuple[str | None, bytes]:
    """The ``alpha_mask_data`` value for *mask* and the bytes the archive must carry.

    Under the inline limit the value is the base64 PNG and the bytes are empty; at or
    above it the value is ``file:raster/blur_mask_<item_id>.png`` and the bytes are the
    PNG the serializer writes there (7.1). A missing mask gives ``None`` and no bytes.
    """
    if mask is None or mask.isNull():
        return None, b""
    png = encode_mask_png(mask)
    if not png:
        return None, b""
    if len(png) < INLINE_LIMIT:
        return base64.b64encode(png).decode("ascii"), b""
    return FILE_PREFIX + mask_entry_name(item_id), png


def decode_mask_field(value: object) -> QImage | None:
    """The mask an inline ``alpha_mask_data`` value holds; None for a ``file:`` reference,
    which only the project serializer can resolve, and for anything unreadable."""
    if not isinstance(value, str) or not value or value.startswith(FILE_PREFIX):
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        return None
    return decode_mask_png(raw)


def mask_file_reference(value: object) -> str | None:
    """The archive entry a ``file:`` ``alpha_mask_data`` value names, or None."""
    if isinstance(value, str) and value.startswith(FILE_PREFIX):
        return value[len(FILE_PREFIX) :]
    return None
