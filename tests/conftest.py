"""Shared pytest fixtures."""

import pytest
from pytestqt.qtbot import QtBot

from snapmock.core.scene import SnapScene
from snapmock.core.view import SnapView
from snapmock.main_window import MainWindow


@pytest.fixture()
def main_window(qtbot: QtBot) -> MainWindow:
    """Create a MainWindow instance managed by qtbot.

    On teardown every open document is marked clean first so the
    unsaved-changes prompt in ``closeEvent`` never blocks the test run.
    """
    window = MainWindow()

    def _mark_all_clean(w: MainWindow) -> None:
        for doc in w.documents.documents:
            doc.scene.command_stack.mark_clean()

    qtbot.addWidget(window, before_close_func=_mark_all_clean)
    return window


@pytest.fixture()
def scene() -> SnapScene:
    """Create a bare SnapScene (no view needed)."""
    return SnapScene()


@pytest.fixture()
def view(qtbot: QtBot, scene: SnapScene) -> SnapView:
    """Create a SnapView attached to a SnapScene."""
    v = SnapView(scene)
    qtbot.addWidget(v)
    return v
