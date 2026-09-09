"""SnapScene — the backbone QGraphicsScene that owns LayerManager + CommandStack."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSizeF, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsScene

from snapmock.config.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    PASTEBOARD_MARGIN,
)
from snapmock.core.command_stack import CommandStack
from snapmock.core.guides import Guide
from snapmock.core.layer_manager import LayerManager


class SnapScene(QGraphicsScene):
    """Extended QGraphicsScene with layer and command-stack management.

    Signals
    -------
    canvas_size_changed(QSizeF)
        Emitted when the logical canvas size changes.
    guides_changed()
        Emitted after the guide list changes (General UI PRD 6.5).
    """

    canvas_size_changed = pyqtSignal(QSizeF)
    background_changed = pyqtSignal()
    guides_changed = pyqtSignal()

    def __init__(
        self,
        width: int = DEFAULT_CANVAS_WIDTH,
        height: int = DEFAULT_CANVAS_HEIGHT,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._canvas_size = QSizeF(width, height)
        self._background_color: QColor = QColor("white")
        self._guides: list[Guide] = []
        self._update_scene_rect()

        self._layer_manager = LayerManager(self)
        self._command_stack = CommandStack(self)

        # Create default layer
        self._layer_manager.add_layer("Layer 1")

    # --- accessors ---

    @property
    def layer_manager(self) -> LayerManager:
        return self._layer_manager

    @property
    def command_stack(self) -> CommandStack:
        return self._command_stack

    @property
    def background_color(self) -> QColor:
        return QColor(self._background_color)

    def set_background_color(self, color: QColor) -> None:
        """Set the canvas background color."""
        self._background_color = QColor(color)
        self.background_changed.emit()
        self.update()

    @property
    def canvas_size(self) -> QSizeF:
        return QSizeF(self._canvas_size)

    @property
    def canvas_rect(self) -> QRectF:
        """Logical canvas bounds (0, 0, w, h) — use instead of sceneRect()."""
        return QRectF(0, 0, self._canvas_size.width(), self._canvas_size.height())

    def set_canvas_size(self, size: QSizeF) -> None:
        """Resize the logical canvas."""
        self._canvas_size = QSizeF(size)
        self._update_scene_rect()
        self.canvas_size_changed.emit(self._canvas_size)

    # --- guides (General UI PRD 6.5); mutate through commands/guide_commands.py ---

    @property
    def guides(self) -> list[Guide]:
        return list(self._guides)

    def add_guide(self, guide: Guide) -> None:
        if guide not in self._guides:
            self._guides.append(guide)
            self._guides_did_change()

    def remove_guide(self, guide: Guide) -> None:
        if guide in self._guides:
            self._guides.remove(guide)
            self._guides_did_change()

    def replace_guide(self, old: Guide, new: Guide) -> None:
        if old in self._guides:
            self._guides[self._guides.index(old)] = new
            self._guides_did_change()

    def set_guides(self, guides: list[Guide]) -> None:
        self._guides = list(guides)
        self._guides_did_change()

    def _guides_did_change(self) -> None:
        self.guides_changed.emit()
        # Every view repaints its foreground through Qt's own scene-update path.
        self.update()

    def _update_scene_rect(self) -> None:
        """Expand sceneRect beyond the canvas to provide a pasteboard margin."""
        m = PASTEBOARD_MARGIN
        w = self._canvas_size.width()
        h = self._canvas_size.height()
        self.setSceneRect(QRectF(-m, -m, w + 2 * m, h + 2 * m))
