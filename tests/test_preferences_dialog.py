"""Tests for the Preferences dialog (General UI PRD 11.3) and how its changes apply."""

from __future__ import annotations

from PyQt6.QtGui import QColor
from pytestqt.qtbot import QtBot

from snapmock.config.settings import AppSettings
from snapmock.core.theme_manager import reset_theme_manager, theme_manager
from snapmock.main_window import MainWindow
from snapmock.ui.preferences_dialog import (
    CATEGORY_APPEARANCE,
    CATEGORY_CANVAS,
    CATEGORY_CAPTURE,
    CATEGORY_GENERAL,
    CATEGORY_LIBRARY,
    CATEGORY_PERFORMANCE,
    CATEGORY_TOOLS,
    PreferencesDialog,
)


def _dialog(qtbot: QtBot, settings: AppSettings | None = None) -> PreferencesDialog:
    dlg = PreferencesDialog(settings or AppSettings())
    qtbot.addWidget(dlg)
    return dlg


class TestLayout:
    def test_sidebar_lists_every_category_in_order(self, qtbot: QtBot) -> None:
        dlg = _dialog(qtbot)
        titles = [dlg._sidebar.item(i).text() for i in range(dlg._sidebar.count())]  # type: ignore[union-attr]
        assert titles == [
            CATEGORY_GENERAL,
            CATEGORY_APPEARANCE,
            CATEGORY_CANVAS,
            CATEGORY_TOOLS,
            CATEGORY_LIBRARY,
            CATEGORY_PERFORMANCE,
        ]
        assert CATEGORY_CAPTURE not in titles

    def test_sidebar_switches_the_page(self, qtbot: QtBot) -> None:
        dlg = _dialog(qtbot)
        dlg.show_category(CATEGORY_TOOLS)
        assert dlg._stack.currentWidget() is dlg._pages[CATEGORY_TOOLS]
        dlg.focus_library_section()
        assert dlg._stack.currentWidget() is dlg._pages[CATEGORY_LIBRARY]

    def test_no_control_is_disabled(self, qtbot: QtBot) -> None:
        from PyQt6.QtWidgets import QWidget

        dlg = _dialog(qtbot)
        disabled = [w for w in dlg.findChildren(QWidget) if not w.isEnabledTo(dlg)]
        assert disabled == []


class TestInitialValues:
    def test_general_defaults(self, qtbot: QtBot) -> None:
        dlg = _dialog(qtbot)
        assert dlg._language_combo.currentData() == "en"
        assert dlg._autosave_interval_spin.value() == 2
        assert dlg._recent_count_spin.value() == 10
        assert (dlg._canvas_width_spin.value(), dlg._canvas_height_spin.value()) == (1920, 1080)
        assert dlg._canvas_color.color.name().upper() == "#FFFFFF"
        assert dlg._pasteboard_field.value() is None
        assert dlg._confirm_delete_cb.isChecked() is True

    def test_autosave_off_shows_zero(self, qtbot: QtBot) -> None:
        settings = AppSettings()
        settings.set_autosave_enabled(False)
        dlg = _dialog(qtbot, settings)
        assert dlg._autosave_interval_spin.value() == 0
        assert dlg._autosave_interval_spin.text() == "Disabled"

    def test_appearance_defaults(self, qtbot: QtBot) -> None:
        dlg = _dialog(qtbot)
        assert dlg._theme_combo.currentData() == "light"
        assert dlg._icon_size_combo.currentData() == 24
        assert dlg._checkerboard_size_combo.currentData() == 8
        assert dlg._checker_a.value() is None
        assert dlg._ui_font_combo.currentData() == "medium"

    def test_canvas_defaults(self, qtbot: QtBot) -> None:
        dlg = _dialog(qtbot)
        assert dlg._grid_size_spin.value() == 10
        assert dlg._grid_color_field.value() is None
        assert dlg._grid_opacity_follow.isChecked() is True
        assert dlg._grid_opacity_slider.value() == 20
        assert dlg._snap_tolerance_spin.value() == 5
        assert dlg._pixel_grid_spin.value() == 800
        assert dlg._guide_color.color.name().upper() == "#00BFFF"
        assert dlg._guide_opacity_slider.value() == 70
        assert dlg._layer_hover_cb.isChecked() is True

    def test_tools_and_performance_defaults(self, qtbot: QtBot) -> None:
        dlg = _dialog(qtbot)
        assert dlg._stroke_color.color.name().upper() == "#FF0000"
        assert dlg._stroke_width_spin.value() == 2.0
        assert dlg._fill_color.color.alpha() == 0
        assert dlg._font_size_spin.value() == 14
        assert dlg._smoothing_slider.value() == 50
        assert dlg._step_start_spin.value() == 1
        assert dlg._undo_limit_spin.value() == 200
        assert dlg._thumbnail_delay_spin.value() == 500

    def test_stored_values_are_shown(self, qtbot: QtBot) -> None:
        settings = AppSettings()
        settings.set_theme_mode("dark")
        settings.set_grid_color(QColor("#123456"))
        settings.set_grid_opacity(35)
        settings.set_pasteboard_color(QColor("#808080"))
        settings.set_undo_limit(50)
        dlg = _dialog(qtbot, settings)
        assert dlg._theme_combo.currentData() == "dark"
        assert dlg._grid_color_field.value() == QColor("#123456")
        assert dlg._grid_opacity_slider.value() == 35
        assert dlg._grid_opacity_follow.isChecked() is False
        assert dlg._pasteboard_field.value() == QColor("#808080")
        assert dlg._undo_limit_spin.value() == 50


class TestGetChanges:
    def test_empty_when_nothing_modified(self, qtbot: QtBot) -> None:
        assert _dialog(qtbot).get_changes() == {}

    def test_reports_only_changed_keys(self, qtbot: QtBot) -> None:
        dlg = _dialog(qtbot)
        dlg._autosave_interval_spin.setValue(0)
        dlg._grid_size_spin.setValue(40)
        dlg._theme_combo.setCurrentIndex(1)
        dlg._pasteboard_field.set_value(QColor("#808080"))
        dlg._grid_opacity_follow.setChecked(False)
        changes = dlg.get_changes()
        assert changes["autosave_interval"] == (2, 0)
        assert changes["grid_size"] == (10, 40)
        assert changes["theme_mode"] == ("light", "dark")
        assert changes["pasteboard_color"] == (None, QColor("#808080"))
        assert changes["grid_opacity"] == (None, 20)
        assert len(changes) == 5


class TestApply:
    def test_general_and_performance_changes_persist(self, main_window: MainWindow) -> None:
        main_window._apply_preference_changes(
            {
                "autosave_interval": (2, 0),
                "recent_files_count": (10, 3),
                "default_canvas_size": ((1920, 1080), (640, 480)),
                "default_canvas_color": (QColor("#FFFFFF"), QColor("#112233")),
                "confirm_delete_layers": (True, False),
                "undo_limit": (200, 25),
                "thumbnail_delay_ms": (500, 900),
            }
        )
        s = AppSettings()
        assert s.autosave_enabled() is False
        assert s.recent_files_count() == 3
        assert s.default_canvas_size() == (640, 480)
        assert s.default_canvas_color().name().upper() == "#112233"
        assert s.confirm_delete_layers() is False
        assert s.undo_limit() == 25
        assert s.thumbnail_delay_ms() == 900
        assert main_window._scene.command_stack.limit == 25
        main_window._file_new()
        assert main_window._scene.canvas_rect.width() == 640
        assert main_window._scene.background_color.name().upper() == "#112233"

    def test_autosave_interval_restarts_the_timer(self, main_window: MainWindow) -> None:
        main_window._apply_preference_changes({"autosave_interval": (2, 5)})
        assert AppSettings().autosave_interval_minutes() == 5
        assert main_window._autosave_timer.isActive()
        main_window._apply_preference_changes({"autosave_interval": (5, 0)})
        assert not main_window._autosave_timer.isActive()

    def test_appearance_changes_apply_live(self, main_window: MainWindow) -> None:
        reset_theme_manager()
        main_window._theme = theme_manager()
        main_window._apply_preference_changes(
            {
                "theme_mode": ("light", "dark"),
                "icon_size": (24, 32),
                "ui_font_size": ("medium", "large"),
                "checkerboard_size": (8, 16),
                "pasteboard_color": (None, QColor("#808080")),
                "grid_color": (None, QColor("#00FF00")),
                "grid_opacity": (None, 60),
                "pixel_grid_zoom": (800, 400),
            }
        )
        s = AppSettings()
        assert s.theme_mode() == "dark"
        assert s.icon_size() == 32
        assert s.ui_font_size() == "large"
        assert s.checkerboard_size() == 16
        assert s.pasteboard_color() == QColor("#808080")
        assert s.grid_color() == QColor("#00FF00")
        assert s.grid_opacity() == 60
        assert s.pixel_grid_zoom() == 400
        view = main_window._view
        assert view.pasteboard_color == QColor("#808080")
        minor, _major = view._grid_pens()
        assert minor.color().green() == 255
        assert minor.color().alpha() == round(60 * 2.55)
        assert view._pixel_grid_threshold == 400
        assert view._get_checkerboard_tile().width() == 32

    def test_tool_defaults_reach_the_tools(self, main_window: MainWindow) -> None:
        main_window._apply_preference_changes(
            {
                "default_stroke_color": (QColor("#FF0000"), QColor("#0000FF")),
                "default_stroke_width": (2.0, 5.0),
                "default_fill_color": (QColor(0, 0, 0, 0), QColor("#00FF00")),
                "default_font_family": ("Sans Serif", "Serif"),
                "default_font_size": (14, 22),
                "freehand_smoothing": (50, 80),
                "numbered_step_start": (1, 7),
            }
        )
        tm = main_window._tool_manager
        rect = tm.tool("rectangle")
        text = tm.tool("text")
        freehand = tm.tool("freehand")
        steps = tm.tool("numbered_step")
        assert rect is not None and text is not None
        assert freehand is not None and steps is not None
        assert rect.creation_defaults["stroke_color"] == QColor("#0000FF")
        assert rect.creation_defaults["stroke_width"] == 5.0
        assert rect.creation_defaults["fill_color"] == QColor("#00FF00")
        assert text.creation_defaults["font_family"] == "Serif"
        assert text.creation_defaults["font_size"] == 22
        assert freehand.creation_defaults["smoothing"] == 80
        assert steps.creation_defaults["start_number"] == 7
        tm.activate("numbered_step")
        assert steps.next_number == 7

    def test_tool_defaults_are_read_at_startup(self, qtbot: QtBot) -> None:
        settings = AppSettings()
        settings.set_default_stroke_color(QColor("#123456"))
        settings.set_numbered_step_start(3)
        settings.set_undo_limit(40)
        window = MainWindow()
        qtbot.addWidget(window)
        rect = window._tool_manager.tool("rectangle")
        assert rect is not None
        assert rect.creation_defaults["stroke_color"] == QColor("#123456")
        assert window._scene.command_stack.limit == 40

    def test_delete_layer_skips_the_confirmation_when_off(
        self, main_window: MainWindow, monkeypatch: object
    ) -> None:
        from PyQt6.QtCore import QRectF
        from PyQt6.QtWidgets import QMessageBox

        from snapmock.items.rectangle_item import RectangleItem

        main_window._layer_new()
        item = RectangleItem(QRectF(0, 0, 10, 10))
        from snapmock.commands.add_item import AddItemCommand

        lm = main_window._scene.layer_manager
        assert lm.active_layer is not None
        main_window._scene.command_stack.push(
            AddItemCommand(main_window._scene, item, lm.active_layer.layer_id)
        )
        AppSettings().set_confirm_delete_layers(False)
        asked: list[str] = []
        monkeypatch.setattr(  # type: ignore[attr-defined]
            QMessageBox, "question", staticmethod(lambda *a, **k: asked.append("asked"))
        )
        before = lm.count
        main_window._layer_delete()
        assert asked == []
        assert lm.count == before - 1
