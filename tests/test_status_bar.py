"""The status bar zones of General UI PRD Section 9."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSizeF
from PyQt6.QtWidgets import QToolButton

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.document import Document
from snapmock.core.process_memory import MEGABYTE
from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.ui import status_bar as status_bar_module
from snapmock.ui.status_bar import (
    CANVAS_ZONE_WIDTH,
    CURSOR_ZONE_WIDTH,
    MEMORY_REFRESH_MS,
    MEMORY_ZONE_WIDTH,
    SELECTION_ZONE_WIDTH,
    STATUS_BAR_HEIGHT,
    ZOOM_ZONE_WIDTH,
    SnapStatusBar,
)
from snapmock.ui.toolbar import ZOOM_PRESETS


def _bar(window: MainWindow) -> SnapStatusBar:
    return window._status_bar  # noqa: SLF001


def _add_rect(window: MainWindow, x: float = 0, y: float = 0) -> RectangleItem:
    scene = window.scene
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 200, 150))
    item.setPos(x, y)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def test_zone_widths_and_height(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    assert bar.height() == STATUS_BAR_HEIGHT == 24
    assert bar._cursor_label.width() == CURSOR_ZONE_WIDTH == 120  # noqa: SLF001
    assert bar._selection_label.width() == SELECTION_ZONE_WIDTH == 120  # noqa: SLF001
    assert bar._canvas_label.width() == CANVAS_ZONE_WIDTH == 140  # noqa: SLF001
    assert bar._zoom_button.width() == ZOOM_ZONE_WIDTH == 80  # noqa: SLF001
    assert bar.memory_label.width() == MEMORY_ZONE_WIDTH == 80
    assert MEMORY_REFRESH_MS == 5_000


def test_cursor_and_canvas_formats(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    bar.update_cursor_pos(1234.4, 567.0)
    assert bar._cursor_label.text() == "X: 1234 Y: 567"  # noqa: SLF001
    size = main_window.scene.canvas_size
    assert bar._canvas_label.text() == f"Canvas: {size.width():.0f} x {size.height():.0f}"  # noqa: SLF001
    main_window.scene.set_canvas_size(QSizeF(1920, 1080))
    assert bar._canvas_label.text() == "Canvas: 1920 x 1080"  # noqa: SLF001


def test_selection_size_blank_until_selected(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    assert bar._selection_label.text() == ""  # noqa: SLF001
    item = _add_rect(main_window)
    main_window.selection_manager.select_items([item])
    assert bar._selection_label.text() == "W: 202 H: 152"  # noqa: SLF001
    other = _add_rect(main_window, 100, 100)
    main_window.selection_manager.select_items([item, other])
    assert bar._selection_label.text() == "W: 302 H: 252"  # noqa: SLF001
    main_window.selection_manager.deselect_all()
    assert bar._selection_label.text() == ""  # noqa: SLF001


def test_zoom_zone_is_a_clickable_preset_menu(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    assert isinstance(bar._zoom_button, QToolButton)  # noqa: SLF001
    assert bar._zoom_button.text() == "100%"  # noqa: SLF001
    main_window.view.set_zoom(150)
    assert bar._zoom_button.text() == "150%"  # noqa: SLF001
    menu = bar.zoom_menu()
    labels = [a.text() for a in menu.actions()]
    assert labels == [f"{p}%" for p in ZOOM_PRESETS]
    assert [a.text() for a in menu.actions() if a.isChecked()] == ["150%"]
    menu.actions()[labels.index("400%")].trigger()
    assert main_window.view.zoom_percent == 400
    assert bar._zoom_button.text() == "400%"  # noqa: SLF001
    assert bar.zoom_menu().actions()[labels.index("400%")].isChecked()


def test_memory_zone_text_and_colour_roles(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    label = bar.memory_label
    assert label.text().endswith(" MB")
    bar.set_memory_bytes(128 * MEGABYTE)
    assert label.text() == "128 MB"
    assert label.property("role") == ""
    bar.set_memory_bytes(700 * MEGABYTE)
    assert label.property("role") == "warning"
    bar.set_memory_bytes(1500 * MEGABYTE)
    assert label.text() == "1,500 MB"
    assert label.property("role") == "error"
    bar.set_memory_bytes(None)
    assert label.text() == "—"
    assert label.property("role") == ""


def test_memory_refresh_reads_the_process(main_window: MainWindow, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bar = _bar(main_window)
    monkeypatch.setattr(status_bar_module, "process_memory_bytes", lambda: 900 * MEGABYTE)
    bar.refresh_memory()
    assert bar.memory_label.text() == "900 MB"
    assert bar.memory_label.property("role") == "warning"
    assert bar._memory_timer.isActive()  # noqa: SLF001
    assert bar._memory_timer.interval() == MEMORY_REFRESH_MS  # noqa: SLF001


def test_zones_follow_the_active_tab(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    item = _add_rect(main_window)
    main_window.selection_manager.select_items([item])
    main_window.view.set_zoom(200)
    second = Document(SnapScene(800, 600), parent=main_window)
    main_window._add_document(second)  # noqa: SLF001
    assert bar._zoom_button.text() == "100%"  # noqa: SLF001
    assert bar._selection_label.text() == ""  # noqa: SLF001
    assert bar._canvas_label.text() == "Canvas: 800 x 600"  # noqa: SLF001
    main_window.documents.set_active_index(0)
    assert bar._zoom_button.text() == "200%"  # noqa: SLF001
    assert bar._selection_label.text() == "W: 202 H: 152"  # noqa: SLF001
