"""SnagitReader — load Snagit .snagx ZIP archives into a SnapScene."""

from __future__ import annotations

import base64
import json
import logging
import zipfile
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QLineF, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QImage, QPixmap

from snapmock.core.scene import SnapScene
from snapmock.io.rtf_utils import extract_font_from_rtf, extract_text_from_rtf
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.callout_item import CalloutItem
from snapmock.items.line_item import LineItem
from snapmock.items.raster_region_item import RasterRegionItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem

log = logging.getLogger(__name__)


def load_snagx(path: Path) -> SnapScene:
    """Load a Snagit ``.snagx`` file and return a fully-populated *SnapScene*."""
    with zipfile.ZipFile(path, "r") as zf:
        index = json.loads(zf.read("index.json"))
        pages = index.get("Pages", [])
        if not pages:
            raise ValueError("snagx index.json contains no pages")

        page_filename = pages[0]
        page = json.loads(zf.read(page_filename))

        width = int(page.get("CaptureCanvasWidth", 1920))
        height = int(page.get("CaptureCanvasHeight", 1080))
        scene = SnapScene(width=width, height=height)

        bg_color_str = page.get("CaptureBackgroundColor", "#00000000")
        bg_color = QColor(bg_color_str)
        if bg_color.alpha() > 0:
            scene.set_background_color(bg_color)

        # -- Background layer --
        bg_layer = scene.layer_manager.active_layer
        if bg_layer is None:
            bg_layer = scene.layer_manager.add_layer("Background")
        else:
            scene.layer_manager.rename_layer(bg_layer.layer_id, "Background")

        bg_image_name = page.get("CaptureBackgroundImage", "")
        if bg_image_name and bg_image_name in zf.namelist():
            png_data = zf.read(bg_image_name)
            img = QImage()
            img.loadFromData(png_data)
            if not img.isNull():
                bg_item = RasterRegionItem(pixmap=QPixmap.fromImage(img))
                bg_item.layer_id = bg_layer.layer_id
                bg_layer.item_ids.append(bg_item.item_id)
                bg_item.setZValue(bg_layer.z_base)
                # Position background at CaptureBackgroundLocation
                bg_loc = page.get("CaptureBackgroundLocation", "0,0")
                bx, by = _parse_point(bg_loc)
                bg_item.setPos(bx, by)
                scene.addItem(bg_item)

        # -- Annotations layer --
        ann_layer = scene.layer_manager.add_layer("Annotations")
        scene.layer_manager.set_active(ann_layer.layer_id)

        z_offset = 1
        for obj in page.get("CaptureObjects", []):
            item = _convert_object(obj, zf)
            if item is None:
                continue
            item.layer_id = ann_layer.layer_id
            ann_layer.item_ids.append(item.item_id)
            item.setZValue(ann_layer.z_base + z_offset)
            z_offset += 1
            scene.addItem(item)

        # Store page-level metadata on the scene for round-trip
        scene._snagit_metadata = {  # type: ignore[attr-defined]
            "page": page,
            "index": index,
        }
        try:
            meta_raw = zf.read("metadata.json")
            scene._snagit_metadata["metadata"] = json.loads(meta_raw)  # type: ignore[attr-defined]
        except KeyError:
            pass

    scene.command_stack.clear()
    scene.command_stack.mark_clean()
    return scene


# ---- dispatch ----


def _convert_object(
    obj: dict[str, Any], zf: zipfile.ZipFile
) -> SnapGraphicsItem | None:
    """Dispatch a Snagit CaptureObject to the appropriate converter."""
    tool_mode = obj.get("ToolMode", "")
    item: SnapGraphicsItem | None = None
    try:
        if tool_mode == "Arrow":
            item = _convert_arrow(obj)
        elif tool_mode == "Line":
            item = _convert_line(obj)
        elif tool_mode == "Shape":
            item = _convert_shape(obj)
        elif tool_mode == "Highlight":
            item = _convert_highlight(obj)
        elif tool_mode == "Callout":
            item = _convert_callout(obj)
        elif tool_mode == "Text":
            item = _convert_text(obj)
        elif tool_mode == "Image":
            item = _convert_image(obj, zf)
        elif tool_mode == "Stamp":
            item = _convert_stamp(obj, zf)
        else:
            log.warning("Unsupported Snagit ToolMode %r — skipping", tool_mode)
            return None
    except Exception:
        log.exception("Failed to convert Snagit object %r", obj.get("ObjectID", "?"))
        return None

    if item is not None:
        # Stash raw Snagit data for round-trip
        item._snagit_data = obj  # type: ignore[union-attr]
        # Apply shared opacity
        opacity = obj.get("Opacity", 100)
        item.setOpacity(opacity / 100.0)
    return item


# ---- converters ----


def _convert_arrow(obj: dict[str, Any]) -> ArrowItem:
    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = _parse_point(points[1]) if len(points) > 1 else (100.0, 0.0)
    item = ArrowItem(line=QLineF(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1])))
    item._stroke_color = QColor(obj.get("ForegroundColor", "#FFFF0000"))
    item._stroke_width = float(obj.get("StrokeWidth", 2))
    return item


def _convert_line(obj: dict[str, Any]) -> LineItem:
    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = _parse_point(points[1]) if len(points) > 1 else (100.0, 0.0)
    item = LineItem(line=QLineF(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1])))
    item._stroke_color = QColor(obj.get("ForegroundColor", "#FFFF0000"))
    item._stroke_width = float(obj.get("StrokeWidth", 2))
    return item


def _convert_shape(obj: dict[str, Any]) -> RectangleItem:
    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = _parse_point(points[1]) if len(points) > 1 else (100.0, 60.0)
    x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])

    corner_radius = 0.0
    tool_shape = obj.get("ToolShape", "Rectangle")
    if tool_shape == "RoundedRectangle":
        ratio = obj.get("CornerRadiusRatio", 0.25)
        corner_radius = ratio * min(w, h)

    item = RectangleItem(corner_radius=corner_radius)
    # Set position via setPos and use a local-origin rect
    item.setPos(x, y)
    item._rect = QRectF(0, 0, w, h)

    item._stroke_color = QColor(obj.get("ForegroundColor", "#FFFF0000"))
    item._stroke_width = float(obj.get("StrokeWidth", 2))
    item._fill_color = QColor(obj.get("BackgroundColor", "#00000000"))
    item.setRotation(float(obj.get("RotationAngle", 0)))
    return item


def _convert_highlight(obj: dict[str, Any]) -> RectangleItem:
    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = _parse_point(points[1]) if len(points) > 1 else (100.0, 30.0)
    x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])

    item = RectangleItem()
    item.setPos(x, y)
    item._rect = QRectF(0, 0, w, h)
    # Highlight: semi-transparent fill, no stroke
    item._fill_color = QColor(obj.get("BackgroundColor", "#FFF7AC08"))
    item._stroke_color = QColor(0, 0, 0, 0)
    item._stroke_width = 0.0
    # Tag as highlight for round-trip
    item._snagit_highlight = True  # type: ignore[attr-defined]
    return item


def _convert_callout(obj: dict[str, Any]) -> CalloutItem:
    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = _parse_point(points[1]) if len(points) > 1 else (150.0, 60.0)
    x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])

    # Tail
    tails = obj.get("CalloutTails", [])
    if tails:
        tx, ty = _parse_point(tails[0])
        tail_tip = QPointF(tx - x, ty - y)  # Convert to local coords
    else:
        tail_tip = QPointF(w / 2, h + 30)

    # Text from RTF
    text = "Callout"
    font_family = "Sans Serif"
    font_size = 14
    text_color = QColor(0, 0, 0)
    rtf = obj.get("RTFEncodedText", "")
    if rtf:
        text = extract_text_from_rtf(rtf)
        font_family, font_size, text_color = extract_font_from_rtf(rtf)

    item = CalloutItem(
        text=text,
        rect=QRectF(0, 0, w, h),
        tail_tip=tail_tip,
    )
    item.setPos(x, y)
    item._font = QFont(font_family, font_size)
    item._text_color = text_color
    item._bg_color = QColor(obj.get("BackgroundColor", "#FFFFFFFF"))
    item._border_color = QColor(obj.get("ForegroundColor", "#FFFC4242"))
    return item


def _convert_text(obj: dict[str, Any]) -> TextItem:
    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = _parse_point(points[1]) if len(points) > 1 else (200.0, 30.0)
    x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])

    text = "Text"
    font_family = "Sans Serif"
    font_size = 14
    text_color = QColor(0, 0, 0)
    rtf = obj.get("RTFEncodedText", "")
    if rtf:
        text = extract_text_from_rtf(rtf)
        font_family, font_size, text_color = extract_font_from_rtf(rtf)

    item = TextItem(text=text, pos_x=x, pos_y=y)
    item._font = QFont(font_family, font_size)
    item._color = text_color
    item._width = max(w, 20.0)
    return item


def _convert_image(
    obj: dict[str, Any], zf: zipfile.ZipFile
) -> RasterRegionItem | None:
    image_b64 = obj.get("Image", "")
    if not image_b64:
        return None

    img_data = base64.b64decode(image_b64)
    img = QImage()
    img.loadFromData(img_data)
    if img.isNull():
        log.warning("Could not decode Image data for object %s", obj.get("ObjectID"))
        return None

    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = (
        _parse_point(points[1])
        if len(points) > 1
        else (p1[0] + img.width(), p1[1] + img.height())
    )
    x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])

    # Scale image to the bounding box specified by PointsArray
    pixmap = QPixmap.fromImage(img)
    if w > 0 and h > 0 and (pixmap.width() != int(w) or pixmap.height() != int(h)):
        pixmap = pixmap.scaled(int(w), int(h))

    item = RasterRegionItem(pixmap=pixmap)
    item.setPos(x, y)
    item.setRotation(float(obj.get("RotationAngle", 0)))
    return item


def _convert_stamp(
    obj: dict[str, Any], zf: zipfile.ZipFile
) -> RasterRegionItem | None:
    """Convert a Stamp object.

    Stamps may contain PDF data.  We attempt to decode as a raster image
    first; if that fails we skip the stamp.
    """
    image_b64 = obj.get("Image", "")
    if not image_b64:
        return None

    img_data = base64.b64decode(image_b64)
    img = QImage()
    img.loadFromData(img_data)

    if img.isNull():
        # Stamp data is likely a PDF — not directly loadable as QImage.
        log.warning(
            "Stamp %s uses PDF data that cannot be rendered — skipping",
            obj.get("ObjectID"),
        )
        return None

    points = obj.get("PointsArray", [])
    p1 = _parse_point(points[0]) if len(points) > 0 else (0.0, 0.0)
    p2 = (
        _parse_point(points[1])
        if len(points) > 1
        else (p1[0] + img.width(), p1[1] + img.height())
    )
    x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])

    pixmap = QPixmap.fromImage(img)
    if w > 0 and h > 0 and (pixmap.width() != int(w) or pixmap.height() != int(h)):
        pixmap = pixmap.scaled(int(w), int(h))

    item = RasterRegionItem(pixmap=pixmap)
    item.setPos(x, y)
    item.setRotation(float(obj.get("RotationAngle", 0)))
    return item


# ---- helpers ----


def _parse_point(s: str) -> tuple[float, float]:
    """Parse ``"x,y"`` string into a float tuple."""
    parts = s.split(",")
    return float(parts[0]), float(parts[1])
