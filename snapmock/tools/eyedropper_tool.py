"""EyedropperTool — sample a colour from the canvas (Blur PRD Section 4).

The tool creates no items: it reads the canvas composite and hands the colour to whatever
asked for it. A press previews the colour under the cursor, a drag keeps previewing it as
the cursor moves, and the release applies the colour under the cursor at that moment
(4.2). What it reads is the canvas colour and every visible annotation item, built by
:meth:`~snapmock.core.render_engine.RenderEngine.render_sample`, so no grid line, guide,
selection handle, or tool overlay can be sampled (Eyedropper and Blur performance
decision 2).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QCursor, QImage, QMouseEvent

from snapmock.config.constants import DEFAULT_SAMPLE_SIZE, SAMPLE_SIZES
from snapmock.tools.base_tool import BaseTool
from snapmock.ui.cursors import eyedropper_cursor


def sample_rect(scene_pos: QPointF, size: int) -> QRectF:
    """The *size* by *size* canvas pixels centred on the pixel under *scene_pos* (4.2)."""
    half = size // 2
    return QRectF(math.floor(scene_pos.x()) - half, math.floor(scene_pos.y()) - half, size, size)


def average_color(image: QImage) -> QColor:
    """The colour of a sampled area: 4.2's arithmetic mean of the red, green, and blue
    channels of every pixel in it.

    A transparent pixel has no colour to average, so it is left out of the mean; the
    result's alpha is the mean over every pixel in the area, so an area half over the
    canvas edge comes back half transparent and an area with nothing in it comes back
    fully transparent, which is what 4.3 and the 8.3 row call "transparent".
    """
    total_red = total_green = total_blue = total_alpha = 0
    counted = 0
    pixels = image.width() * image.height()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            total_alpha += color.alpha()
            if color.alpha() == 0:
                continue
            total_red += color.red()
            total_green += color.green()
            total_blue += color.blue()
            counted += 1
    if counted == 0 or pixels == 0:
        return QColor(0, 0, 0, 0)
    return QColor(
        round(total_red / counted),
        round(total_green / counted),
        round(total_blue / counted),
        round(total_alpha / pixels),
    )


class EyedropperTool(BaseTool):
    """Sample a colour from the canvas; the tool creates no items.

    Since BaseTool doesn't inherit QObject, the sampled colour is stored and read back
    through :attr:`picked_color`, and callers that want it as it happens install
    :meth:`set_pick_callback` for an applied sample and
    :meth:`set_preview_callback` for the colour under the cursor.
    """

    def __init__(self) -> None:
        super().__init__()
        self._picked_color: QColor = QColor()
        self._pick_serial = 0
        self._pick_callback: Callable[[QColor], None] | None = None
        self._preview_color: QColor = QColor()
        self._preview_callback: Callable[[QColor], None] | None = None
        self._sampling = False
        self._creation_defaults["sample_size"] = DEFAULT_SAMPLE_SIZE

    @property
    def tool_id(self) -> str:
        return "eyedropper"

    @property
    def display_name(self) -> str:
        return "Eyedropper"

    @property
    def cursor(self) -> QCursor:
        """The dropper glyph with its tip as the hotspot (General UI PRD 6.6)."""
        return eyedropper_cursor()

    # ---- the sampled colour ----

    @property
    def picked_color(self) -> QColor:
        return QColor(self._picked_color)

    @property
    def pick_serial(self) -> int:
        """Counts applied samples, so a caller can tell whether one happened since it
        last looked. A preview during a drag does not count."""
        return self._pick_serial

    @property
    def preview_color(self) -> QColor:
        """The colour under the cursor as the drag moves, before it is applied (4.2)."""
        return QColor(self._preview_color)

    @property
    def pick_callback(self) -> Callable[[QColor], None] | None:
        return self._pick_callback

    def set_pick_callback(self, callback: Callable[[QColor], None] | None) -> None:
        """Called with each applied colour; the Tool Options Bar shows it (PRD 5.3)."""
        self._pick_callback = callback

    @property
    def preview_callback(self) -> Callable[[QColor], None] | None:
        return self._preview_callback

    def set_preview_callback(self, callback: Callable[[QColor], None] | None) -> None:
        """Called with the colour under the cursor while a drag lasts, so the bar's
        colour display follows the cursor in real time (4.2)."""
        self._preview_callback = callback

    # ---- the sample area (4.2, 4.4) ----

    @property
    def sample_size(self) -> int:
        """The side of the sampled square in canvas pixels: 1, 3, 5, or 11 (4.4)."""
        raw = self._creation_defaults.get("sample_size", DEFAULT_SAMPLE_SIZE)
        try:
            size = int(raw)
        except (TypeError, ValueError):
            return DEFAULT_SAMPLE_SIZE
        return size if size in SAMPLE_SIZES else DEFAULT_SAMPLE_SIZE

    def sample_image(self, scene_pos: QPointF, size: int | None = None) -> QImage | None:
        """The canvas composite over the sampled area, or None with no scene."""
        from snapmock.core.render_engine import RenderEngine

        if self._scene is None:
            return None
        area = sample_rect(scene_pos, size if size is not None else self.sample_size)
        return RenderEngine(self._scene).render_sample(area)

    def sample_at(self, scene_pos: QPointF) -> QColor:
        """The colour of the sampled area centred on *scene_pos* (4.2).

        Transparent where the area lies beyond the canvas or over nothing.
        """
        image = self.sample_image(scene_pos)
        if image is None:
            return QColor(0, 0, 0, 0)
        return average_color(image)

    # ---- the press, the drag, and the release (4.2) ----

    @property
    def is_active_operation(self) -> bool:
        return self._sampling

    def cancel(self) -> None:
        """A focus loss or Escape drops the drag; nothing is applied."""
        self._sampling = False

    def _scene_pos(self, event: QMouseEvent) -> QPointF:
        if self._scene is not None and self._scene.views():
            return self._scene.views()[0].mapToScene(event.pos())
        return QPointF()

    def _preview(self, color: QColor) -> None:
        self._preview_color = QColor(color)
        if self._preview_callback is not None:
            self._preview_callback(QColor(color))

    def _apply(self, color: QColor) -> None:
        self._picked_color = QColor(color)
        self._preview_color = QColor(color)
        self._pick_serial += 1
        if self._pick_callback is not None:
            self._pick_callback(QColor(color))

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        self._sampling = True
        self._preview(self.sample_at(self._scene_pos(event)))
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._scene is None:
            return False
        if not self._sampling:
            return False
        self._preview(self.sample_at(self._scene_pos(event)))
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._scene is None or not self._sampling:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        color = self.sample_at(self._scene_pos(event))
        self._sampling = False
        # Last: a pick callback may deactivate the tool (the colour picker's button).
        self._apply(color)
        return True

    @property
    def status_hint(self) -> str:
        return "Click to sample color"
