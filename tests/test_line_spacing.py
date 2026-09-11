"""Line Spacing (Text & Callout PRD 2.2; General UI PRD 8.4; Vector Item Properties Phase 2
step 3): the property on the text items, the Property Panel row, and the editing path."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QTextBlockFormat, QTextCursor
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import DEFAULT_LINE_SPACING
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.items.callout_item import CalloutItem
from snapmock.items.text_item import TextItem
from snapmock.main_window import MainWindow
from snapmock.tools.text_tool import TextTool
from snapmock.ui.property_panel import MIXED_TEXT, PropertyPanel

Button = Qt.MouseButton
Modifier = Qt.KeyboardModifier


def _spin(panel: PropertyPanel) -> QDoubleSpinBox:
    spin = panel._line_spacing_spin  # noqa: SLF001
    assert isinstance(spin, QDoubleSpinBox)
    return spin


def test_the_property_reads_and_writes_every_paragraph(qapp: QApplication) -> None:
    for item in (TextItem("one\ntwo"), CalloutItem("one\ntwo")):
        assert item.line_spacing == 1.0  # nothing set: Qt's single spacing
        assert item.paragraph_line_spacings() == [1.0, 1.0]
        item.line_spacing = 2.0
        assert item.paragraph_line_spacings() == [2.0, 2.0]
        item.line_spacing = 9.0
        assert item.line_spacing == 5.0  # clamped to the PRD's range
        item.line_spacing = 0.1
        assert item.line_spacing == 0.5


def test_the_spacing_survives_the_html_round_trip(qapp: QApplication) -> None:
    for item in (TextItem("one\ntwo"), CalloutItem("one\ntwo")):
        item.line_spacing = 1.5
        restored = type(item).deserialize(item.serialize())
        assert restored.paragraph_line_spacings() == [1.5, 1.5]
        assert restored.document_height(300) > item.__class__("one\ntwo").document_height(300)


def test_the_panel_row_is_a_command_and_shows_mixed_paragraphs(qtbot: QtBot) -> None:
    scene = SnapScene()
    sm = SelectionManager(scene)
    panel = PropertyPanel(sm, scene)
    qtbot.addWidget(panel)
    panel.show()
    layer = scene.layer_manager.active_layer
    assert layer is not None
    a = TextItem("one\ntwo")
    b = CalloutItem("three")
    b.setPos(200, 200)
    for item in (a, b):
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    sm.select(a)
    spin = _spin(panel)
    assert spin.value() == 1.0
    assert (spin.minimum(), spin.maximum(), spin.singleStep()) == (0.4, 5.0, 0.1)
    spin.setValue(1.8)
    assert a.paragraph_line_spacings() == [1.8, 1.8]
    assert scene.command_stack.undo_text == "Change line_spacings"
    # One paragraph differs: the row shows the mixed dash
    cursor = QTextCursor(a.text_document)
    cursor.movePosition(QTextCursor.MoveOperation.End)
    fmt = QTextBlockFormat()
    fmt.setLineHeight(300.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
    cursor.mergeBlockFormat(fmt)
    panel._refresh_from_selection()  # noqa: SLF001
    assert spin.text() == MIXED_TEXT
    sm.select_items([a, b])
    spin.setValue(2.5)
    assert a.paragraph_line_spacings() == [2.5, 2.5] and b.line_spacing == 2.5
    assert scene.command_stack.undo_text == "Change line spacing"
    scene.command_stack.undo()
    assert b.line_spacing == 1.0 and a.paragraph_line_spacings() == [1.8, 3.0]


def test_a_new_text_box_takes_the_prd_default_and_editing_sets_the_paragraph(
    main_window: MainWindow,
) -> None:
    tm = main_window.tool_manager
    tm.activate("text")
    tool = tm.tool("text")
    assert isinstance(tool, TextTool)
    assert tool.creation_defaults["line_spacing"] == DEFAULT_LINE_SPACING
    panel = main_window._property_panel  # noqa: SLF001
    assert _spin(panel).value() == DEFAULT_LINE_SPACING  # tool-defaults mode
    view_pos = QPointF(main_window.view.mapFromScene(QPointF(40, 40)))
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        view_pos,
        Button.LeftButton,
        Button.LeftButton,
        Modifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        view_pos,
        Button.LeftButton,
        Button.LeftButton,
        Modifier.NoModifier,
    )
    tm.handle_mouse_press(press)
    tm.handle_mouse_release(release)
    item = tool.editing_item
    assert isinstance(item, TextItem)
    assert item.line_spacing == DEFAULT_LINE_SPACING
    editor = tool.active_editor
    assert editor is not None
    # Editing: the row writes the paragraph at the cursor, no command yet
    count = main_window.scene.command_stack.count
    _spin(panel).setValue(2.0)
    assert item.paragraph_line_spacings() == [2.0]
    assert main_window.scene.command_stack.count == count
    assert editor.textCursor().blockFormat().lineHeight() == 200.0
