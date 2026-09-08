"""Undoable library file operations (Library PRD Section 10)."""

from __future__ import annotations

from pathlib import Path

from snapmock.core.command_stack import BaseCommand
from snapmock.library.manager import LibraryManager, send_to_system_trash


class RenameLibraryFileCommand(BaseCommand):
    """Rename a library file on disk and in its manifest."""

    def __init__(self, manager: LibraryManager, path: Path, new_name: str) -> None:
        self._manager = manager
        self._old_path = path
        self._old_name = path.stem
        self._new_name = new_name
        self._new_path: Path | None = None

    def redo(self) -> None:
        self._new_path = self._manager.rename_file(self._old_path, self._new_name)

    def undo(self) -> None:
        if self._new_path is not None:
            self._manager.rename_file(self._new_path, self._old_name)

    @property
    def new_path(self) -> Path | None:
        return self._new_path

    @property
    def description(self) -> str:
        return f"Rename {self._old_name}"


class DeleteLibraryFileCommand(BaseCommand):
    """Delete files or folders through the session trash (Library PRD 10.2).

    ``redo`` moves each path into the manager's session trash; ``undo`` moves
    them back. ``discard`` sends whatever is still in the session trash to the
    system trash: the command can no longer be undone, so the files leave the
    library for good.
    """

    def __init__(self, manager: LibraryManager, paths: list[Path]) -> None:
        self._manager = manager
        self._paths = list(paths)
        self._trashed: list[tuple[Path, Path]] = []

    def redo(self) -> None:
        self._trashed = self._manager.trash_files(self._paths)

    def undo(self) -> None:
        restored = dict(self._manager.restore_files(self._trashed))
        self._paths = [restored.get(trashed, original) for original, trashed in self._trashed]
        self._trashed = []

    def discard(self) -> None:
        for _original, trashed in self._trashed:
            send_to_system_trash(trashed)
        self._trashed = []

    @property
    def paths(self) -> list[Path]:
        """Where the files are, or would be, in the library right now."""
        return list(self._paths)

    @property
    def trash_paths(self) -> list[Path]:
        """Where the files sit in the session trash while the delete stands."""
        return [trashed for _original, trashed in self._trashed]

    @property
    def description(self) -> str:
        if len(self._paths) == 1:
            return f"Delete {self._paths[0].stem}"
        return f"Delete {len(self._paths)} items"


class MoveLibraryFileCommand(BaseCommand):
    """Move files to another folder inside the library."""

    def __init__(self, manager: LibraryManager, paths: list[Path], dest: Path) -> None:
        self._manager = manager
        self._paths = list(paths)
        self._dest = dest
        self._moved: list[tuple[Path, Path]] = []

    def redo(self) -> None:
        self._moved = self._manager.move_files(self._paths, self._dest)

    def undo(self) -> None:
        for old, new in reversed(self._moved):
            self._manager.move_files([new], old.parent)

    @property
    def description(self) -> str:
        return f"Move {len(self._paths)} file(s)"


class CreateFolderCommand(BaseCommand):
    """Create a subfolder; undo removes it only while it is still empty."""

    def __init__(self, manager: LibraryManager, parent: Path, name: str = "New Folder") -> None:
        self._manager = manager
        self._parent = parent
        self._name = name
        self._created: Path | None = None
        self.undo_blocked_message: str | None = None

    def redo(self) -> None:
        self._created = self._manager.create_folder(self._parent, self._name)

    def undo(self) -> None:
        if self._created is None:
            return
        if not self._manager.remove_empty_folder(self._created):
            self.undo_blocked_message = (
                f'Folder "{self._created.name}" is not empty and was not removed.'
            )

    @property
    def created_path(self) -> Path | None:
        return self._created

    @property
    def description(self) -> str:
        return "New folder"
