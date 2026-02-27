"""Undo/redo command infrastructure."""

from abc import ABC, abstractmethod

from PyQt6.QtCore import QObject, pyqtSignal

from snapmock.config.constants import UNDO_LIMIT


class BaseCommand(ABC):
    """Abstract base for all undoable commands."""

    @abstractmethod
    def redo(self) -> None:
        """Execute (or re-execute) the command."""

    @abstractmethod
    def undo(self) -> None:
        """Reverse the command."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the undo/redo menu."""

    @property
    def merge_id(self) -> int:
        """Return a non-zero id to enable merging with the previous command.

        Commands with the same non-zero merge_id are candidates for merging
        via :meth:`merge_with`. Return 0 (default) to disable merging.
        """
        return 0

    def merge_with(self, other: "BaseCommand") -> bool:
        """Attempt to merge *other* into this command.

        Return ``True`` if the merge was successful (and *other* should be
        discarded), ``False`` otherwise.  The default implementation never
        merges.
        """
        return False


class CommandStack(QObject):
    """Manages an ordered stack of :class:`BaseCommand` objects with undo/redo.

    Signals
    -------
    can_undo_changed(bool)
        Emitted when the ability to undo changes.
    can_redo_changed(bool)
        Emitted when the ability to redo changes.
    undo_text_changed(str)
        Emitted with the description of the next undo command (or empty string).
    redo_text_changed(str)
        Emitted with the description of the next redo command (or empty string).
    stack_changed()
        Emitted after any push/undo/redo/clear operation.
    """

    can_undo_changed = pyqtSignal(bool)
    can_redo_changed = pyqtSignal(bool)
    undo_text_changed = pyqtSignal(str)
    redo_text_changed = pyqtSignal(str)
    stack_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None, limit: int = UNDO_LIMIT) -> None:
        super().__init__(parent)
        self._commands: list[BaseCommand] = []
        self._index: int = 0  # points *past* the last executed command
        self._limit = limit
        self._clean_index: int = 0

    # --- public API ---

    def push(self, command: BaseCommand) -> None:
        """Execute *command* and push it onto the stack.

        Clears the redo history.  If the stack exceeds *limit*, the oldest
        command is dropped.
        """
        # Try merging with the top command
        if self._index > 0:
            top = self._commands[self._index - 1]
            if top.merge_id != 0 and top.merge_id == command.merge_id:
                if top.merge_with(command):
                    top.undo()
                    top.redo()
                    self._emit_signals()
                    return

        # Truncate any redo history
        del self._commands[self._index :]
        command.redo()
        self._commands.append(command)
        self._index += 1

        # Enforce limit
        if len(self._commands) > self._limit:
            excess = len(self._commands) - self._limit
            del self._commands[:excess]
            self._index -= excess
            self._clean_index = max(0, self._clean_index - excess)

        self._emit_signals()

    def undo(self) -> None:
        """Undo the most recent command, if any."""
        if not self.can_undo:
            return
        self._index -= 1
        self._commands[self._index].undo()
        self._emit_signals()

    def redo(self) -> None:
        """Redo the next command, if any."""
        if not self.can_redo:
            return
        self._commands[self._index].redo()
        self._index += 1
        self._emit_signals()

    def clear(self) -> None:
        """Remove all commands from the stack."""
        self._commands.clear()
        self._index = 0
        self._clean_index = 0
        self._emit_signals()

    def mark_clean(self) -> None:
        """Mark the current position as the clean (saved) state."""
        self._clean_index = self._index

    # --- queries ---

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return self._index < len(self._commands)

    @property
    def is_dirty(self) -> bool:
        return self._index != self._clean_index

    @property
    def undo_text(self) -> str:
        if self.can_undo:
            return self._commands[self._index - 1].description
        return ""

    @property
    def redo_text(self) -> str:
        if self.can_redo:
            return self._commands[self._index].description
        return ""

    @property
    def count(self) -> int:
        return len(self._commands)

    # --- internal ---

    def _emit_signals(self) -> None:
        self.can_undo_changed.emit(self.can_undo)
        self.can_redo_changed.emit(self.can_redo)
        self.undo_text_changed.emit(self.undo_text)
        self.redo_text_changed.emit(self.redo_text)
        self.stack_changed.emit()
