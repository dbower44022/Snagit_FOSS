"""BaseTool — abstract base class for all interactive tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager


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

    # --- event handlers (return True if consumed) ---

    def mouse_press(self, event: QMouseEvent) -> bool:
        return False

    def mouse_move(self, event: QMouseEvent) -> bool:
        return False

    def mouse_release(self, event: QMouseEvent) -> bool:
        return False

    def mouse_double_click(self, event: QMouseEvent) -> bool:
        return False
