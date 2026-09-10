"""Layer data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from PyQt6.QtGui import QPainter

BLEND_MODES: tuple[str, ...] = (
    "Normal",
    "Multiply",
    "Screen",
    "Overlay",
    "Darken",
    "Lighten",
    "Difference",
)
"""The layer blend modes of General UI PRD 7.4, in the action bar's order."""

DEFAULT_BLEND_MODE = "Normal"

LAYER_TYPE_BACKGROUND = "Background"
LAYER_TYPE_ANNOTATION = "Annotation"
LAYER_TYPE_RASTER_REGION = "RasterRegion"
LAYER_TYPES: tuple[str, ...] = (
    LAYER_TYPE_BACKGROUND,
    LAYER_TYPE_ANNOTATION,
    LAYER_TYPE_RASTER_REGION,
)
"""The layer types of Technical Architecture PRD 3.2.1; the Background layer is pinned to
the bottom of the stack (Navigation and Raster Operations follow-up decision 2)."""

_COMPOSITION_MODES: dict[str, QPainter.CompositionMode] = {
    "Normal": QPainter.CompositionMode.CompositionMode_SourceOver,
    "Multiply": QPainter.CompositionMode.CompositionMode_Multiply,
    "Screen": QPainter.CompositionMode.CompositionMode_Screen,
    "Overlay": QPainter.CompositionMode.CompositionMode_Overlay,
    "Darken": QPainter.CompositionMode.CompositionMode_Darken,
    "Lighten": QPainter.CompositionMode.CompositionMode_Lighten,
    "Difference": QPainter.CompositionMode.CompositionMode_Difference,
}


def composition_mode(blend_mode: str) -> QPainter.CompositionMode:
    """The painter composition mode a layer blend mode names; Normal for an unknown name."""
    return _COMPOSITION_MODES.get(blend_mode, QPainter.CompositionMode.CompositionMode_SourceOver)


def normalize_blend_mode(value: object) -> str:
    """*value* when it names a blend mode, else Normal (a file from an earlier build)."""
    return value if isinstance(value, str) and value in BLEND_MODES else DEFAULT_BLEND_MODE


def normalize_layer_type(value: object) -> str:
    """*value* when it names a layer type, else Annotation (a file from an earlier build)."""
    return value if isinstance(value, str) and value in LAYER_TYPES else LAYER_TYPE_ANNOTATION


@dataclass
class Layer:
    """Lightweight data object that groups scene items and controls their rendering.

    A ``Layer`` is *not* a ``QGraphicsItem``; it is metadata that the
    :class:`~snapmock.core.layer_manager.LayerManager` uses to organise items
    and synchronise z-values with the scene.
    """

    name: str
    layer_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    blend_mode: str = DEFAULT_BLEND_MODE
    layer_type: str = LAYER_TYPE_ANNOTATION
    z_base: int = 0
    item_ids: list[str] = field(default_factory=list)

    @property
    def is_background(self) -> bool:
        return self.layer_type == LAYER_TYPE_BACKGROUND

    def clone(self, *, new_id: bool = True) -> Layer:
        """Return a deep copy.  If *new_id* is True a fresh id is generated.

        The copy is an Annotation layer whatever the original's type, so a project never
        holds two Background layers by accident (follow-up decision 2).
        """
        return Layer(
            name=f"{self.name} copy",
            layer_id=uuid.uuid4().hex if new_id else self.layer_id,
            visible=self.visible,
            locked=self.locked,
            opacity=self.opacity,
            blend_mode=self.blend_mode,
            layer_type=LAYER_TYPE_ANNOTATION,
            z_base=self.z_base,
            item_ids=list(self.item_ids),
        )
