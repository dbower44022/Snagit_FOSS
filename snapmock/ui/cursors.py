"""Canvas cursors of General UI PRD 6.6 that Qt does not provide, drawn from the icon set.

Each cursor is a 24 px pixmap with a white halo under a black glyph so it reads on
any canvas content, and a hotspot on the point the glyph indicates. The glyph
cursors reuse the vendored Tabler files under ``resources/icons/tabler/``; the
raster-selection and text-hover cursors are drawn here because no glyph matches.
Cursors are built on first use (a QCursor needs the application) and cached.
"""

from __future__ import annotations

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from snapmock.core.theme_manager import ICONS_DIR, current_theme

CURSOR_SIZE = 24
_GLYPH_STROKE = 2
_HALO_STROKE = 4
_GLYPH = QColor(0, 0, 0)
_HALO = QColor(255, 255, 255)

_cache: dict[str, QCursor] = {}


def _render_glyph(svg: str, color: QColor, stroke: int, pixmap: QPixmap) -> None:
    data = svg.replace("currentColor", color.name(QColor.NameFormat.HexRgb)).replace(
        f'stroke-width="{_GLYPH_STROKE}"', f'stroke-width="{stroke}"'
    )
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    QSvgRenderer(data.encode("utf-8")).render(painter)
    painter.end()


def glyph_cursor(name: str, hot_x: int, hot_y: int) -> QCursor:
    """The Tabler glyph *name* as a cursor with its hotspot at (*hot_x*, *hot_y*)."""
    cached = _cache.get(name)
    if cached is not None:
        return cached
    try:
        svg = (ICONS_DIR / f"{name}.svg").read_text(encoding="utf-8")
    except OSError:
        cursor = QCursor(Qt.CursorShape.CrossCursor)
        _cache[name] = cursor
        return cursor
    pixmap = QPixmap(CURSOR_SIZE, CURSOR_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    _render_glyph(svg, _HALO, _HALO_STROKE, pixmap)
    _render_glyph(svg, _GLYPH, _GLYPH_STROKE, pixmap)
    cursor = QCursor(pixmap, hot_x, hot_y)
    _cache[name] = cursor
    return cursor


def rotate_cursor() -> QCursor:
    """Circular arrow over the rotate handle."""
    return glyph_cursor("rotate-clockwise", CURSOR_SIZE // 2, CURSOR_SIZE // 2)


def zoom_in_cursor() -> QCursor:
    """Magnifying glass with a plus; the hotspot is the lens centre."""
    return glyph_cursor("zoom-in", 10, 10)


def zoom_out_cursor() -> QCursor:
    """Magnifying glass with a minus (Zoom tool with Alt held)."""
    return glyph_cursor("zoom-out", 10, 10)


def eyedropper_cursor() -> QCursor:
    """The dropper glyph; the hotspot is its tip at the lower left."""
    return glyph_cursor("color-picker", 4, 20)


def _halo_pen(width: int) -> QPen:
    pen = QPen(_HALO, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def raster_select_cursor() -> QCursor:
    """Crosshair with a dotted square at the lower right (Raster Selection tool)."""
    cached = _cache.get("raster-select")
    if cached is not None:
        return cached
    size = CURSOR_SIZE
    mid = size // 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    square = QRect(mid + 3, mid + 3, 8, 8)
    for pen in (_halo_pen(3), QPen(_GLYPH, 1)):
        painter.setPen(pen)
        painter.drawLine(mid, 1, mid, mid - 3)
        painter.drawLine(mid, mid + 3, mid, size - 2)
        painter.drawLine(1, mid, mid - 3, mid)
        painter.drawLine(mid + 3, mid, size - 2, mid)
    painter.setPen(_halo_pen(3))
    painter.drawRect(square)
    dotted = QPen(_GLYPH, 1, Qt.PenStyle.DotLine)
    painter.setPen(dotted)
    painter.drawRect(square)
    painter.end()
    cursor = QCursor(pixmap, mid, mid)
    _cache["raster-select"] = cursor
    return cursor


def numbered_step_cursor() -> QCursor:
    """Crosshair with a small badge at the lower right (Numbered Step tool, PRD 2.1)."""
    cached = _cache.get("numbered-step")
    if cached is not None:
        return cached
    size = CURSOR_SIZE
    mid = size // 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    for pen in (_halo_pen(3), QPen(_GLYPH, 1)):
        painter.setPen(pen)
        painter.drawLine(mid, 1, mid, mid - 3)
        painter.drawLine(mid, mid + 3, mid, size - 2)
        painter.drawLine(1, mid, mid - 3, mid)
        painter.drawLine(mid + 3, mid, size - 2, mid)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    badge = QRect(mid + 3, mid + 3, 9, 9)
    painter.setPen(_halo_pen(2))
    painter.setBrush(QColor(204, 0, 0))
    painter.drawEllipse(badge)
    painter.setPen(QPen(_HALO, 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawLine(mid + 7, mid + 5, mid + 7, mid + 10)
    painter.end()
    cursor = QCursor(pixmap, mid, mid)
    _cache["numbered-step"] = cursor
    return cursor


def text_hover_cursor() -> QCursor:
    """I-beam with an accent highlight bar, shown over an existing text item."""
    cached = _cache.get("text-hover")
    if cached is not None:
        return cached
    size = CURSOR_SIZE
    mid = size // 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    accent = QColor(current_theme().accent)
    accent.setAlpha(110)
    painter.fillRect(QRect(mid - 6, 5, 13, size - 10), accent)
    for pen in (_halo_pen(3), QPen(_GLYPH, 1)):
        painter.setPen(pen)
        painter.drawLine(mid, 3, mid, size - 4)
        painter.drawLine(mid - 3, 3, mid + 3, 3)
        painter.drawLine(mid - 3, size - 4, mid + 3, size - 4)
    painter.end()
    cursor = QCursor(pixmap, mid, mid)
    _cache["text-hover"] = cursor
    return cursor


def reset_cursor_cache() -> None:
    """Drop the built cursors (tests, and a theme change for the text-hover accent)."""
    _cache.clear()
