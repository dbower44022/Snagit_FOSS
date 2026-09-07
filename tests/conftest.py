"""Shared pytest fixtures."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from snapmock.config import settings as settings_module
from snapmock.core.scene import SnapScene
from snapmock.core.view import SnapView
from snapmock.main_window import MainWindow


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AppSettings at a throwaway INI file and a temporary library.

    Keeps the test run from touching the real QSettings store or creating
    ``~/SnapMock/Library`` on the developer's machine.
    """
    ini = tmp_path / "settings.ini"
    library_dir = tmp_path / "Library"

    def _init(self: settings_module.AppSettings) -> None:
        self._qs = QSettings(str(ini), QSettings.Format.IniFormat)

    monkeypatch.setattr(settings_module.AppSettings, "__init__", _init)
    settings_module.AppSettings().set_library_directory(library_dir)
    return library_dir


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
