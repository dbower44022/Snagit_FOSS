"""Tests for CommandStack and BaseCommand."""

from snapmock.commands.macro_command import MacroCommand
from snapmock.core.command_stack import BaseCommand, CommandStack


class IncrementCommand(BaseCommand):
    """Test command that increments/decrements a counter."""

    def __init__(self, counter: list[int], amount: int = 1) -> None:
        self._counter = counter
        self._amount = amount

    def redo(self) -> None:
        self._counter[0] += self._amount

    def undo(self) -> None:
        self._counter[0] -= self._amount

    @property
    def description(self) -> str:
        return f"Increment by {self._amount}"


class MergeableCommand(BaseCommand):
    """Test command that supports merging (accumulates value)."""

    MERGE_ID = 42

    def __init__(self, counter: list[int], amount: int = 1) -> None:
        self._counter = counter
        self._amount = amount
        self._old: int = 0

    def redo(self) -> None:
        self._old = self._counter[0]
        self._counter[0] += self._amount

    def undo(self) -> None:
        self._counter[0] = self._old

    @property
    def description(self) -> str:
        return f"Merge increment {self._amount}"

    @property
    def merge_id(self) -> int:
        return self.MERGE_ID

    def merge_with(self, other: BaseCommand) -> bool:
        if isinstance(other, MergeableCommand):
            self._amount += other._amount
            return True
        return False


def test_push_executes_command() -> None:
    counter = [0]
    stack = CommandStack()
    stack.push(IncrementCommand(counter))
    assert counter[0] == 1


def test_undo_reverses_command() -> None:
    counter = [0]
    stack = CommandStack()
    stack.push(IncrementCommand(counter))
    stack.undo()
    assert counter[0] == 0


def test_redo_reapplies_command() -> None:
    counter = [0]
    stack = CommandStack()
    stack.push(IncrementCommand(counter))
    stack.undo()
    stack.redo()
    assert counter[0] == 1


def test_undo_redo_flags() -> None:
    stack = CommandStack()
    assert not stack.can_undo
    assert not stack.can_redo
    stack.push(IncrementCommand([0]))
    assert stack.can_undo
    assert not stack.can_redo
    stack.undo()
    assert not stack.can_undo
    assert stack.can_redo


def test_push_clears_redo_history() -> None:
    counter = [0]
    stack = CommandStack()
    stack.push(IncrementCommand(counter, 10))
    stack.undo()
    stack.push(IncrementCommand(counter, 5))
    assert counter[0] == 5
    assert not stack.can_redo
    assert stack.count == 1


def test_stack_limit() -> None:
    counter = [0]
    stack = CommandStack(limit=3)
    for i in range(5):
        stack.push(IncrementCommand(counter, 1))
    assert stack.count == 3
    assert counter[0] == 5


def test_dirty_flag() -> None:
    stack = CommandStack()
    assert not stack.is_dirty
    stack.push(IncrementCommand([0]))
    assert stack.is_dirty
    stack.mark_clean()
    assert not stack.is_dirty
    stack.push(IncrementCommand([0]))
    assert stack.is_dirty


def test_undo_redo_text() -> None:
    stack = CommandStack()
    assert stack.undo_text == ""
    assert stack.redo_text == ""
    stack.push(IncrementCommand([0], 5))
    assert stack.undo_text == "Increment by 5"
    stack.undo()
    assert stack.redo_text == "Increment by 5"


def test_clear() -> None:
    counter = [0]
    stack = CommandStack()
    stack.push(IncrementCommand(counter))
    stack.clear()
    assert stack.count == 0
    assert not stack.can_undo


def test_merge_commands() -> None:
    counter = [0]
    stack = CommandStack()
    stack.push(MergeableCommand(counter, 3))
    stack.push(MergeableCommand(counter, 7))
    assert counter[0] == 10
    assert stack.count == 1  # merged into one
    stack.undo()
    assert counter[0] == 0


def test_macro_command() -> None:
    counter = [0]
    cmds = [IncrementCommand(counter, 1), IncrementCommand(counter, 2)]
    macro = MacroCommand(cmds, description="Add 3")
    stack = CommandStack()
    stack.push(macro)
    assert counter[0] == 3
    stack.undo()
    assert counter[0] == 0
