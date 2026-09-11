"""StampTool, its Tool Options Bar, the library panel, and stamp editing (Numbered Steps,
Stamps & Emoji PRD 3.4, 3.6, 3.7, 3.8, 3.11; kickoff Phase 2 step 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QColor, QDropEvent, QMouseEvent
from PyQt6.QtWidgets import QCheckBox, QDialog, QMenu, QPushButton, QSpinBox, QToolButton
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.marker_commands import ChangeStampCommand
from snapmock.core.scene import SnapScene
from snapmock.core.stamp_library import CUSTOM_CATEGORY, StampLibrary, set_stamp_library
from snapmock.items.stamp_item import StampItem
from snapmock.main_window import MainWindow
from snapmock.tools import numbered_step_tool as animation_module
from snapmock.tools.stamp_tool import NO_STAMP_HINT, StampTool
from snapmock.ui.color_picker import ColorPicker
from snapmock.ui.context_menus import build_item_context_menu
from snapmock.ui.stamp_library_panel import (
    EMPTY_CUSTOM_TEXT,
    StampLibraryPanel,
    StampMetadataDialog,
)
from snapmock.ui.tool_options_bar import ToolOptionsBar

Button = Qt.MouseButton
Modifier = Qt.KeyboardModifier

SIMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
    '<rect x="0" y="0" width="64" height="64" fill="#FF0000"/></svg>'
)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(animation_module, "ANIMATIONS_ENABLED", False)
    set_stamp_library(StampLibrary(custom_dir=tmp_path / "custom-stamps"))
    yield  # type: ignore[misc]
    set_stamp_library(None)


def _tool(window: MainWindow, stamp_id: str | None = "status/approved") -> StampTool:
    window.tool_manager.activate("stamp")
    tool = window.tool_manager.tool("stamp")
    assert isinstance(tool, StampTool)
    if stamp_id:
        tool.set_active_stamp(stamp_id)
    return tool


def _bar(window: MainWindow) -> ToolOptionsBar:
    return window._tool_options  # noqa: SLF001


def _event(
    kind: QEvent.Type, window: MainWindow, scene_pos: QPointF, mods: Modifier = Modifier.NoModifier
) -> QMouseEvent:
    view_pos = QPointF(window.view.mapFromScene(scene_pos))
    return QMouseEvent(kind, view_pos, Button.LeftButton, Button.LeftButton, mods)


def _press(window: MainWindow, p: QPointF) -> None:
    window.tool_manager.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, window, p))


def _move(window: MainWindow, p: QPointF, mods: Modifier = Modifier.NoModifier) -> None:
    window.tool_manager.handle_mouse_move(_event(QEvent.Type.MouseMove, window, p, mods))


def _release(window: MainWindow, p: QPointF) -> None:
    window.tool_manager.handle_mouse_release(_event(QEvent.Type.MouseButtonRelease, window, p))


def _click(window: MainWindow, p: QPointF) -> None:
    _press(window, p)
    _release(window, p)


def _double_click(window: MainWindow, p: QPointF) -> None:
    window.tool_manager.handle_mouse_double_click(
        _event(QEvent.Type.MouseButtonDblClick, window, p)
    )


def _stamps(window: MainWindow) -> list[StampItem]:
    found = [i for i in window.scene.annotation_items() if isinstance(i, StampItem)]
    return list(reversed(found))


def _menu_texts(menu: QMenu) -> list[str]:
    return [a.text() for a in menu.actions() if not a.isSeparator()]


# --- placement (Section 3.4) ---


def test_hints_cursor_and_no_stamp_route(main_window: MainWindow) -> None:
    tool = _tool(main_window, None)
    assert tool.active_stamp is None
    assert tool.status_hint == NO_STAMP_HINT
    assert tool.cursor == Qt.CursorShape.CrossCursor
    _click(main_window, QPointF(100, 100))
    assert _stamps(main_window) == []
    panel = tool.panel
    assert isinstance(panel, StampLibraryPanel)
    assert not panel.isHidden()
    panel.hide()
    tool.set_active_stamp("status/approved")
    assert tool.status_hint == "Click to place Approved. Drag to set size."
    assert not tool.cursor.pixmap().isNull()  # type: ignore[union-attr]
    assert tool.creation_defaults["stamp_size"] == 48.0


def test_click_places_the_active_stamp_centred_and_the_tool_stays(
    main_window: MainWindow,
) -> None:
    tool = _tool(main_window)
    _click(main_window, QPointF(100, 120))
    _click(main_window, QPointF(200, 120))
    stamps = _stamps(main_window)
    assert [s.stamp_id for s in stamps] == ["status/approved", "status/approved"]
    assert stamps[0].pos() == QPointF(100, 120)
    assert stamps[0].stamp_size == 48.0
    assert stamps[0].scale() == 1.0
    assert main_window.tool_manager.active_tool_id == "stamp"
    assert tool.status_hint == "Placed Approved. Click to place another."
    main_window.scene.command_stack.undo()
    assert len(_stamps(main_window)) == 1


def test_drag_fits_the_stamp_in_the_rectangle_and_shift_squares_it(
    main_window: MainWindow,
) -> None:
    _tool(main_window)
    _press(main_window, QPointF(100, 100))
    _move(main_window, QPointF(220, 160))
    _release(main_window, QPointF(220, 160))
    (stamp,) = _stamps(main_window)
    assert stamp.stamp_size == pytest.approx(60.0)  # the square stamp fits the 120 by 60 box
    assert stamp.pos() == QPointF(160, 130)
    _press(main_window, QPointF(300, 100))
    _move(main_window, QPointF(420, 160), Modifier.ShiftModifier)
    _release(main_window, QPointF(420, 160))
    second = _stamps(main_window)[-1]
    assert second.stamp_size == pytest.approx(120.0)
    assert second.pos() == QPointF(360, 160)


def test_placement_takes_the_creation_defaults(main_window: MainWindow) -> None:
    tool = _tool(main_window)
    tool.creation_defaults.update(
        {
            "stamp_size": 96.0,
            "stamp_color": QColor("#00aa00"),
            "stamp_secondary_color": QColor("#0000aa"),
            "flip_horizontal": True,
            "opacity_pct": 50.0,
            "shadow_enabled": True,
        }
    )
    _click(main_window, QPointF(10, 10))
    (stamp,) = _stamps(main_window)
    assert stamp.stamp_size == 96.0
    assert stamp.stamp_color.name() == "#00aa00"
    assert stamp.stamp_secondary_color.name() == "#0000aa"
    assert stamp.flip_horizontal is True
    assert stamp.opacity_pct == pytest.approx(50.0)
    assert stamp.shadow_enabled is True


def test_locked_layer_refuses_with_the_message(
    main_window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    _tool(main_window)
    layer = main_window.scene.layer_manager.active_layer
    assert layer is not None
    main_window.scene.layer_manager.set_locked(layer.layer_id, True)
    _click(main_window, QPointF(10, 10))
    assert _stamps(main_window) == []
    assert unmet_messages[-1] == ("Stamp", "Stamp needs an unlocked active layer.")


# --- the Tool Options Bar (Section 3.6) ---


def test_bar_shows_preview_library_button_and_the_section_3_6_controls(
    main_window: MainWindow,
) -> None:
    tool = _tool(main_window)
    bar = _bar(main_window)
    widgets = bar.shared_widgets
    assert list(widgets) == [
        "stamp_size",
        "stamp_color",
        "stamp_secondary_color",
        "flip_horizontal",
        "flip_vertical",
        "opacity_pct",
        "shadow_enabled",
    ]
    size = widgets["stamp_size"]
    assert isinstance(size, QSpinBox)
    assert (size.minimum(), size.maximum()) == (16, 512)
    assert isinstance(widgets["stamp_color"], ColorPicker)
    flip = widgets["flip_horizontal"]
    assert isinstance(flip, QToolButton) and flip.isCheckable()
    assert isinstance(widgets["shadow_enabled"], QCheckBox)
    preview = next(
        b for b in bar.findChildren(QToolButton) if b.accessibleName() == "Active stamp"
    )
    assert not preview.icon().isNull()
    assert any(b.text() == "Library..." for b in bar.findChildren(QPushButton))
    assert bar.preset_button is not None  # the stamp tool now has creation defaults
    flip.setChecked(True)
    assert tool.creation_defaults["flip_horizontal"] is True
    size.setValue(200)
    assert tool.creation_defaults["stamp_size"] == 200


def test_colour_change_on_a_fixed_stamp_explains(
    main_window: MainWindow, unmet_messages: list[tuple[str, str]], tmp_path: Path
) -> None:
    from snapmock.core.stamp_library import stamp_library

    source = tmp_path / "fixed.svg"
    source.write_text(SIMPLE_SVG)
    info = stamp_library().import_svg(source, name="Fixed", colorizable=False)
    tool = _tool(main_window, info.id)
    picker = _bar(main_window).shared_widgets["stamp_color"]
    assert isinstance(picker, ColorPicker)
    picker.color_changed.emit(QColor("#00ff00"))
    assert unmet_messages[-1] == ("Stamp Color", "Stamp Color needs a colorizable stamp.")
    assert tool.creation_defaults["stamp_color"] == QColor("#00ff00")  # stored all the same
    tool.set_active_stamp("status/approved")  # colorizable, no secondary region
    secondary = _bar(main_window).shared_widgets["stamp_secondary_color"]
    assert isinstance(secondary, ColorPicker)
    secondary.color_changed.emit(QColor("#0000ff"))
    assert unmet_messages[-1] == (
        "Secondary Color",
        "Secondary Color needs a stamp with a secondary colour region.",
    )


# --- the library panel (Sections 3.4 and 3.8) ---


def test_panel_tabs_grid_and_search(qtbot: QtBot) -> None:
    panel = StampLibraryPanel(popup=False)
    qtbot.addWidget(panel)
    panel.show()
    tabs = [panel.tabs.tabText(i) for i in range(panel.tabs.count())]
    assert tabs == [
        "Status",
        "Arrows & Pointers",
        "UI Annotations",
        "Shapes & Symbols",
        "Decorative",
        "Custom",
    ]
    assert panel.current_category == "status"
    assert "status/approved" in panel.visible_ids()
    assert all(i.startswith("status/") for i in panel.visible_ids())
    assert panel.grid.iconSize().width() == 48
    panel.set_category("shapes")
    assert all(i.startswith("shapes/") for i in panel.visible_ids())
    panel.search_edit.setText("arrow")
    ids = panel.visible_ids()
    assert ids and all("arrow" in i or "pointer" in i or "cursor" in i for i in ids)
    panel.search_edit.setText("zzzz-nothing")
    assert panel.visible_ids() == []
    assert not panel.empty_label.isHidden()
    assert "zzzz-nothing" in panel.empty_label.text()
    panel.search_edit.setText("")
    panel.set_category(CUSTOM_CATEGORY)
    assert panel.visible_ids() == []
    assert panel.empty_label.text() == EMPTY_CUSTOM_TEXT
    assert not panel.import_button.isHidden()


def test_panel_click_chooses_and_hides(qtbot: QtBot) -> None:
    panel = StampLibraryPanel(popup=False)
    qtbot.addWidget(panel)
    panel.show()
    chosen: list[str] = []
    panel.stamp_chosen.connect(chosen.append)
    item = panel.grid.item(0)
    assert item is not None
    panel.grid.itemClicked.emit(item)
    assert chosen == ["status/approved"]
    assert panel.isHidden()
    panel.set_current("shapes/lock")
    assert panel.current_category == "shapes"
    current = panel.grid.currentItem()
    assert current is not None and current.text() == "Lock"


def _accepting_dialog(name: str, parent: object = None) -> StampMetadataDialog:
    dialog = StampMetadataDialog(name, None)
    dialog.tags_edit.setText("mine, badge")
    dialog.colorizable_check.setChecked(False)
    dialog.exec = lambda: QDialog.DialogCode.Accepted  # type: ignore[method-assign]
    return dialog


def test_import_through_the_dialog_and_a_drop(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt6.QtWidgets import QFileDialog

    panel = StampLibraryPanel(popup=False)
    qtbot.addWidget(panel)
    panel.show()
    source = tmp_path / "Badge One.svg"
    source.write_text(SIMPLE_SVG)
    monkeypatch.setattr(StampLibraryPanel, "metadata_dialog", staticmethod(_accepting_dialog))
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(source)], "SVG files (*.svg)")
    )
    panel.set_category(CUSTOM_CATEGORY)
    panel.import_button.click()
    assert panel.visible_ids() == ["custom/badge-one"]
    info = panel.library.stamp("custom/badge-one")
    assert info is not None
    assert info.tags == ("mine", "badge")
    assert info.colorizable is False
    # A drop of an SVG file on the Custom tab imports it too
    second = tmp_path / "two.svg"
    second.write_text(SIMPLE_SVG)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(second)), QUrl.fromLocalFile(str(tmp_path / "x.png"))])
    event = QDropEvent(
        QPointF(10, 10), Qt.DropAction.CopyAction, mime, Button.LeftButton, Modifier.NoModifier
    )
    panel.grid.dropEvent(event)
    assert set(panel.visible_ids()) == {"custom/badge-one", "custom/two"}
    # On a built-in tab the grid takes no files
    panel.set_category("status")
    assert panel.grid.accepts_files is False


def test_import_cancelled_imports_nothing(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel = StampLibraryPanel(popup=False)
    qtbot.addWidget(panel)

    def _cancel(name: str, parent: object = None) -> StampMetadataDialog:
        dialog = StampMetadataDialog(name, None)
        dialog.exec = lambda: QDialog.DialogCode.Rejected  # type: ignore[method-assign]
        return dialog

    monkeypatch.setattr(StampLibraryPanel, "metadata_dialog", staticmethod(_cancel))
    source = tmp_path / "skip.svg"
    source.write_text(SIMPLE_SVG)
    assert panel.import_files([source]) == []
    assert panel.library.in_category(CUSTOM_CATEGORY) == []


# --- double-click replacement and the context rows (Section 3.7) ---


def test_double_click_opens_the_library_and_a_pick_is_one_undo_entry(
    main_window: MainWindow,
) -> None:
    tool = _tool(main_window)
    _click(main_window, QPointF(200, 200))
    (stamp,) = _stamps(main_window)
    main_window.tool_manager.activate("select")
    _double_click(main_window, QPointF(200, 200))
    panel = tool.panel
    assert isinstance(panel, StampLibraryPanel) and not panel.isHidden()
    assert panel.grid.currentItem() is not None
    panel.stamp_chosen.emit("shapes/lock")
    assert stamp.stamp_id == "shapes/lock"
    assert stamp.stamp_name == "Lock"
    main_window.scene.command_stack.undo()
    assert stamp.stamp_id == "status/approved"
    main_window.scene.command_stack.redo()
    assert stamp.stamp_id == "shapes/lock"
    # The stamp tool's own double-click takes the same route, and its click selects
    main_window.tool_manager.activate("stamp")
    _double_click(main_window, QPointF(200, 200))
    assert not panel.isHidden()
    panel.hide()
    _click(main_window, QPointF(200, 200))
    assert len(_stamps(main_window)) == 1
    assert main_window.selection_manager.items == [stamp]


def test_context_rows_for_one_stamp(
    main_window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    _tool(main_window)
    _click(main_window, QPointF(200, 200))
    (stamp,) = _stamps(main_window)
    main_window.selection_manager.select(stamp)
    texts = _menu_texts(build_item_context_menu(main_window))
    assert "Change Stamp..." in texts
    assert "Reset Size" in texts
    assert "Flip Horizontal" in texts and "Flip Vertical" in texts
    assert "Renumber All Steps" not in texts
    stamp.stamp_size = 200.0
    main_window._stamp_reset_size()  # noqa: SLF001
    assert stamp.stamp_size == 48.0
    main_window.scene.command_stack.undo()
    assert stamp.stamp_size == 200.0
    main_window.selection_manager.deselect_all()
    main_window._stamp_reset_size()  # noqa: SLF001
    assert unmet_messages[-1] == ("Reset Size", "Reset Size needs one stamp.")
    main_window._stamp_change()  # noqa: SLF001
    assert unmet_messages[-1] == ("Change Stamp", "Change Stamp needs one stamp.")


def test_change_stamp_command_swaps_and_restores(scene: SnapScene) -> None:
    from snapmock.core.stamp_library import stamp_library

    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = StampItem("status/heart")
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    info = stamp_library().stamp("shapes/bolt")
    assert info is not None
    command = ChangeStampCommand(item, info, stamp_library().svg_data(info.id))
    assert command.description == "Change stamp to Lightning Bolt"
    scene.command_stack.push(command)
    assert (command.old_stamp_id, command.new_stamp_id) == ("status/heart", "shapes/bolt")
    assert item.stamp_id == "shapes/bolt" and item.svg_data == stamp_library().svg_data(
        "shapes/bolt"
    )
    scene.command_stack.undo()
    assert item.stamp_id == "status/heart" and item.stamp_name == "Heart"


# --- the Property Panel ---


def test_property_panel_shows_a_stamp_section(main_window: MainWindow) -> None:
    _tool(main_window)
    _click(main_window, QPointF(200, 200))
    (stamp,) = _stamps(main_window)
    main_window.selection_manager.select(stamp)
    panel = main_window._property_panel  # noqa: SLF001
    assert not panel._stamp_section.isHidden()  # noqa: SLF001
    assert not panel._shadow_section.isHidden()  # noqa: SLF001
    assert panel._appearance_section.isHidden()  # noqa: SLF001
    assert panel._stamp_name_label.text() == "Approved"  # noqa: SLF001
    panel._stamp_size_spin.setValue(100.0)  # noqa: SLF001
    assert stamp.stamp_size == 100.0
    panel._stamp_opacity_spin.setValue(40)  # noqa: SLF001
    assert stamp.opacity_pct == pytest.approx(40.0)
    panel._stamp_color_picker.color_changed.emit(QColor("#123456"))  # noqa: SLF001
    assert stamp.stamp_color.name() == "#123456"
    main_window.scene.command_stack.undo()
    main_window.scene.command_stack.undo()
    main_window.scene.command_stack.undo()
    assert stamp.stamp_size == 48.0 and stamp.opacity_pct == 100.0
