"""Shared pytest fixtures."""

import pytest
from pytestqt.qtbot import QtBot

from snapmock.core.scene import SnapScene
from snapmock.core.view import SnapView
from snapmock.main_window import MainWindow


@pytest.fixture()
def main_window(qtbot: QtBot) -> MainWindow:
    """Create a MainWindow instance managed by qtbot."""
    window = MainWindow()
    qtbot.addWidget(window)
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
