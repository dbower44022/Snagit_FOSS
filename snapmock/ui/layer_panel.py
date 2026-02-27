"""LayerPanel — dock widget showing the layer stack."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from snapmock.core.layer import Layer
    from snapmock.core.layer_manager import LayerManager


class LayerPanel(QDockWidget):
    """Dockable layer panel with visibility/lock toggles."""

    def __init__(self, layer_manager: LayerManager, parent: QWidget | None = None) -> None:
        super().__init__("Layers", parent)
        self._layer_manager = layer_manager
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        container = QWidget()
        layout = QVBoxLayout(container)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("+")
        self._add_btn.setToolTip("Add layer")
        self._add_btn.clicked.connect(self._on_add_layer)
        btn_layout.addWidget(self._add_btn)

        self._remove_btn = QPushButton("-")
        self._remove_btn.setToolTip("Remove layer")
        self._remove_btn.clicked.connect(self._on_remove_layer)
        btn_layout.addWidget(self._remove_btn)
        layout.addLayout(btn_layout)

        self.setWidget(container)

        # Connect signals
        layer_manager.layer_added.connect(self._refresh)
        layer_manager.layer_removed.connect(self._refresh_str)
        layer_manager.layers_reordered.connect(self._refresh_void)
        layer_manager.active_layer_changed.connect(self._refresh_str)
        layer_manager.layer_renamed.connect(self._refresh_renamed)

        self._refresh_void()

    def _refresh(self, _layer: Layer | None = None) -> None:
        self._refresh_void()

    def _refresh_str(self, _id: str = "") -> None:
        self._refresh_void()

    def _refresh_renamed(self, _id: str, _name: str) -> None:
        self._refresh_void()

    def _refresh_void(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        # Display top-to-bottom (reverse of internal bottom-to-top)
        for layer in reversed(self._layer_manager.layers):
            item = QListWidgetItem(layer.name)
            item.setData(Qt.ItemDataRole.UserRole, layer.layer_id)
            self._list.addItem(item)
            if layer.layer_id == self._layer_manager.active_layer_id:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        item = self._list.item(row)
        if item is not None:
            layer_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(layer_id, str):
                self._layer_manager.set_active(layer_id)

    def _on_add_layer(self) -> None:
        self._layer_manager.add_layer()

    def _on_remove_layer(self) -> None:
        active = self._layer_manager.active_layer
        if active is not None:
            self._layer_manager.remove_layer(active.layer_id)

    def set_manager(self, layer_manager: LayerManager) -> None:
        """Replace the LayerManager (e.g. after opening a new project)."""
        self._layer_manager = layer_manager
        layer_manager.layer_added.connect(self._refresh)
        layer_manager.layer_removed.connect(self._refresh_str)
        layer_manager.layers_reordered.connect(self._refresh_void)
        layer_manager.active_layer_changed.connect(self._refresh_str)
        layer_manager.layer_renamed.connect(self._refresh_renamed)
        self._refresh_void()
