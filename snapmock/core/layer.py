"""Layer data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


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
    z_base: int = 0
    item_ids: list[str] = field(default_factory=list)

    def clone(self, *, new_id: bool = True) -> Layer:
        """Return a deep copy.  If *new_id* is True a fresh id is generated."""
        return Layer(
            name=f"{self.name} copy",
            layer_id=uuid.uuid4().hex if new_id else self.layer_id,
            visible=self.visible,
            locked=self.locked,
            opacity=self.opacity,
            z_base=self.z_base,
            item_ids=list(self.item_ids),
        )
