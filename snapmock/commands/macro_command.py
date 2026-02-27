"""MacroCommand groups multiple sub-commands into a single undoable unit."""

from snapmock.core.command_stack import BaseCommand


class MacroCommand(BaseCommand):
    """A composite command that executes/undoes a sequence of sub-commands."""

    def __init__(self, commands: list[BaseCommand], description: str = "Macro") -> None:
        self._commands = list(commands)
        self._description = description

    def redo(self) -> None:
        for cmd in self._commands:
            cmd.redo()

    def undo(self) -> None:
        for cmd in reversed(self._commands):
            cmd.undo()

    @property
    def description(self) -> str:
        return self._description
