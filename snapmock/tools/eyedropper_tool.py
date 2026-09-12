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

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QCursor, QImage, QMouseEvent

from snapmock.config.constants import (
    COLOR_HISTORY_MAX,
    DEFAULT_APPLY_TARGET,
    DEFAULT_SAMPLE_SIZE,
    SAMPLE_SIZES,
    ApplyTarget,
    ColorFormat,
)
from snapmock.tools.base_tool import BaseTool
from snapmock.ui.cursors import eyedropper_cursor
from snapmock.ui.loupe_overlay import LOUPE_CAPTURE_SIDE, LoupeOverlay


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


def format_color_value(color: QColor, color_format: ColorFormat) -> str:
    """*color* written as 4.4's three formats, in 4.4's own spelling.

    A sample with nothing under it reads "transparent", as 4.3 and the 8.3 row ask.
    """
    if not color.isValid() or color.alpha() == 0:
        return "transparent"
    if color_format is ColorFormat.RGB:
        return f"rgb ({color.red()}, {color.green()}, {color.blue()})"
    if color_format is ColorFormat.HSL:
        hue = max(0, color.hslHue())
        saturation = round(color.hslSaturation() / 255 * 100)
        lightness = round(color.lightness() / 255 * 100)
        return f"{hue}°, {saturation}%, {lightness}%"
    return color.name().upper()


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
        self._loupe: LoupeOverlay | None = None
        self._history: list[QColor] = []
        # 4.4's tool-session properties. The four the bar edits are creation defaults, so a
        # preset and a theme capture them; last_sampled_color and the history do not persist.
        self._creation_defaults["sample_size"] = DEFAULT_SAMPLE_SIZE
        self._creation_defaults["color_format"] = ColorFormat.HEX
        self._creation_defaults["apply_target"] = DEFAULT_APPLY_TARGET
        self._creation_defaults["copy_to_clipboard"] = False

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

    @property
    def color_format(self) -> ColorFormat:
        """How the colour value reads: hexadecimal, red-green-blue, or
        hue-saturation-lightness (4.4)."""
        raw = self._creation_defaults.get("color_format", ColorFormat.HEX)
        return raw if isinstance(raw, ColorFormat) else ColorFormat.HEX

    @property
    def apply_target(self) -> ApplyTarget:
        """Which colour property an applied sample sets (4.4, 4.6)."""
        raw = self._creation_defaults.get("apply_target", DEFAULT_APPLY_TARGET)
        return raw if isinstance(raw, ApplyTarget) else DEFAULT_APPLY_TARGET

    @property
    def copy_to_clipboard(self) -> bool:
        """Whether each applied sample also copies its value to the system clipboard (4.4)."""
        return bool(self._creation_defaults.get("copy_to_clipboard", False))

    @property
    def last_sampled_color(self) -> QColor:
        """4.4's ``last_sampled_color``: the most recently applied sample."""
        return QColor(self._picked_color)

    @property
    def color_history(self) -> list[QColor]:
        """4.5's Color History: the last eight applied samples, newest first."""
        return [QColor(color) for color in self._history]

    def push_history(self, color: QColor) -> None:
        """Put *color* at the head of the history, de-duplicated, capped at eight (4.5).

        Session state: 7.3 offers a settings file for it and does not require one.
        """
        if not color.isValid() or color.alpha() == 0:
            return
        self._history = [c for c in self._history if c.rgba() != color.rgba()]
        self._history.insert(0, QColor(color))
        del self._history[COLOR_HISTORY_MAX:]

    def set_last_sampled_color(self, color: QColor) -> None:
        """Make *color* the last sampled colour without counting a new sample: a click on
        a Color History swatch re-applies one that was sampled already (4.5)."""
        self._picked_color = QColor(color)
        self._preview_color = QColor(color)

    def value_text(self, color: QColor | None = None) -> str:
        """The last sampled colour, or *color*, in the chosen format (4.5)."""
        return format_color_value(self.picked_color if color is None else color, self.color_format)

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

    # ---- the preview loupe (4.3) ----

    @property
    def loupe(self) -> LoupeOverlay | None:
        """The magnified preview, once the tool has had a view to put it over."""
        return self._loupe

    def _ensure_loupe(self) -> LoupeOverlay | None:
        view = self._view
        viewport = view.viewport() if view is not None else None
        if viewport is None:
            return None
        if self._loupe is None or self._loupe.parentWidget() is not viewport:
            self._loupe = LoupeOverlay(viewport)
        return self._loupe

    def update_loupe(self, view_pos: QPoint) -> None:
        """Show the loupe beside *view_pos*, in the viewport's coordinates, magnifying the
        canvas under it (4.3). Called on every move, and on the Alt key press, so the loupe
        appears before any click (4.7)."""
        loupe = self._ensure_loupe()
        view = self._view
        if loupe is None or view is None:
            return
        scene_pos = view.mapToScene(view_pos)
        image = self.sample_image(scene_pos, LOUPE_CAPTURE_SIDE)
        loupe.show_sample(view_pos, image, self.sample_at(scene_pos), self.sample_size)

    def hide_loupe(self) -> None:
        if self._loupe is not None:
            self._loupe.hide()

    # ---- the press, the drag, and the release (4.2) ----

    @property
    def is_active_operation(self) -> bool:
        return self._sampling

    def deactivate(self) -> None:
        self.hide_loupe()
        super().deactivate()

    def cancel(self) -> None:
        """A focus loss or Escape drops the drag; nothing is applied."""
        self._sampling = False
        self.hide_loupe()

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
        self.update_loupe(event.pos())
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        """The loupe follows the cursor whether or not a button is down (4.3); only a drag
        previews the colour into the Tool Options Bar (4.2)."""
        if self._scene is None:
            return False
        self.update_loupe(event.pos())
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
        self.update_loupe(event.pos())
        # Last: a pick callback may deactivate the tool (the colour picker's button).
        self._apply(color)
        return True

    @property
    def status_hint(self) -> str:
        return "Click to sample color"
