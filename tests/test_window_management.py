"""Multi-monitor recovery of floating panels (General UI PRD 15.3), the Unsaved Changes
dialog with its canvas preview (11.7), and the zoom level per recently opened project
(15.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QPoint, QRectF
from PyQt6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.settings import AppSettings
from snapmock.core.scene import SnapScene
from snapmock.io.project_serializer import save_project
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.ui.unsaved_changes_dialog import UnsavedChangesDialog, message_text, render_preview


def _dirty(window: MainWindow) -> None:
    doc = window.active_document
    layer = doc.scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, 10, 10))
    doc.scene.command_stack.push(AddItemCommand(doc.scene, item, layer.layer_id))
    assert doc.is_dirty


class TestFloatingPanels:
    def test_panel_off_every_screen_moves_to_the_primary_screen(
        self, main_window: MainWindow
    ) -> None:
        panel = main_window._layer_panel  # noqa: SLF001
        panel.setFloating(True)
        panel.move(QPoint(9000, 9000))
        main_window._recover_floating_panels()  # noqa: SLF001
        screen = QApplication.primaryScreen()
        assert screen is not None
        assert screen.availableGeometry().contains(panel.frameGeometry().topLeft())

    def test_panel_on_a_screen_is_left_alone(self, main_window: MainWindow) -> None:
        panel = main_window._property_panel  # noqa: SLF001
        panel.setFloating(True)
        panel.move(QPoint(120, 130))
        main_window._recover_floating_panels()  # noqa: SLF001
        assert panel.pos() == QPoint(120, 130)

    def test_docked_panels_are_untouched(self, main_window: MainWindow) -> None:
        panel = main_window._layer_panel  # noqa: SLF001
        assert not panel.isFloating()
        before = panel.pos()
        main_window._recover_floating_panels()  # noqa: SLF001
        assert panel.pos() == before


class TestUnsavedChangesDialog:
    def test_wording_buttons_and_preview(self, qtbot: QtBot, qapp: QApplication) -> None:
        scene = SnapScene(400, 200)
        dialog = UnsavedChangesDialog("Untitled", scene)
        qtbot.addWidget(dialog)
        assert dialog.text() == message_text("Untitled")
        assert dialog.text() == (
            "You have unsaved changes to Untitled. Do you want to save before closing?"
        )
        discard = dialog.button(QMessageBox.StandardButton.Discard)
        assert discard is not None and discard.text() == "Don't Save"
        save = dialog.button(QMessageBox.StandardButton.Save)
        assert save is not None and save.text() == "Save" and save.isDefault()
        cancel = dialog.button(QMessageBox.StandardButton.Cancel)
        assert cancel is not None and cancel.text() == "Cancel"
        pixmap = dialog.preview_label.pixmap()
        assert not pixmap.isNull()
        assert pixmap.width() == 200 and pixmap.height() == 100
        assert dialog.preview_label.accessibleName() == "Canvas preview"

    def test_preview_never_upscales(self, qapp: QApplication) -> None:
        pixmap = render_preview(SnapScene(50, 30))
        assert (pixmap.width(), pixmap.height()) == (50, 30)

    @pytest.mark.parametrize(
        ("kind", "expected"),
        [
            (QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Save),
            (QMessageBox.StandardButton.Discard, QMessageBox.StandardButton.Discard),
            (QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel),
        ],
    )
    def test_each_button_reports_itself(
        self,
        qtbot: QtBot,
        kind: QMessageBox.StandardButton,
        expected: QMessageBox.StandardButton,
    ) -> None:
        dialog = UnsavedChangesDialog("Shot", None)
        qtbot.addWidget(dialog)
        button = dialog.button(kind)
        assert button is not None
        button.click()
        assert dialog.result_button() is expected

    def test_closing_the_dialog_is_cancel(self, qtbot: QtBot) -> None:
        dialog = UnsavedChangesDialog("Shot", None)
        qtbot.addWidget(dialog)
        dialog.reject()
        assert dialog.result_button() is QMessageBox.StandardButton.Cancel

    def test_window_close_path_uses_the_dialog(
        self, main_window: MainWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _dirty(main_window)
        seen: dict[str, object] = {}

        def _exec(dialog: UnsavedChangesDialog) -> int:
            seen["text"] = dialog.text()
            seen["preview"] = not dialog.preview_label.pixmap().isNull()
            discard = dialog.button(QMessageBox.StandardButton.Discard)
            assert discard is not None
            discard.click()
            return 0

        monkeypatch.setattr(UnsavedChangesDialog, "exec", _exec)
        doc = main_window.active_document
        assert main_window._maybe_save_before_close(doc) is True  # noqa: SLF001
        assert seen["text"] == message_text("Untitled")
        assert seen["preview"] is True
        doc.scene.command_stack.mark_clean()


class TestZoomPerRecentProject:
    def test_settings_map_is_capped_and_newest_first(self) -> None:
        settings = AppSettings()
        for i in range(60):
            settings.set_recent_file_zoom(Path(f"/tmp/p{i}.smk"), 100 + i)
        assert settings.recent_file_zoom(Path("/tmp/p59.smk")) == 159
        assert settings.recent_file_zoom(Path("/tmp/p0.smk")) is None
        assert settings.recent_file_zoom(Path("/tmp/none.smk")) is None

    def test_zoom_is_restored_when_the_project_is_reopened(
        self, main_window: MainWindow, tmp_path: Path
    ) -> None:
        path = tmp_path / "shot.smk"
        save_project(SnapScene(300, 200), path)
        doc = main_window._open_project(path)  # noqa: SLF001
        assert doc is not None
        doc.view.set_zoom(250)
        assert main_window._close_document(doc) is True  # noqa: SLF001
        assert AppSettings().recent_file_zoom(path) == 250
        reopened = main_window._open_project(path)  # noqa: SLF001
        assert reopened is not None
        assert reopened.view.zoom_percent == 250

    def test_session_save_records_every_open_file(
        self, main_window: MainWindow, tmp_path: Path
    ) -> None:
        path = tmp_path / "shot.smk"
        save_project(SnapScene(300, 200), path)
        doc = main_window._open_project(path)  # noqa: SLF001
        assert doc is not None
        doc.view.set_zoom(150)
        main_window._save_session()  # noqa: SLF001
        assert AppSettings().recent_file_zoom(path) == 150
