"""Tests for Document, DocumentManager, and tabbed editing in MainWindow."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRectF
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.document import Document
from snapmock.core.document_manager import DocumentManager
from snapmock.core.scene import SnapScene
from snapmock.io.project_serializer import save_project
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow


def _add_rect(scene: SnapScene) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(
        AddItemCommand(scene, RectangleItem(rect=QRectF(0, 0, 10, 10)), layer.layer_id)
    )


# --- Document ---


def test_document_defaults(qtbot: QtBot) -> None:
    doc = Document(SnapScene())
    assert doc.display_name == "Untitled"
    assert doc.file_path is None
    assert doc.is_dirty is False
    assert doc.tab_title == "Untitled"
    assert doc.view.scene() is doc.scene


def test_document_dirty_marks_tab_title(qtbot: QtBot) -> None:
    doc = Document(SnapScene())
    _add_rect(doc.scene)
    assert doc.is_dirty is True
    assert doc.tab_title == "*Untitled"


def test_library_document_never_dirty(qtbot: QtBot) -> None:
    doc = Document(SnapScene(), file_path=Path("/tmp/x.smk"), is_library_file=True)
    _add_rect(doc.scene)
    assert doc.is_dirty is False
    assert doc.tab_title == "x"


def test_document_display_name_from_path(qtbot: QtBot) -> None:
    doc = Document(SnapScene(), file_path=Path("/tmp/shot.smk"))
    assert doc.display_name == "shot"
    doc.display_name = "Renamed"
    assert doc.display_name == "Renamed"


# --- DocumentManager ---


def test_manager_add_activates_and_removes(qtbot: QtBot) -> None:
    dm = DocumentManager()
    a = Document(SnapScene())
    b = Document(SnapScene())
    dm.add(a)
    assert dm.active is a
    dm.add(b)
    assert dm.active is b
    assert dm.count == 2
    dm.remove(b)
    assert dm.active is a
    dm.remove(a)
    assert dm.active is None
    assert dm.count == 0


def test_manager_find_by_path_and_cycle(qtbot: QtBot, tmp_path: Path) -> None:
    dm = DocumentManager()
    p = tmp_path / "a.smk"
    a = Document(SnapScene(), file_path=p)
    b = Document(SnapScene())
    dm.add(a)
    dm.add(b)
    assert dm.find_by_path(p) is a
    assert dm.find_by_path(tmp_path / "zz.smk") is None
    dm.activate_next()
    assert dm.active is a
    dm.activate_previous()
    assert dm.active is b


def test_manager_move_reorders(qtbot: QtBot) -> None:
    dm = DocumentManager()
    a, b, c = Document(SnapScene()), Document(SnapScene()), Document(SnapScene())
    for d in (a, b, c):
        dm.add(d)
    dm.move(0, 2)
    assert dm.documents == [b, c, a]


# --- MainWindow integration ---


def test_window_starts_with_one_document(main_window: MainWindow) -> None:
    assert main_window.documents.count == 1
    assert main_window.active_document.display_name == "Untitled"
    assert not main_window._tabs.tab_bar.isVisible()  # noqa: SLF001


def test_file_new_opens_second_tab_when_first_is_touched(main_window: MainWindow) -> None:
    first = main_window.active_document
    _add_rect(first.scene)
    main_window._file_new()  # noqa: SLF001
    assert main_window.documents.count == 2
    assert main_window.active_document is not first
    assert main_window.scene is main_window.active_document.scene
    assert main_window._tabs.tab_bar.count() == 2  # noqa: SLF001


def test_file_new_replaces_pristine_untitled(main_window: MainWindow) -> None:
    first = main_window.active_document
    main_window._file_new()  # noqa: SLF001
    assert main_window.documents.count == 1
    assert main_window.active_document is not first


def test_open_project_reuses_tab_for_same_path(main_window: MainWindow, tmp_path: Path) -> None:
    scene = SnapScene(width=300, height=200)
    _add_rect(scene)
    path = tmp_path / "proj.smk"
    save_project(scene, path)

    doc = main_window._open_project(path)  # noqa: SLF001
    assert doc is not None
    assert main_window.active_document is doc
    assert main_window.scene.canvas_size.width() == 300
    assert "proj" in main_window.windowTitle()

    main_window._file_new()  # noqa: SLF001
    again = main_window._open_project(path)  # noqa: SLF001
    assert again is doc
    assert main_window.documents.count == 2


def test_switching_tabs_rebinds_tool_manager_and_panels(main_window: MainWindow) -> None:
    first = main_window.active_document
    _add_rect(first.scene)
    main_window._file_new()  # noqa: SLF001
    second = main_window.active_document
    tm = main_window.tool_manager
    assert tm._scene is second.scene  # noqa: SLF001
    assert main_window._layer_panel._layer_manager is second.scene.layer_manager  # noqa: SLF001

    main_window.documents.set_active(first)
    assert main_window.scene is first.scene
    assert tm._scene is first.scene  # noqa: SLF001
    assert tm._selection_manager is first.selection_manager  # noqa: SLF001
    assert main_window._property_panel._scene is first.scene  # noqa: SLF001
    assert main_window._status_bar._view is first.view  # noqa: SLF001
    assert main_window.windowTitle().startswith("*Untitled")


def test_each_tab_has_independent_undo(main_window: MainWindow) -> None:
    first = main_window.active_document
    _add_rect(first.scene)
    main_window._file_new()  # noqa: SLF001
    second = main_window.active_document
    assert second.scene.command_stack.can_undo is False
    assert first.scene.command_stack.can_undo is True


def test_close_last_tab_keeps_one_untitled(main_window: MainWindow) -> None:
    only = main_window.active_document
    assert main_window._close_document(only)  # noqa: SLF001
    assert main_window.documents.count == 1
    assert main_window.active_document is not only
    assert main_window.active_document.display_name == "Untitled"


def test_close_clean_tab_without_prompt(main_window: MainWindow) -> None:
    first = main_window.active_document
    _add_rect(first.scene)
    main_window._file_new()  # noqa: SLF001
    second = main_window.active_document
    assert main_window._close_document(second)  # noqa: SLF001
    assert main_window.documents.count == 1
    assert main_window.active_document is first


def test_redo_and_deselect_follow_the_active_document(qtbot: QtBot) -> None:
    """Edit > Redo and Edit > Deselect act on the active tab, not the first one."""
    window = MainWindow()
    qtbot.addWidget(window)
    first = window.active_document
    window._file_new()  # noqa: SLF001
    second = window.active_document
    assert second is not first
    layer = second.scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 10, 10))
    second.scene.command_stack.push(AddItemCommand(second.scene, item, layer.layer_id))
    second.selection_manager.select(item)
    assert second.selection_manager.count == 1
    window._edit_deselect()  # noqa: SLF001
    assert second.selection_manager.count == 0
    second.scene.command_stack.undo()
    assert not second.scene.command_stack.can_undo
    window._edit_redo()  # noqa: SLF001
    assert second.scene.command_stack.can_undo
    assert not first.scene.command_stack.can_undo
    second.scene.command_stack.mark_clean()
