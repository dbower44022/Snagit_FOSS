"""Document — one open file: its scene, view, selection, and clipboard."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.view import SnapView


class Document(QObject):
    """Everything that belongs to a single open canvas tab.

    Signals
    -------
    title_changed()
        Emitted when the display name, file path, or dirty state changes.
    """

    title_changed = pyqtSignal()

    def __init__(
        self,
        scene: SnapScene,
        *,
        file_path: Path | None = None,
        is_library_file: bool = False,
        display_name: str | None = None,
        library_metadata: dict[str, Any] | None = None,
        capture_metadata: dict[str, Any] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.tab_id: str = uuid.uuid4().hex
        scene.setParent(self)
        self._scene = scene
        self._view = SnapView(scene)
        self._selection_manager = SelectionManager(scene, parent=self)
        self._clipboard = ClipboardManager(scene, parent=self)
        self._file_path: Path | None = file_path
        self._is_library_file = is_library_file
        self._display_name: str | None = display_name
        self.library_metadata: dict[str, Any] | None = library_metadata
        self.capture_metadata: dict[str, Any] | None = capture_metadata
        scene.command_stack.stack_changed.connect(self.title_changed)

    # --- core objects ---

    @property
    def scene(self) -> SnapScene:
        return self._scene

    @property
    def view(self) -> SnapView:
        return self._view

    @property
    def selection_manager(self) -> SelectionManager:
        return self._selection_manager

    @property
    def clipboard(self) -> ClipboardManager:
        return self._clipboard

    # --- identity ---

    @property
    def file_path(self) -> Path | None:
        return self._file_path

    @file_path.setter
    def file_path(self, value: Path | None) -> None:
        self._file_path = value
        self.title_changed.emit()

    @property
    def is_library_file(self) -> bool:
        return self._is_library_file

    @is_library_file.setter
    def is_library_file(self, value: bool) -> None:
        self._is_library_file = value
        self.title_changed.emit()

    @property
    def display_name(self) -> str:
        if self._display_name:
            return self._display_name
        if self._file_path is not None:
            return self._file_path.stem
        return "Untitled"

    @display_name.setter
    def display_name(self, value: str | None) -> None:
        self._display_name = value
        self.title_changed.emit()

    @property
    def is_dirty(self) -> bool:
        """Library files are written back continuously and are never dirty."""
        if self._is_library_file:
            return False
        return self._scene.command_stack.is_dirty

    @property
    def tab_title(self) -> str:
        return f"*{self.display_name}" if self.is_dirty else self.display_name

    def dispose(self) -> None:
        """Release the Qt objects owned by this document."""
        self._view.setScene(None)
        self._view.deleteLater()
        self._scene.deleteLater()
        self.deleteLater()
