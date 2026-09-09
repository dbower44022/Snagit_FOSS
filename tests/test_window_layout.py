"""Window management: layout persistence, Reset Layout, last-used tool, Unsaved Changes."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtWidgets import QDockWidget, QMessageBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.settings import AppSettings
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.ui.unsaved_changes_dialog import UnsavedChangesDialog


def test_docks_and_toolbars_have_object_names_for_state_persistence(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    names = {w.objectName() for w in window.findChildren(QDockWidget)}
    assert {"LayerPanel", "PropertyPanel", "LibraryPanel"} <= names
    assert window._toolbar.objectName() == "ToolPalette"  # noqa: SLF001
    assert window._tool_options.objectName() == "ToolOptionsBar"  # noqa: SLF001


def test_reset_layout_restores_hidden_panels_and_default_area(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._layer_panel.hide()  # noqa: SLF001
    window._toolbar.hide()  # noqa: SLF001
    window.removeDockWidget(window._property_panel)  # noqa: SLF001
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, window._property_panel)  # noqa: SLF001
    window._status_bar_action.setChecked(False)  # noqa: SLF001
    window._view_reset_layout()  # noqa: SLF001
    assert window._layer_panel.isVisibleTo(window)  # noqa: SLF001
    assert window._toolbar.isVisibleTo(window)  # noqa: SLF001
    assert window.dockWidgetArea(window._property_panel) == (  # noqa: SLF001
        Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert window._status_bar_action.isChecked()  # noqa: SLF001


def test_last_used_tool_is_saved_and_restored(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.tool_manager.activate("rectangle")
    window._save_window_state()  # noqa: SLF001
    assert AppSettings().last_tool() == "rectangle"
    second = MainWindow()
    qtbot.addWidget(second)
    assert second.tool_manager.active_tool_id == "rectangle"


def test_transient_tools_are_not_restored(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.tool_manager.activate("rectangle")
    window._save_window_state()  # noqa: SLF001
    window.tool_manager.activate("pan")
    window._save_window_state()  # noqa: SLF001
    assert AppSettings().last_tool() == "rectangle"


def test_unsaved_changes_dialog_wording_and_dont_save(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    doc = window.active_document
    layer = doc.scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 10, 10))
    doc.scene.command_stack.push(AddItemCommand(doc.scene, item, layer.layer_id))
    assert doc.is_dirty
    seen: dict[str, str] = {}

    def _exec(box: UnsavedChangesDialog) -> int:
        seen["text"] = box.text()
        discard = box.button(QMessageBox.StandardButton.Discard)
        assert discard is not None
        seen["discard"] = discard.text()
        discard.click()
        return 0

    monkeypatch.setattr(UnsavedChangesDialog, "exec", _exec)
    assert window._maybe_save_before_close(doc) is True  # noqa: SLF001
    assert seen["text"] == (
        "You have unsaved changes to Untitled. Do you want to save before closing?"
    )
    assert seen["discard"] == "Don't Save"
    doc.scene.command_stack.mark_clean()
