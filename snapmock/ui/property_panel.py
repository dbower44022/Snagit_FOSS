"""PropertyPanel — dock widget showing selected item properties."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QLabel,
    QWidget,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsItem

    from snapmock.core.selection_manager import SelectionManager


class PropertyPanel(QDockWidget):
    """Dockable panel showing properties of the selected item(s)."""

    def __init__(self, selection_manager: SelectionManager, parent: QWidget | None = None) -> None:
        super().__init__("Properties", parent)
        self._selection_manager = selection_manager
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._container = QWidget()
        self._layout = QFormLayout(self._container)
        self._info_label = QLabel("No selection")
        self._layout.addRow(self._info_label)
        self.setWidget(self._container)

        selection_manager.selection_changed.connect(self._on_selection_changed)
        selection_manager.selection_cleared.connect(self._on_selection_cleared)

    def _on_selection_changed(self, items: list[QGraphicsItem]) -> None:
        if len(items) == 0:
            self._info_label.setText("No selection")
        elif len(items) == 1:
            item = items[0]
            self._info_label.setText(f"{type(item).__name__}")
        else:
            self._info_label.setText(f"{len(items)} items selected")

    def _on_selection_cleared(self) -> None:
        self._info_label.setText("No selection")
