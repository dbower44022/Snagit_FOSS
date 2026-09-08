"""Tests for the theme manager (General UI PRD Section 13) and View > Dark Mode."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from snapmock.config.settings import AppSettings
from snapmock.core import theme_manager as tm
from snapmock.core.theme_manager import (
    COLOR_NAMES,
    ThemeMode,
    load_theme,
    parse_theme_file,
    reset_theme_manager,
    theme_manager,
)
from snapmock.main_window import MainWindow


@pytest.fixture(autouse=True)
def fresh_theme_manager() -> None:
    """Each test starts with no process-wide ThemeManager and ends the same way."""
    reset_theme_manager()
    yield
    reset_theme_manager()


class TestThemeFiles:
    def test_light_and_dark_define_every_colour(self) -> None:
        light = load_theme("light")
        dark = load_theme("dark")
        for name in COLOR_NAMES:
            assert getattr(light.colors, name).isValid(), name
            assert getattr(dark.colors, name).isValid(), name

    def test_tables_of_section_13(self) -> None:
        light = load_theme("light").colors
        dark = load_theme("dark").colors
        assert light.window_bg.name().upper() == "#F5F5F5"
        assert light.accent.name().upper() == "#2B579A"
        assert light.pasteboard.name().upper() == "#E0E0E0"
        assert dark.window_bg.name().upper() == "#2D2D2D"
        assert dark.accent.name().upper() == "#5B9BD5"
        assert dark.pasteboard.name().upper() == "#1E1E1E"
        assert light.grid_lines.alpha() == 0x33
        assert dark.grid_lines.alpha() == 0x26

    def test_constants_are_substituted_into_the_rules(self) -> None:
        light = load_theme("light")
        assert "@" not in light.style_sheet
        assert "#F5F5F5" in light.style_sheet

    def test_missing_constant_is_an_error(self) -> None:
        text = "@window-bg: #FFFFFF;\nQWidget { color: @text-primary; }"
        with pytest.raises(ValueError, match="lacks constants"):
            parse_theme_file(text, "broken")

    def test_undefined_reference_is_an_error(self) -> None:
        light_text = (tm.THEMES_DIR / "light.qss").read_text(encoding="utf-8")
        with pytest.raises(ValueError, match="undefined constant"):
            parse_theme_file(light_text + "\nQWidget { color: @nope; }", "broken")


class TestThemeManager:
    def test_default_is_light(self, qtbot: QtBot) -> None:
        manager = theme_manager()
        assert manager.mode is ThemeMode.LIGHT
        assert manager.resolved == "light"

    def test_set_mode_dark_applies_live(self, qtbot: QtBot, qapp: object) -> None:
        manager = theme_manager()
        manager.apply()
        with qtbot.waitSignal(manager.theme_changed) as blocker:
            manager.set_mode(ThemeMode.DARK)
        assert blocker.args == ["dark"]
        assert manager.resolved == "dark"
        assert manager.colors.window_bg.name().upper() == "#2D2D2D"
        assert "#2D2D2D" in qapp.styleSheet()  # type: ignore[attr-defined]
        assert qapp.palette().window().color().name().upper() == "#2D2D2D"  # type: ignore[attr-defined]

    def test_same_mode_does_not_reapply(self, qtbot: QtBot) -> None:
        manager = theme_manager()
        manager.apply()
        with qtbot.assertNotEmitted(manager.theme_changed):
            manager.set_mode(ThemeMode.LIGHT)

    def test_system_follows_the_style_hint(
        self, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager = theme_manager()
        monkeypatch.setattr(tm, "system_prefers_dark", lambda: True)
        manager.set_mode(ThemeMode.SYSTEM)
        assert manager.resolved == "dark"
        monkeypatch.setattr(tm, "system_prefers_dark", lambda: False)
        manager.set_mode(ThemeMode.SYSTEM)
        assert manager.resolved == "light"

    def test_ui_font_size_changes_the_application_font(self, qtbot: QtBot, qapp: object) -> None:
        manager = theme_manager()
        manager.apply()
        base = qapp.font().pointSizeF()  # type: ignore[attr-defined]
        manager.set_ui_font_size("large")
        assert qapp.font().pointSizeF() == pytest.approx(base + 2)  # type: ignore[attr-defined]
        manager.set_ui_font_size("medium")
        assert qapp.font().pointSizeF() == pytest.approx(base)  # type: ignore[attr-defined]

    def test_icon_size_signal(self, qtbot: QtBot) -> None:
        manager = theme_manager()
        with qtbot.waitSignal(manager.icon_size_changed) as blocker:
            manager.set_icon_size(32)
        assert blocker.args == [32]
        assert manager.icon_size == 32
        manager.set_icon_size(99)
        assert manager.icon_size == 24

    def test_from_value_falls_back_to_light(self) -> None:
        assert ThemeMode.from_value("dark") is ThemeMode.DARK
        assert ThemeMode.from_value("bogus") is ThemeMode.LIGHT


class TestDarkModeMenu:
    def _dark_mode_action(self, window: MainWindow):  # type: ignore[no-untyped-def]
        return window._dark_mode_action

    def test_action_reflects_saved_theme(self, qtbot: QtBot) -> None:
        AppSettings().set_theme_mode("dark")
        window = MainWindow()
        qtbot.addWidget(window)
        assert self._dark_mode_action(window).isChecked() is True
        assert theme_manager().resolved == "dark"

    def test_toggle_persists_and_switches(self, main_window: MainWindow) -> None:
        action = self._dark_mode_action(main_window)
        assert action.isChecked() is False
        action.setChecked(True)
        assert theme_manager().resolved == "dark"
        assert AppSettings().theme_mode() == "dark"
        action.setChecked(False)
        assert theme_manager().resolved == "light"
        assert AppSettings().theme_mode() == "light"

    def test_preferences_mode_updates_the_action(self, main_window: MainWindow) -> None:
        main_window.set_theme_mode(ThemeMode.DARK)
        assert self._dark_mode_action(main_window).isChecked() is True
        assert AppSettings().theme_mode() == "dark"
