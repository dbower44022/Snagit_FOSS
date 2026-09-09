"""Tests for canvas area features: pasteboard, grid, rulers, cursors, drag-and-drop."""

from PyQt6.QtCore import QRectF, Qt

from snapmock.config.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    EMPTY_CANVAS_TEXT,
    GRID_MAJOR_MULTIPLE,
    GRID_MINOR_MIN_ZOOM,
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
    # Raster select tool uses the crosshair-with-square pixmap cursor (PRD 6.6)
    main_window.tool_manager.activate("raster_select")
    assert vp.cursor().shape() == Qt.CursorShape.BitmapCursor
    main_window.tool_manager.activate("rectangle")
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


def test_empty_canvas_prompt_wording_follows_prd_6_2() -> None:
    assert EMPTY_CANVAS_TEXT == (
        "Drag an image here, paste from clipboard (Ctrl+V), or go to File > Import Image"
    )


def test_grid_major_lines_every_five_units() -> None:
    """PRD 6.4: major grid lines every 5 grid units."""
    assert GRID_MAJOR_MULTIPLE == 5


def test_minor_grid_lines_hide_below_200_percent(view: SnapView) -> None:
    """PRD 6.4: below 200 percent zoom only the major lines are drawn."""
    assert GRID_MINOR_MIN_ZOOM == 200
    view.set_grid_visible(True)
    view.set_zoom(100)
    assert not view.shows_minor_grid_lines
    view.set_zoom(200)
    assert view.shows_minor_grid_lines
    view.set_zoom(150)
    assert not view.shows_minor_grid_lines
    # Drawing at either zoom must still run cleanly.
    from PyQt6.QtGui import QImage, QPainter

    for zoom in (100, 400):
        view.set_zoom(zoom)
        image = QImage(200, 200, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        view.drawForeground(painter, QRectF(0, 0, 200, 200))
        painter.end()


# --- crosshairs (General UI PRD 3.3) ---


def test_crosshairs_follow_the_cursor_and_leave_with_it(view: SnapView) -> None:
    from PyQt6.QtCore import QPointF
    from PyQt6.QtTest import QTest

    view.resize(400, 300)
    view.show()
    assert not view.crosshairs_visible
    assert view.crosshair_pos is None
    view.set_crosshairs_visible(True)
    vp = view.viewport()
    assert vp is not None
    QTest.mouseMove(vp, vp.rect().center())
    pos = view.crosshair_pos
    assert pos is not None
    expected = view.mapToScene(vp.rect().center())
    assert abs(pos.x() - expected.x()) < 1 and abs(pos.y() - expected.y()) < 1
    # Painting with crosshairs on runs through the foreground path.
    from PyQt6.QtGui import QImage, QPainter

    image = QImage(200, 200, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    view.drawForeground(painter, QRectF(0, 0, 200, 200))
    painter.end()
    view.leaveEvent(None)
    assert view.crosshair_pos is None
    view._move_crosshairs(QPointF(10, 10))  # noqa: SLF001
    view.set_crosshairs_visible(False)
    assert view.crosshair_pos is None


def test_show_crosshairs_menu_toggle_applies_to_every_document_and_persists(
    main_window: "MainWindow",  # type: ignore[name-defined] # noqa: F821
) -> None:
    from snapmock.config.settings import AppSettings
    from snapmock.core.document import Document
    from snapmock.main_window import MainWindow

    assert isinstance(main_window, MainWindow)
    action = main_window._crosshairs_action  # noqa: SLF001
    assert action.isCheckable() and not action.isChecked()
    second = Document(SnapScene())
    main_window._add_document(second, activate=False)  # noqa: SLF001
    action.setChecked(True)
    assert all(d.view.crosshairs_visible for d in main_window.documents.documents)
    assert AppSettings().crosshairs_visible()
    third = Document(SnapScene())
    main_window._add_document(third, activate=False)  # noqa: SLF001
    assert third.view.crosshairs_visible
    action.setChecked(False)
    assert not any(d.view.crosshairs_visible for d in main_window.documents.documents)
    assert not AppSettings().crosshairs_visible()
