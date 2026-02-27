"""BaseTool — abstract base class for all interactive tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QToolBar

    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager
    from snapmock.core.view import SnapView


class BaseTool(ABC):
    """Abstract base for all drawing/editing tools.

    Subclasses override mouse/key handlers and return ``True`` if the
    event was consumed.
    """

    def __init__(self) -> None:
        self._scene: SnapScene | None = None
        self._selection_manager: SelectionManager | None = None

    # --- identity ---

    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Unique string identifier for this tool."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for toolbar/tooltip."""

    @property
    def cursor(self) -> Qt.CursorShape:
        """Cursor to display when this tool is active."""
        return Qt.CursorShape.ArrowCursor

    # --- lifecycle ---

    def activate(self, scene: SnapScene, selection_manager: SelectionManager) -> None:
        """Called when this tool becomes the active tool."""
        self._scene = scene
        self._selection_manager = selection_manager

    def deactivate(self) -> None:
        """Called when another tool replaces this one."""
        self._scene = None
        self._selection_manager = None

    def cancel(self) -> None:
        """Clean teardown of any in-progress operation.

        Called when the tool is switched away or when Escape is pressed.
        Subclasses should override to remove overlays, cancel drags, etc.
        """

    # --- properties ---

    @property
    def is_active_operation(self) -> bool:
        """Whether the tool has an active drag/operation in progress.

        When True, Space-bar pan override is suppressed so the tool keeps
        receiving events.
        """
        return False

    @property
    def _view(self) -> SnapView | None:
        """Convenience accessor for the first view attached to the scene."""
        if self._scene is not None and self._scene.views():
            return self._scene.views()[0]  # type: ignore[return-value]
        return None

    # --- event handlers (return True if consumed) ---

    def mouse_press(self, event: QMouseEvent) -> bool:
        return False

    def mouse_move(self, event: QMouseEvent) -> bool:
        return False

    def mouse_release(self, event: QMouseEvent) -> bool:
        return False

    def mouse_double_click(self, event: QMouseEvent) -> bool:
        return False

    def key_press(self, event: QKeyEvent) -> bool:
        """Handle a key press event. Return True if consumed."""
        return False

    def key_release(self, event: QKeyEvent) -> bool:
        """Handle a key release event. Return True if consumed."""
        return False

    # --- options bar ---

    def build_options_widgets(self, toolbar: QToolBar) -> None:
        """Populate *toolbar* with per-tool option widgets.

        Called each time this tool is activated.  Default does nothing.
        """
