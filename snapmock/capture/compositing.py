"""Pure image operations on a :class:`ScreenGrab` (PRD Sections 2.2 to 2.4, 4.2, 4.5).

Everything here is a function of the frozen grab; nothing reads the screen.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QBuffer, QIODevice, QPoint, QRect, QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

from snapmock.capture.models import MonitorInfo, ScreenGrab


def physical_rect_for(logical_rect: QRect, ratio: float) -> QRect:
    """Convert a logical rectangle to physical pixels, rounding outward (PRD 4.5)."""
    left = math.floor(logical_rect.left() * ratio)
    top = math.floor(logical_rect.top() * ratio)
    right = math.ceil((logical_rect.left() + logical_rect.width()) * ratio)
    bottom = math.ceil((logical_rect.top() + logical_rect.height()) * ratio)
    return QRect(left, top, max(0, right - left), max(0, bottom - top))


def composite_cursor(grab: ScreenGrab) -> bool:
    """Draw the cursor into the monitor image under it. Returns True when drawn."""
    if grab.cursor_image is None or grab.cursor_position is None:
        return False
    monitor = grab.monitor_at(grab.cursor_position)
    if monitor is None:
        return False
    image = grab.images.get(monitor.name)
    if image is None or image.isNull():
        return False
    hotspot = grab.cursor_hotspot or QPoint(0, 0)
    local = grab.cursor_position - monitor.logical_geometry.topLeft()
    ratio = monitor.device_pixel_ratio
    x = round(local.x() * ratio) - hotspot.x()
    y = round(local.y() * ratio) - hotspot.y()
    painter = QPainter(image)
    painter.drawImage(QPoint(x, y), grab.cursor_image)
    painter.end()
    return True


def render_region(grab: ScreenGrab, logical_rect: QRect, ratio: float) -> QImage:
    """Render *logical_rect* of the virtual desktop at *ratio* physical pixels per logical.

    Each monitor's image is drawn at its own offset; a monitor whose ratio
    differs from *ratio* is scaled to match (only All Monitors with mixed
    ratios reaches that path). Areas no monitor covers stay black (PRD 4.4).
    """
    target_rect = physical_rect_for(logical_rect, ratio)
    image = QImage(target_rect.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0))
    if image.isNull() or target_rect.isEmpty():
        return image
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for monitor in grab.monitors:
        source = grab.images.get(monitor.name)
        if source is None or source.isNull():
            continue
        if not monitor.logical_geometry.intersects(logical_rect):
            continue
        # Where this monitor lands in the target image, in physical pixels.
        dest_x = monitor.logical_geometry.x() * ratio - target_rect.x()
        dest_y = monitor.logical_geometry.y() * ratio - target_rect.y()
        if math.isclose(monitor.device_pixel_ratio, ratio):
            painter.drawImage(QPoint(round(dest_x), round(dest_y)), source)
        else:
            dest = QRectF(
                dest_x,
                dest_y,
                monitor.logical_geometry.width() * ratio,
                monitor.logical_geometry.height() * ratio,
            )
            painter.drawImage(dest, source, QRectF(source.rect()))
    painter.end()
    return image


def monitor_region(grab: ScreenGrab, monitor: MonitorInfo) -> QImage:
    """The physical-pixel image of one monitor, as captured."""
    source = grab.images.get(monitor.name)
    if source is None:
        return QImage()
    return source.copy()


def max_ratio(monitors: list[MonitorInfo]) -> float:
    return max((m.device_pixel_ratio for m in monitors), default=1.0)


def image_to_png_bytes(image: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data().data())
