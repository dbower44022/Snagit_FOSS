"""Inline editor for a numbered step: the value and the label, over the badge (PRD 2.8).

Numbered Steps, Stamps & Emoji PRD Section 2.8: a double-click on a numbered step puts
an editable field over the badge; the user types a new number (or the custom text in text
mode), Tab moves to the label field, and Enter finishes. Escape finishes without applying
(kickoff Phase 1 step 4). The edit is one undo entry: a ModifyPropertyCommand per changed
property, wrapped in a MacroCommand when both change.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt, QTimer
from PyQt6.QtGui import QIntValidator, QKeyEvent
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QWidget

from snapmock.commands.macro_command import MacroCommand
from snapmock.commands.modify_property import ModifyPropertyCommand
from snapmock.config.constants import DisplayMode
from snapmock.core.command_stack import BaseCommand
from snapmock.core.theme_manager import current_theme
from snapmock.items.numbered_step_item import NumberedStepItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.core.view import SnapView

EDIT_HINT = "Type to change value. Tab: edit label. Enter/Escape: finish."
"""The status bar text while editing (PRD 2.11)."""
_MIN_VALUE_WIDTH = 48
_LABEL_WIDTH = 140


class StepInlineEditor(QWidget):
    """Two line edits over a numbered step: its value and its label."""

    def __init__(
        self,
        item: NumberedStepItem,
        view: SnapView,
        scene: SnapScene,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        viewport = view.viewport()
        super().__init__(viewport)
        self._item = item
        self._view = view
        self._scene = scene
        self._on_finished = on_finished
        self._finished = False
        self.setAccessibleName("Numbered step editor")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.value_edit = QLineEdit(self)
        self.value_edit.setAccessibleName("Step value")
        self.value_edit.setToolTip("The step's number, or its text in text mode")
        if item.display_mode is DisplayMode.TEXT:
            self.value_edit.setText(item.custom_text)
        else:
            self.value_edit.setText(str(item.number_value))
            self.value_edit.setValidator(QIntValidator(0, 9999, self.value_edit))
        self.value_edit.setMinimumWidth(_MIN_VALUE_WIDTH)
        self.label_edit = QLineEdit(self)
        self.label_edit.setAccessibleName("Step label")
        self.label_edit.setToolTip("The label beside the badge; empty for none")
        self.label_edit.setPlaceholderText("Label")
        self.label_edit.setText(item.label_text)
        self.label_edit.setFixedWidth(_LABEL_WIDTH)
        layout.addWidget(self.value_edit)
        layout.addWidget(self.label_edit)
        accent = current_theme().accent.name()
        self.setStyleSheet(
            f"QLineEdit {{ background: rgba(255, 255, 255, 230); border: 1px solid {accent}; }}"
        )
        for edit in (self.value_edit, self.label_edit):
            edit.installEventFilter(self)
            edit.returnPressed.connect(self.finish)
        self.reposition()
        self.show()
        self.value_edit.setFocus()
        self.value_edit.selectAll()

    @property
    def item(self) -> NumberedStepItem:
        return self._item

    def reposition(self) -> None:
        """Place the editor over the badge in viewport coordinates."""
        badge = self._item.mapToScene(self._item.badge_rect())
        rect = QRectF(self._view.mapFromScene(badge).boundingRect())
        width = max(int(rect.width()), _MIN_VALUE_WIDTH) + _LABEL_WIDTH + 8
        height = max(int(rect.height()), 24)
        self.setGeometry(int(rect.left()), int(rect.center().y() - height / 2), width, height)

    # --- keys ---

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:  # noqa: N802
        if event is None:
            return False
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.cancel()
                return True
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                other = self.label_edit if watched is self.value_edit else self.value_edit
                other.setFocus()
                other.selectAll()
                return True
        elif event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self._finish_if_focus_left)
        return False

    def _finish_if_focus_left(self) -> None:
        focus = QApplication.focusWidget()
        if focus is not self.value_edit and focus is not self.label_edit:
            self.finish()

    # --- finishing ---

    def _commands(self) -> list[BaseCommand]:
        item = self._item
        commands: list[BaseCommand] = []
        value = self.value_edit.text()
        if item.display_mode is DisplayMode.TEXT:
            if value != item.custom_text:
                commands.append(
                    ModifyPropertyCommand(item, "custom_text", item.custom_text, value)
                )
        elif value.strip().isdigit() and int(value) != item.number_value:
            commands.append(
                ModifyPropertyCommand(item, "number_value", item.number_value, int(value))
            )
        label = self.label_edit.text()
        if label != item.label_text:
            commands.append(ModifyPropertyCommand(item, "label_text", item.label_text, label))
        return commands

    def finish(self) -> None:
        """Apply the edit as one undo entry and close (Enter, or focus left)."""
        if self._finished:
            return
        self._finished = True
        commands = self._commands()
        if len(commands) == 1:
            self._scene.command_stack.push(commands[0])
        elif commands:
            self._scene.command_stack.push(MacroCommand(commands, "Edit step"))
        self._close()

    def cancel(self) -> None:
        """Close without applying (Escape)."""
        if self._finished:
            return
        self._finished = True
        self._close()

    def _close(self) -> None:
        for edit in (self.value_edit, self.label_edit):
            edit.removeEventFilter(self)
        self.hide()
        self.setParent(None)
        self.deleteLater()
        if self._on_finished is not None:
            self._on_finished()
