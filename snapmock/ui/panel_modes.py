"""Panel collapse modes of General UI PRD Sections 15.1 and 15.2.

The main window's width picks a mode for the two right panels: full, narrow
(200 px, abbreviated controls) below the narrow threshold, and icon strip
(48 px, thumbnails only, a popover for the controls) at or below the strip
threshold. The strip threshold is the minimum window width, so "below 1024 px"
in the PRD is read as "at or below": the window cannot go lower.
"""

from __future__ import annotations

from enum import Enum

from snapmock.config.constants import (
    DEFAULT_PANEL_WIDTH,
    PANEL_NARROW_THRESHOLD_DEFAULT,
    PANEL_STRIP_THRESHOLD_DEFAULT,
)

NARROW_THRESHOLD_DEFAULT = PANEL_NARROW_THRESHOLD_DEFAULT
"""Window width below which the panels go narrow (PRD 15.2)."""
STRIP_THRESHOLD_DEFAULT = PANEL_STRIP_THRESHOLD_DEFAULT
"""Window width at or below which the panels become icon strips (PRD 15.1, 15.2)."""

NARROW_PANEL_WIDTH = 200
STRIP_PANEL_WIDTH = 48


class PanelMode(Enum):
    FULL = "full"
    NARROW = "narrow"
    ICON_STRIP = "icon_strip"


def mode_for_width(width: int, narrow_threshold: int, strip_threshold: int) -> PanelMode:
    """The mode a window *width* selects under the two thresholds."""
    if width <= strip_threshold:
        return PanelMode.ICON_STRIP
    if width < narrow_threshold:
        return PanelMode.NARROW
    return PanelMode.FULL


def panel_width_for(mode: PanelMode) -> int:
    """The width the right panels take in *mode*."""
    if mode is PanelMode.ICON_STRIP:
        return STRIP_PANEL_WIDTH
    if mode is PanelMode.NARROW:
        return NARROW_PANEL_WIDTH
    return DEFAULT_PANEL_WIDTH
