"""Tests for the main application window."""

from snagit_foss.app import MainWindow


def test_main_window_title(main_window: MainWindow) -> None:
    """Window title should be set correctly."""
    assert main_window.windowTitle() == "Snagit FOSS"


def test_main_window_default_size(main_window: MainWindow) -> None:
    """Window should have the expected default size."""
    assert main_window.width() == 800
    assert main_window.height() == 600
