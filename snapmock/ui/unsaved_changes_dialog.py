"""The Unsaved Changes dialog of General UI PRD Section 11.7, with the canvas preview.

A ``QMessageBox`` cannot hold a preview, so this is a small ``QDialog`` with
the same wording and the same three buttons. :meth:`result_button` reports the
choice as the ``QMessageBox.StandardButton`` the close path already handles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from snapmock.core.render_engine import RenderEngine

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene

PREVIEW_MAX = 200
"""Longest side of the canvas preview, in pixels."""

StandardButton = QMessageBox.StandardButton


def message_text(name: str) -> str:
    """The Section 11.7 wording for the document called *name*."""
    return f"You have unsaved changes to {name}. Do you want to save before closing?"


def render_preview(scene: SnapScene, longest_side: int = PREVIEW_MAX) -> QPixmap:
    """The canvas rendered small enough to fit *longest_side*."""
    rect = scene.canvas_rect
    scale = min(1.0, longest_side / max(1.0, rect.width()), longest_side / max(1.0, rect.height()))
    image = RenderEngine(scene).render_region(rect, scene.background_color, scale)
    return QPixmap.fromImage(image)


class UnsavedChangesDialog(QDialog):
    """Save, Don't Save, Cancel over a preview of the document's canvas."""

    def __init__(self, name: str, scene: SnapScene | None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Unsaved Changes")
        self.setAccessibleName("Unsaved Changes")
        self._result = StandardButton.Cancel
        self._buttons: dict[StandardButton, QPushButton] = {}

        outer = QVBoxLayout(self)
        body = QHBoxLayout()
        self._preview = QLabel()
        self._preview.setAccessibleName("Canvas preview")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        if scene is not None:
            self._preview.setPixmap(render_preview(scene))
            body.addWidget(self._preview)
        self._text = QLabel(message_text(name))
        self._text.setWordWrap(True)
        self._text.setMinimumWidth(260)
        self._text.setAccessibleName("Message")
        body.addWidget(self._text, 1)
        outer.addLayout(body)

        box = QDialogButtonBox()
        save = box.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        discard = box.addButton("Don't Save", QDialogButtonBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        for button, kind in (
            (save, StandardButton.Save),
            (discard, StandardButton.Discard),
            (cancel, StandardButton.Cancel),
        ):
            if button is None:
                continue
            button.setAccessibleName(button.text())
            button.clicked.connect(lambda _c=False, k=kind: self._choose(k))
            self._buttons[kind] = button
        if save is not None:
            save.setDefault(True)
        outer.addWidget(box)

    def text(self) -> str:
        """The message, as a ``QMessageBox`` would report it."""
        return self._text.text()

    def button(self, kind: StandardButton) -> QPushButton | None:
        """The Save, Discard (shown as Don't Save), or Cancel button."""
        return self._buttons.get(kind)

    @property
    def preview_label(self) -> QLabel:
        return self._preview

    def result_button(self) -> StandardButton:
        """Save, Discard, or Cancel; Cancel when the dialog was closed any other way."""
        return self._result

    def _choose(self, kind: StandardButton) -> None:
        self._result = kind
        if kind is StandardButton.Cancel:
            self.reject()
        else:
            self.accept()
