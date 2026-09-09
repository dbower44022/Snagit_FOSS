"""Responsive behaviour (General UI PRD 15.1, 15.2): panel collapse modes, thresholds,
the icon-strip popovers, and the Tool Options Bar overflow."""

from __future__ import annotations

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication, QToolButton, QWidget
from pytestqt.qtbot import QtBot

from snapmock.config.settings import AppSettings
from snapmock.main_window import MainWindow
from snapmock.ui.layer_panel import _RowRects
from snapmock.ui.panel_modes import (
    NARROW_PANEL_WIDTH,
    STRIP_PANEL_WIDTH,
    PanelMode,
    mode_for_width,
    panel_width_for,
)


def _defaults() -> None:
    """The PRD thresholds (the conftest floors them for every other test)."""
    settings = AppSettings()
    settings.set_panel_narrow_threshold(1280)
    settings.set_panel_strip_threshold(1024)


def _shown(qtbot: QtBot, width: int = 1400, height: int = 800) -> MainWindow:
    _defaults()
    window = MainWindow()

    def _clean(w: MainWindow) -> None:
        for doc in w.documents.documents:
            doc.scene.command_stack.mark_clean()

    qtbot.addWidget(window, before_close_func=_clean)
    window.show()
    window.resize(width, height)
    QApplication.processEvents()
    return window


class TestModeSelection:
    def test_thresholds(self) -> None:
        assert mode_for_width(1400, 1280, 1024) is PanelMode.FULL
        assert mode_for_width(1280, 1280, 1024) is PanelMode.FULL
        assert mode_for_width(1279, 1280, 1024) is PanelMode.NARROW
        assert mode_for_width(1025, 1280, 1024) is PanelMode.NARROW
        assert mode_for_width(1024, 1280, 1024) is PanelMode.ICON_STRIP
        assert mode_for_width(800, 1280, 1024) is PanelMode.ICON_STRIP

    def test_panel_widths(self) -> None:
        assert panel_width_for(PanelMode.FULL) == 300
        assert panel_width_for(PanelMode.NARROW) == NARROW_PANEL_WIDTH == 200
        assert panel_width_for(PanelMode.ICON_STRIP) == STRIP_PANEL_WIDTH == 48

    def test_settings_defaults_and_clamps(self) -> None:
        settings = AppSettings()
        settings._qs.remove("panels/narrowThreshold")  # noqa: SLF001
        settings._qs.remove("panels/stripThreshold")  # noqa: SLF001
        assert settings.panel_narrow_threshold() == 1280
        assert settings.panel_strip_threshold() == 1024
        settings.set_panel_narrow_threshold(10)
        settings.set_panel_strip_threshold(99999)
        assert settings.panel_narrow_threshold() == 600
        assert settings.panel_strip_threshold() == 5120


class TestWindowModes:
    def test_resizing_the_window_moves_through_the_modes(self, qtbot: QtBot) -> None:
        window = _shown(qtbot, 1400, 800)
        layer = window._layer_panel  # noqa: SLF001
        props = window._property_panel  # noqa: SLF001
        assert window.panel_mode is PanelMode.FULL
        assert layer.mode is PanelMode.FULL and props.mode is PanelMode.FULL
        assert not props._stroke_w_slider.isHidden()  # noqa: SLF001

        window.resize(1200, 800)
        QApplication.processEvents()
        assert window.panel_mode is PanelMode.NARROW
        assert layer.mode is PanelMode.NARROW
        assert props._stroke_w_slider.isHidden()  # noqa: SLF001
        assert props._stroke_hex.isHidden()  # noqa: SLF001
        assert props.widget() is props._scroll  # noqa: SLF001
        assert layer.button("New Layer").isVisibleTo(layer)

        window.resize(1024, 600)
        QApplication.processEvents()
        assert window.panel_mode is PanelMode.ICON_STRIP
        assert layer.mode is PanelMode.ICON_STRIP
        assert layer.maximumWidth() == STRIP_PANEL_WIDTH
        assert props.maximumWidth() == STRIP_PANEL_WIDTH
        assert not layer.button("New Layer").isVisibleTo(layer)
        assert props.widget() is props.strip
        assert layer.list_widget.sizeHintForColumn(0) <= STRIP_PANEL_WIDTH

        window.resize(1400, 800)
        QApplication.processEvents()
        assert window.panel_mode is PanelMode.FULL
        assert props.widget() is props._scroll  # noqa: SLF001
        assert not props._stroke_w_slider.isHidden()  # noqa: SLF001
        assert layer.button("New Layer").isVisibleTo(layer)
        assert layer.maximumWidth() > STRIP_PANEL_WIDTH

    def test_row_geometry_per_mode(self) -> None:
        rect = QRect(0, 0, 300, 40)
        full = _RowRects(rect, PanelMode.FULL)
        narrow = _RowRects(rect, PanelMode.NARROW)
        strip = _RowRects(QRect(0, 0, 48, 40), PanelMode.ICON_STRIP)
        assert full.opacity.width() > 0
        assert narrow.opacity.width() == 0
        assert narrow.name.width() > full.name.width()
        assert strip.eye.isEmpty() and strip.lock.isEmpty() and strip.name.isEmpty()
        assert strip.thumbnail.width() > 0 and strip.thumbnail.right() <= 48

    def test_thresholds_from_preferences_change_the_mode(self, qtbot: QtBot) -> None:
        window = _shown(qtbot, 1200, 800)
        assert window.panel_mode is PanelMode.NARROW
        window._apply_preference_changes(  # noqa: SLF001
            {"panel_narrow_threshold": (1280, 1100), "panel_strip_threshold": (1024, 900)}
        )
        assert AppSettings().panel_narrow_threshold() == 1100
        assert window.panel_mode is PanelMode.FULL
        window.resize(1000, 700)
        QApplication.processEvents()
        assert window.panel_mode is PanelMode.NARROW

    def test_preferences_appearance_rows(self, qtbot: QtBot) -> None:
        from snapmock.ui.preferences_dialog import PreferencesDialog

        _defaults()
        dlg = PreferencesDialog(AppSettings())
        qtbot.addWidget(dlg)
        assert dlg._narrow_threshold_spin.value() == 1280  # noqa: SLF001
        assert dlg._strip_threshold_spin.value() == 1024  # noqa: SLF001
        assert dlg._narrow_threshold_spin.accessibleName()  # noqa: SLF001
        dlg._narrow_threshold_spin.setValue(1500)  # noqa: SLF001
        assert dlg.get_changes()["panel_narrow_threshold"] == (1280, 1500)

    def test_reset_layout_keeps_the_mode(self, qtbot: QtBot) -> None:
        window = _shown(qtbot, 1024, 600)
        window._view_reset_layout()  # noqa: SLF001
        assert window.panel_mode is PanelMode.ICON_STRIP
        assert window._layer_panel.maximumWidth() == STRIP_PANEL_WIDTH  # noqa: SLF001


class TestStripPopovers:
    def test_layer_thumbnail_popover_carries_the_controls(self, qtbot: QtBot) -> None:
        window = _shown(qtbot, 1024, 600)
        panel = window._layer_panel  # noqa: SLF001
        layer = window.scene.layer_manager.active_layer
        assert layer is not None
        stack = window.scene.command_stack
        before = stack.count
        panel.open_layer_popover(layer.layer_id, QRect(0, 0, 48, 40))
        popover = panel.layer_popover
        assert popover is not None
        assert popover.name_edit.text() == layer.name
        assert popover.visible_check.isChecked() is True
        popover.visible_check.setChecked(False)
        assert layer.visible is False
        assert stack.count == before + 1
        popover.lock_check.setChecked(True)
        assert layer.locked is True
        popover.opacity_slider.setValue(40)
        assert layer.opacity == 0.4
        popover.name_edit.setText("Background")
        popover.name_edit.editingFinished.emit()
        assert layer.name == "Background"
        for w in (popover.name_edit, popover.visible_check, popover.lock_check):
            assert w.accessibleName()
        popover.close()

    def test_property_strip_buttons_open_the_panel_popover(self, qtbot: QtBot) -> None:
        window = _shown(qtbot, 1024, 600)
        props = window._property_panel  # noqa: SLF001
        buttons = props.strip.findChildren(QToolButton)
        names = [b.accessibleName() for b in buttons]
        assert "Transform section" in names and "Canvas section" in names
        transform = next(b for b in buttons if b.accessibleName() == "Transform section")
        transform.click()
        popover = props.popover
        assert popover is not None
        assert props._scroll.parentWidget() is popover  # noqa: SLF001
        assert props._transform_section.expanded  # noqa: SLF001
        popover.close()
        QApplication.processEvents()
        assert props._scroll.parentWidget() is not popover  # noqa: SLF001
        window.resize(1400, 800)
        QApplication.processEvents()
        assert props.widget() is props._scroll  # noqa: SLF001
        assert isinstance(props.widget(), QWidget)


class TestOptionsBarOverflow:
    def test_extension_button_is_named(self, main_window: MainWindow) -> None:
        for bar, name in (
            (main_window._tool_options, "More tool options"),  # noqa: SLF001
            (main_window._main_toolbar, "More toolbar buttons"),  # noqa: SLF001
            (main_window._toolbar, "More tools"),  # noqa: SLF001
        ):
            ext = bar.findChild(QToolButton, "qt_toolbar_ext_button")
            assert ext is not None
            assert ext.accessibleName() == name

    def test_bar_overflows_into_the_extension_button_at_the_minimum(self, qtbot: QtBot) -> None:
        window = _shown(qtbot, 1024, 600)
        window.tool_manager.activate("callout")
        QApplication.processEvents()
        bar = window._tool_options  # noqa: SLF001
        ext = bar.findChild(QToolButton, "qt_toolbar_ext_button")
        assert ext is not None
        assert bar.sizeHint().width() > 0
