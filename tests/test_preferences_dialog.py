"""Tests for PreferencesDialog."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from snapmock.config.settings import AppSettings
from snapmock.ui.preferences_dialog import PreferencesDialog


def _make_settings() -> AppSettings:
    """Create an AppSettings instance with known defaults."""
    settings = AppSettings()
    # Reset to known state for tests
    settings.set_autosave_enabled(True)
    settings.set_autosave_interval_minutes(2)
    settings.set_grid_visible(False)
    settings.set_grid_size(20)
    settings.set_rulers_visible(False)
    settings.set_snap_to_grid(False)
    return settings


class TestPreferencesDialogInitialValues:
    def test_shows_autosave_enabled(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_autosave_enabled(True)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._autosave_cb.isChecked() is True

    def test_shows_autosave_interval(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_autosave_interval_minutes(5)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._autosave_interval_spin.value() == 5

    def test_autosave_interval_disabled_when_unchecked(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_autosave_enabled(False)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._autosave_interval_spin.isEnabled() is False

    def test_autosave_interval_enabled_when_checked(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_autosave_enabled(True)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._autosave_interval_spin.isEnabled() is True
        # Toggle off via checkbox
        dlg._autosave_cb.setChecked(False)
        assert dlg._autosave_interval_spin.isEnabled() is False

    def test_shows_grid_visible(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_grid_visible(True)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._grid_visible_cb.isChecked() is True

    def test_shows_grid_size(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_grid_size(50)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._grid_size_spin.value() == 50

    def test_shows_rulers_visible(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_rulers_visible(True)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._rulers_cb.isChecked() is True

    def test_shows_snap_to_grid(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_snap_to_grid(True)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg._snap_to_grid_cb.isChecked() is True


class TestPreferencesDialogGetChanges:
    def test_empty_when_nothing_modified(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        assert dlg.get_changes() == {}

    def test_detects_autosave_enabled_change(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_autosave_enabled(True)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        dlg._autosave_cb.setChecked(False)
        changes = dlg.get_changes()
        assert "autosave_enabled" in changes
        assert changes["autosave_enabled"] == (True, False)

    def test_detects_autosave_interval_change(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_autosave_interval_minutes(2)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        dlg._autosave_interval_spin.setValue(10)
        changes = dlg.get_changes()
        assert "autosave_interval" in changes
        assert changes["autosave_interval"] == (2, 10)

    def test_detects_grid_size_change(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        settings.set_grid_size(20)
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        dlg._grid_size_spin.setValue(40)
        changes = dlg.get_changes()
        assert "grid_size" in changes
        assert changes["grid_size"] == (20, 40)

    def test_detects_multiple_changes(self, qtbot: QtBot) -> None:
        settings = _make_settings()
        dlg = PreferencesDialog(settings)
        qtbot.addWidget(dlg)
        dlg._grid_visible_cb.setChecked(True)
        dlg._rulers_cb.setChecked(True)
        dlg._snap_to_grid_cb.setChecked(True)
        changes = dlg.get_changes()
        assert "grid_visible" in changes
        assert "rulers_visible" in changes
        assert "snap_to_grid" in changes
        assert len(changes) == 3
