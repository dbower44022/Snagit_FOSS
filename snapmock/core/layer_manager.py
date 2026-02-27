"""LayerManager — owns the ordered layer stack and emits change signals."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from snapmock.config.constants import LAYER_Z_RANGE
from snapmock.core.layer import Layer


class LayerManager(QObject):
    """Manages an ordered list of :class:`Layer` objects.

    Layers are indexed bottom-to-top: index 0 is the lowest layer.

    Signals
    -------
    layer_added(Layer)
    layer_removed(str)
        Emitted with the removed layer's id.
    layers_reordered()
    active_layer_changed(str)
        Emitted with the new active layer's id.
    layer_visibility_changed(str, bool)
    layer_lock_changed(str, bool)
    layer_opacity_changed(str, float)
    layer_renamed(str, str)
    """

    layer_added = pyqtSignal(object)
    layer_removed = pyqtSignal(str)
    layers_reordered = pyqtSignal()
    active_layer_changed = pyqtSignal(str)
    layer_visibility_changed = pyqtSignal(str, bool)
    layer_lock_changed = pyqtSignal(str, bool)
    layer_opacity_changed = pyqtSignal(str, float)
    layer_renamed = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._layers: list[Layer] = []
        self._active_id: str = ""

    # --- queries ---

    @property
    def layers(self) -> list[Layer]:
        """Return the layer list (bottom-to-top)."""
        return list(self._layers)

    @property
    def count(self) -> int:
        return len(self._layers)

    @property
    def active_layer(self) -> Layer | None:
        return self.layer_by_id(self._active_id)

    @property
    def active_layer_id(self) -> str:
        return self._active_id

    def layer_by_id(self, layer_id: str) -> Layer | None:
        for layer in self._layers:
            if layer.layer_id == layer_id:
                return layer
        return None

    def index_of(self, layer_id: str) -> int:
        for i, layer in enumerate(self._layers):
            if layer.layer_id == layer_id:
                return i
        return -1

    # --- mutations ---

    def add_layer(self, name: str | None = None, index: int | None = None) -> Layer:
        """Create and insert a new layer. Returns the new layer."""
        if name is None:
            name = f"Layer {self.count + 1}"
        layer = Layer(name=name)
        if index is None:
            index = len(self._layers)
        self._layers.insert(index, layer)
        self._recalc_z_bases()
        if not self._active_id:
            self._active_id = layer.layer_id
            self.active_layer_changed.emit(self._active_id)
        self.layer_added.emit(layer)
        return layer

    def insert_layer(self, layer: Layer, index: int) -> None:
        """Insert an existing layer object at *index*."""
        self._layers.insert(index, layer)
        self._recalc_z_bases()
        self.layer_added.emit(layer)

    def remove_layer(self, layer_id: str) -> Layer | None:
        """Remove a layer by id. Returns the removed layer, or None."""
        if self.count <= 1:
            return None  # never remove the last layer
        idx = self.index_of(layer_id)
        if idx < 0:
            return None
        layer = self._layers.pop(idx)
        self._recalc_z_bases()
        # If active layer was removed, activate the nearest one
        if self._active_id == layer_id:
            new_idx = min(idx, len(self._layers) - 1)
            self._active_id = self._layers[new_idx].layer_id
            self.active_layer_changed.emit(self._active_id)
        self.layer_removed.emit(layer_id)
        return layer

    def move_layer(self, layer_id: str, new_index: int) -> None:
        """Move a layer to *new_index* in the stack."""
        old_idx = self.index_of(layer_id)
        if old_idx < 0 or old_idx == new_index:
            return
        layer = self._layers.pop(old_idx)
        new_index = max(0, min(new_index, len(self._layers)))
        self._layers.insert(new_index, layer)
        self._recalc_z_bases()
        self.layers_reordered.emit()

    def set_active(self, layer_id: str) -> None:
        """Make the layer with *layer_id* the active layer."""
        if self.layer_by_id(layer_id) is None:
            return
        if self._active_id != layer_id:
            self._active_id = layer_id
            self.active_layer_changed.emit(layer_id)

    def set_visibility(self, layer_id: str, visible: bool) -> None:
        layer = self.layer_by_id(layer_id)
        if layer is not None:
            layer.visible = visible
            self.layer_visibility_changed.emit(layer_id, visible)

    def set_locked(self, layer_id: str, locked: bool) -> None:
        layer = self.layer_by_id(layer_id)
        if layer is not None:
            layer.locked = locked
            self.layer_lock_changed.emit(layer_id, locked)

    def set_opacity(self, layer_id: str, opacity: float) -> None:
        layer = self.layer_by_id(layer_id)
        if layer is not None:
            layer.opacity = max(0.0, min(1.0, opacity))
            self.layer_opacity_changed.emit(layer_id, layer.opacity)

    def rename_layer(self, layer_id: str, name: str) -> None:
        layer = self.layer_by_id(layer_id)
        if layer is not None:
            layer.name = name
            self.layer_renamed.emit(layer_id, name)

    # --- internal ---

    def _recalc_z_bases(self) -> None:
        """Recalculate z_base for each layer based on stack position."""
        for i, layer in enumerate(self._layers):
            layer.z_base = i * LAYER_Z_RANGE
