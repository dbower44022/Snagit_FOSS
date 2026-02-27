"""MainWindow — primary application window."""

from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow

from snapmock.config.constants import APP_NAME
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView


class MainWindow(QMainWindow):
    """Primary application window.

    Owns the SnapScene, SnapView, and SelectionManager.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(800, 600)

        self._scene = SnapScene(parent=self)
        self._view = SnapView(self._scene)
        self._selection_manager = SelectionManager(self._scene, parent=self)

        self.setCentralWidget(self._view)

    @property
    def scene(self) -> SnapScene:
        return self._scene

    @property
    def view(self) -> SnapView:
        return self._view

    @property
    def selection_manager(self) -> SelectionManager:
        return self._selection_manager
