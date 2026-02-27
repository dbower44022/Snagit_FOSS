"""SnapScene — the backbone QGraphicsScene that owns LayerManager + CommandStack."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSizeF, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsScene

from snapmock.config.constants import DEFAULT_CANVAS_HEIGHT, DEFAULT_CANVAS_WIDTH
from snapmock.core.command_stack import CommandStack
from snapmock.core.layer_manager import LayerManager


class SnapScene(QGraphicsScene):
    """Extended QGraphicsScene with layer and command-stack management.

    Signals
    -------
    canvas_size_changed(QSizeF)
        Emitted when the logical canvas size changes.
    """

    canvas_size_changed = pyqtSignal(QSizeF)

    def __init__(
        self,
        width: int = DEFAULT_CANVAS_WIDTH,
        height: int = DEFAULT_CANVAS_HEIGHT,
        background: QColor | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._canvas_size = QSizeF(width, height)
        self.setSceneRect(QRectF(0, 0, width, height))

        if background is None:
            background = QColor("white")
        self.setBackgroundBrush(background)

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
    def canvas_size(self) -> QSizeF:
        return QSizeF(self._canvas_size)

    def set_canvas_size(self, size: QSizeF) -> None:
        """Resize the logical canvas."""
        self._canvas_size = QSizeF(size)
        self.setSceneRect(QRectF(0, 0, size.width(), size.height()))
        self.canvas_size_changed.emit(self._canvas_size)
