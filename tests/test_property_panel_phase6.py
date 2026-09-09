"""Property Panel items of General UI PRD Section 8 built in Phase 6."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont
from pytestqt.qtbot import QtBot

from snapmock.commands.canvas_property_commands import SetCanvasPropertyCommand
from snapmock.config.settings import AppSettings
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.io.project_serializer import load_project, save_project
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem
from snapmock.main_window import MainWindow
from snapmock.ui.context_menus import build_canvas_context_menu
from snapmock.ui.property_panel import MIXED_TEXT, PropertyPanel


def _make_panel(qtbot: QtBot) -> tuple[PropertyPanel, SnapScene, SelectionManager]:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    return panel, scene, sm


def _add_rect(scene: SnapScene, x: float = 0, y: float = 0, w: float = 100) -> RectangleItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, w, 60))
    item.setPos(x, y)
    item.layer_id = layer.layer_id
    layer.item_ids.append(item.item_id)
    scene.addItem(item)
    return item


def _add_text(scene: SnapScene, text: str = "Hello") -> TextItem:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = TextItem(text=text)
    item.layer_id = layer.layer_id
    layer.item_ids.append(item.item_id)
    scene.addItem(item)
    return item


# ---- collapse persistence (PRD 8.2) ----


def test_section_collapse_state_persists(qtbot: QtBot) -> None:
    panel, _scene, _sm = _make_panel(qtbot)
    assert panel._canvas_section.expanded
    panel._canvas_section._toggle_btn.click()
    assert not panel._canvas_section.expanded
    assert AppSettings().property_section_expanded("Canvas") is False
    panel2, _s2, _sm2 = _make_panel(qtbot)
    assert not panel2._canvas_section.expanded
    assert panel2._transform_section.expanded


# ---- transform: chain link, mixed values, one command per change (PRD 8.3, 8.6) ----


def test_aspect_lock_scales_both_axes(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_rect(scene)
    sm.select(item)
    assert not panel.aspect_locked
    panel._w_spin.setValue(200.0)
    assert item.boundingRect().height() < 70  # the stroke pads the bounding rect
    panel._aspect_lock.setChecked(True)
    assert not panel._aspect_lock.icon().isNull()
    panel._w_spin.setValue(400.0)
    assert item.boundingRect().height() > 110


def test_mixed_values_show_dash_and_apply_to_all(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    a = _add_rect(scene, 10, 10)
    b = _add_rect(scene, 50, 10)
    a.stroke_color = QColor("#FF0000")
    b.stroke_color = QColor("#00FF00")
    sm.select(a)
    sm.toggle(b)
    assert panel._x_spin.text() == MIXED_TEXT
    assert panel._y_spin.value() == 10
    assert panel._stroke_color_picker.mixed
    assert panel._stroke_hex.text() == ""
    assert panel._type_label.text() == "RectangleItem"  # one type across the selection
    panel._x_spin.setValue(30.0)
    assert a.pos_x == 30 and b.pos_x == 30
    assert scene.command_stack.count == 1
    assert scene.command_stack.undo_text == "Change pos_x on 2 items"
    scene.command_stack.undo()
    assert a.pos_x == 10 and b.pos_x == 50
    panel._stroke_hex.setText("#0000FF")
    panel._stroke_hex.editingFinished.emit()
    assert a.stroke_color == QColor("#0000FF") and b.stroke_color == QColor("#0000FF")
    assert not panel._stroke_color_picker.mixed
    assert panel._stroke_hex.text() == "#0000FF"


def test_hex_input_rejects_invalid_and_accepts_alpha(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_rect(scene)
    sm.select(item)
    panel._fill_hex.setText("not a colour")
    panel._fill_hex.editingFinished.emit()
    assert item.fill_color == QColor("transparent")
    assert panel._fill_hex.text() == "#00000000"
    panel._fill_hex.setText("#80FF0000")
    panel._fill_hex.editingFinished.emit()
    assert item.fill_color.alpha() == 128
    assert scene.command_stack.undo_text == "Change fill_color"


def test_slider_drag_over_a_selection_is_one_undo_entry(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    a = _add_rect(scene, 10, 10)
    b = _add_rect(scene, 50, 10)
    sm.select(a)
    sm.toggle(b)
    panel._opacity_slider.setValue(80)
    panel._opacity_slider.setValue(60)
    assert a.opacity_pct == 60 and b.opacity_pct == 60
    assert scene.command_stack.count == 1


# ---- text section (PRD 8.4) ----


def test_font_weight_and_style_dropdowns(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_text(scene)
    sm.select(item)
    assert panel._text_section.isVisible()
    assert panel._weight_combo.currentText() == "Regular"
    assert panel._style_combo.currentText() == "Normal"
    panel._weight_combo.setCurrentIndex(1)
    assert item.font.bold()
    panel._style_combo.setCurrentIndex(1)
    assert item.font.italic()
    assert scene.command_stack.undo_text == "Change font"
    # Background Fill is in the Text section, not the Text Box section
    assert panel._text_bg_color_picker.parent() is not None
    form = panel._text_section.form_layout
    assert form.indexOf(panel._text_bg_color_picker) >= 0
    panel._text_bg_color_picker.color = QColor("#123456")
    panel._text_bg_color_picker.color_changed.emit(QColor("#123456"))
    assert item.bg_color == QColor("#123456")


def test_text_alignment_is_a_command_across_the_selection(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    a = _add_text(scene, "one")
    b = _add_text(scene, "two")
    sm.select(a)
    sm.toggle(b)
    panel._text_align_combo.setCurrentIndex(2)  # Right
    assert a.horizontal_alignment == Qt.AlignmentFlag.AlignRight
    assert b.horizontal_alignment == Qt.AlignmentFlag.AlignRight
    assert scene.command_stack.undo_text == "Change horizontal_alignment on 2 items"
    scene.command_stack.undo()
    assert a.horizontal_alignment == Qt.AlignmentFlag.AlignLeft
    panel._font_size_spin.setValue(30)
    assert a.font.pointSize() == 30 and b.font.pointSize() == 30
    assert scene.command_stack.undo_text == "Change font"
    assert panel._weight_combo.currentIndex() == 0
    f = QFont(b.font)
    f.setBold(True)
    b.font = f
    panel._refresh_from_selection()
    assert panel._weight_combo.currentIndex() == -1  # mixed


# ---- canvas section (PRD 8.5) ----


def test_canvas_section_edits_size_colour_and_dpi_through_commands(qtbot: QtBot) -> None:
    panel, scene, sm = _make_panel(qtbot)
    item = _add_rect(scene, 10, 10)
    assert panel._canvas_section.isVisible()
    assert panel._canvas_w_spin.value() == 1920
    assert panel._dpi_spin.value() == 72
    panel._canvas_w_spin.setValue(800)
    assert scene.canvas_size.width() == 800
    assert item.pos_x == 10  # anchored top-left
    assert scene.command_stack.undo_text == "Resize canvas"
    panel._bg_color_picker.color = QColor("#ABCDEF")
    panel._bg_color_picker.color_changed.emit(QColor("#ABCDEF"))
    assert scene.background_color == QColor("#ABCDEF")
    assert scene.command_stack.undo_text == "Change canvas color"
    panel._dpi_spin.setValue(300)
    assert scene.canvas_dpi == 300
    assert scene.command_stack.undo_text == "Change canvas DPI"
    scene.command_stack.undo()
    assert scene.canvas_dpi == 72
    assert panel._dpi_spin.value() == 72


def test_canvas_dpi_round_trips_in_the_manifest(tmp_path: Path, qapp: object) -> None:
    scene = SnapScene()
    scene.command_stack.push(SetCanvasPropertyCommand(scene, "canvas_dpi", 72, 150))
    path = tmp_path / "dpi.smk"
    save_project(scene, path, write_thumbnail=False)
    loaded = load_project(path)
    assert loaded.canvas_dpi == 150
    assert SnapScene().canvas_dpi == 72


def test_canvas_preference_controls_reach_the_window(main_window: MainWindow) -> None:
    panel = main_window._property_panel  # noqa: SLF001
    panel._grid_size_spin.setValue(25)
    assert AppSettings().grid_size() == 25
    assert main_window.view._grid_size == 25  # noqa: SLF001
    panel._snap_check.setChecked(True)
    assert AppSettings().snap_to_grid() is True
    assert main_window._snap_grid_action.isChecked()  # noqa: SLF001
    main_window._snap_grid_action.setChecked(False)  # noqa: SLF001
    assert not panel._snap_check.isChecked()
    panel._pasteboard_picker.color = QColor("#101010")
    panel._pasteboard_picker.color_changed.emit(QColor("#101010"))
    assert AppSettings().pasteboard_color() == QColor("#101010")
    assert main_window.view.pasteboard_color == QColor("#101010")


def test_canvas_properties_menu_opens_the_canvas_section(main_window: MainWindow) -> None:
    panel = main_window._property_panel  # noqa: SLF001
    item = RectangleItem(rect=QRectF(0, 0, 10, 10))
    layer = main_window.scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    main_window.scene.addItem(item)
    main_window.selection_manager.select(item)
    panel._canvas_section.set_expanded(False)
    panel.hide()
    menu = build_canvas_context_menu(main_window)
    for action in menu.actions():
        if action.text() == "Canvas Properties...":
            action.trigger()
            break
    else:
        raise AssertionError("Canvas Properties row missing")
    assert panel.isVisibleTo(main_window)
    assert panel._canvas_section.expanded
    assert panel._canvas_section.isVisibleTo(panel)
    assert not main_window.selection_manager.items
