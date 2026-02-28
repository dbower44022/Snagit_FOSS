"""Tests for canvas area features: pasteboard, grid, rulers, cursors, drag-and-drop."""

from PyQt6.QtCore import QRectF, Qt

from snapmock.config.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    PASTEBOARD_MARGIN,
)
from snapmock.core.scene import SnapScene
from snapmock.core.view import SnapView


def test_scene_rect_includes_pasteboard(scene: SnapScene) -> None:
    """sceneRect must extend beyond the logical canvas by PASTEBOARD_MARGIN."""
    sr = scene.sceneRect()
    assert sr.left() == -PASTEBOARD_MARGIN
    assert sr.top() == -PASTEBOARD_MARGIN
    assert sr.width() == DEFAULT_CANVAS_WIDTH + 2 * PASTEBOARD_MARGIN
    assert sr.height() == DEFAULT_CANVAS_HEIGHT + 2 * PASTEBOARD_MARGIN


def test_canvas_rect_is_logical_canvas(scene: SnapScene) -> None:
    """canvas_rect should return (0, 0, w, h)."""
    cr = scene.canvas_rect
    assert cr == QRectF(0, 0, DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT)


def test_view_grid_toggle(view: SnapView) -> None:
    """Grid visibility should be toggleable."""
    assert view._grid_visible is False  # noqa: SLF001
    view.set_grid_visible(True)
    assert view._grid_visible is True  # noqa: SLF001
    view.set_grid_visible(False)
    assert view._grid_visible is False  # noqa: SLF001


def test_view_rulers_toggle(view: SnapView) -> None:
    """Ruler visibility should be toggleable."""
    assert view._rulers_visible is False  # noqa: SLF001
    view.set_rulers_visible(True)
    assert view._rulers_visible is True  # noqa: SLF001
    assert view._h_ruler is not None  # noqa: SLF001
    assert view._v_ruler is not None  # noqa: SLF001
    view.set_rulers_visible(False)
    assert view._rulers_visible is False  # noqa: SLF001


def test_cursor_applied_on_tool_change(main_window: "MainWindow") -> None:  # type: ignore[name-defined] # noqa: F821
    """Viewport cursor should match the active tool's cursor."""
    from snapmock.main_window import MainWindow

    assert isinstance(main_window, MainWindow)
    view = main_window.view
    vp = view.viewport()
    assert vp is not None
    # Select tool default is ArrowCursor
    main_window.tool_manager.activate("select")
    assert vp.cursor().shape() == Qt.CursorShape.ArrowCursor
    # Raster select tool uses CrossCursor
    main_window.tool_manager.activate("raster_select")
    assert vp.cursor().shape() == Qt.CursorShape.CrossCursor


def test_view_accepts_drops(view: SnapView) -> None:
    """View should accept drag-and-drop."""
    assert view.acceptDrops() is True


def test_draw_background_paints(view: SnapView) -> None:
    """drawBackground should execute without error."""
    from PyQt6.QtGui import QImage, QPainter

    image = QImage(200, 200, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    view.drawBackground(painter, QRectF(0, 0, 200, 200))
    painter.end()


def test_empty_canvas_prompt(view: SnapView) -> None:
    """An empty scene should trigger the prompt text path (no crash)."""
    snap = view._snap_scene  # noqa: SLF001
    assert snap is not None
    assert view._scene_has_no_user_items(snap) is True  # noqa: SLF001
