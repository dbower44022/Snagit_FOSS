"""Shared pytest fixtures."""

import pytest
from pytestqt.qtbot import QtBot

from snagit_foss.app import MainWindow


@pytest.fixture()
def main_window(qtbot: QtBot) -> MainWindow:
    """Create a MainWindow instance managed by qtbot."""
    window = MainWindow()
    qtbot.addWidget(window)
    return window
