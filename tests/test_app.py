"""Tests for the main application window."""

from snapmock.main_window import MainWindow


def test_main_window_title(main_window: MainWindow) -> None:
    """Window title should be set correctly."""
    assert "SnapMock" in main_window.windowTitle()
    assert "Untitled" in main_window.windowTitle()


def test_main_window_default_size(main_window: MainWindow) -> None:
    """Window should have a reasonable default size.

    Exact dimensions may differ from the requested 1200x800 due to
    display scaling, restored QSettings geometry, or window-manager
    constraints, so we only verify sensible minimums.
    """
    assert main_window.width() >= 800
    assert main_window.height() >= 600


def test_main_window_has_scene(main_window: MainWindow) -> None:
    """MainWindow should expose a SnapScene."""
    assert main_window.scene is not None


def test_main_window_has_view(main_window: MainWindow) -> None:
    """The active document's SnapView lives inside the central tab widget."""
    assert main_window.view is not None
    central = main_window.centralWidget()
    assert central is not None
    assert main_window.view.parent() is not None
    assert central.isAncestorOf(main_window.view)
