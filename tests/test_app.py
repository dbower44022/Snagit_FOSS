"""Tests for the main application window."""

from snapmock.main_window import MainWindow


def test_main_window_title(main_window: MainWindow) -> None:
    """Window title should be set correctly."""
    assert "SnapMock" in main_window.windowTitle()
    assert "Untitled" in main_window.windowTitle()


def test_main_window_default_size(main_window: MainWindow) -> None:
    """Window should have the expected default size."""
    assert main_window.width() == 1200
    assert main_window.height() == 800


def test_main_window_has_scene(main_window: MainWindow) -> None:
    """MainWindow should expose a SnapScene."""
    assert main_window.scene is not None


def test_main_window_has_view(main_window: MainWindow) -> None:
    """MainWindow should have a SnapView as central widget."""
    assert main_window.view is not None
    assert main_window.centralWidget() is main_window.view
