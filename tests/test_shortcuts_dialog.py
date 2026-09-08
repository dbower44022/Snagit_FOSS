"""Help > Keyboard Shortcuts (General UI PRD 3.8, 12)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from snapmock.config.shortcuts import SHORTCUTS
from snapmock.ui.shortcuts_dialog import (
    KeyboardShortcutsDialog,
    action_label,
    shortcut_rows,
)


def test_rows_cover_every_bound_shortcut_and_the_conventions() -> None:
    rows = shortcut_rows()
    actions = {r.action for r in rows}
    bound = [a for a, text in SHORTCUTS.items() if text or a == "tool.pan"]
    for action_id in bound:
        assert action_label(action_id) in actions, action_id
    assert "Pan to canvas origin" in actions
    assert "Temporary eyedropper" in actions
    delete = next(r for r in rows if r.action == "Delete" and r.category == "Edit")
    assert delete.keys == "Del / Backspace"
    pan = next(r for r in rows if r.action == "Pan / Hand")
    assert pan.keys == "Space (hold)"


def test_capture_bindings_override_the_defaults() -> None:
    rows = shortcut_rows({"capture.region": "Ctrl+Shift+R"})
    region = next(r for r in rows if r.action == "Capture Region")
    assert region.keys == "Ctrl+Shift+R"


def test_search_filters_rows(qtbot: QtBot) -> None:
    dlg = KeyboardShortcutsDialog()
    qtbot.addWidget(dlg)
    assert len(dlg.visible_rows()) == len(dlg.rows)
    dlg._search.setText("layer")  # noqa: SLF001
    shown = dlg.visible_rows()
    assert shown
    assert all("layer" in f"{r.category} {r.action} {r.keys}".lower() for r in shown)
    dlg._search.setText("ctrl+shift+z")  # noqa: SLF001
    assert [r.action for r in dlg.visible_rows()] == ["Redo"]
    dlg._search.setText("")  # noqa: SLF001
    assert len(dlg.visible_rows()) == len(dlg.rows)
