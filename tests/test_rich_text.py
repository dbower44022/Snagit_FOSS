"""Tests for the rich text engine: QTextDocument-based TextItem/CalloutItem."""

import pytest
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QApplication

from snapmock.commands.text_edit_command import TextEditCommand
from snapmock.config.constants import VerticalAlign
from snapmock.core.scene import SnapScene
from snapmock.items.callout_item import CalloutItem
from snapmock.items.text_item import TextItem

# --- Document creation ---


def test_text_item_creates_document() -> None:
    item = TextItem(text="Hello")
    assert item.text_document is not None
    assert item.plain_text() == "Hello"


def test_callout_item_creates_document() -> None:
    item = CalloutItem(text="Note")
    assert item.text_document is not None
    assert item.plain_text() == "Note"


# --- Backward-compat property shims ---


def test_text_property_getter_returns_plain_text() -> None:
    item = TextItem(text="Hello World")
    assert item.text == "Hello World"


def test_text_property_setter_updates_document() -> None:
    item = TextItem(text="Before")
    item.text = "After"
    assert item.plain_text() == "After"


def test_font_property_getter() -> None:
    item = TextItem(text="Test")
    f = item.font
    assert f.family() == item.text_document.defaultFont().family()
    assert f.pointSize() == item.text_document.defaultFont().pointSize()


def test_font_property_setter() -> None:
    item = TextItem(text="Test")
    new_font = QFont("Monospace", 24)
    item.font = new_font
    assert item.text_document.defaultFont().pointSize() == 24


def test_text_color_property_getter() -> None:
    item = TextItem(text="Color test")
    color = item.text_color
    assert isinstance(color, QColor)


def test_text_color_property_setter() -> None:
    item = TextItem(text="Color test")
    item.text_color = QColor("#FF0000")
    assert item.text_color == QColor("#FF0000")


# --- HTML round-trip ---


def test_html_roundtrip() -> None:
    item = TextItem(text="Hello")
    original_html = item.html()
    assert "Hello" in original_html

    # Modify via HTML
    item.set_html(original_html.replace("Hello", "World"))
    assert item.plain_text() == "World"


def test_html_preserves_formatting() -> None:
    item = TextItem(text="Test")
    # Apply bold to the document
    cursor = QTextCursor(item.text_document)
    cursor.select(QTextCursor.SelectionType.Document)
    fmt = QTextCharFormat()
    fmt.setFontWeight(QFont.Weight.Bold)
    cursor.mergeCharFormat(fmt)

    html = item.html()
    assert "bold" in html.lower() or "font-weight" in html.lower()


# --- is_editing flag ---


def test_is_editing_default_false() -> None:
    item = TextItem(text="Test")
    assert not item.is_editing


def test_is_editing_setter() -> None:
    item = TextItem(text="Test")
    item.is_editing = True
    assert item.is_editing
    item.is_editing = False
    assert not item.is_editing


# --- TextEditCommand ---


def test_text_edit_command_redo() -> None:
    item = TextItem(text="Old")
    old_html = item.html()
    item.text = "New"
    new_html = item.html()

    # Reset to old
    item.set_html(old_html)
    assert item.plain_text() == "Old"

    cmd = TextEditCommand(item, old_html, new_html)
    cmd.redo()
    assert item.plain_text() == "New"


def test_text_edit_command_undo() -> None:
    item = TextItem(text="Old")
    old_html = item.html()
    item.text = "New"
    new_html = item.html()

    cmd = TextEditCommand(item, old_html, new_html)
    # Don't need to call redo here, just test undo
    cmd.undo()
    assert item.plain_text() == "Old"


def test_text_edit_command_merge() -> None:
    item = TextItem(text="First")
    html_first = item.html()
    item.text = "Second"
    html_second = item.html()
    item.text = "Third"
    html_third = item.html()

    cmd1 = TextEditCommand(item, html_first, html_second)
    cmd2 = TextEditCommand(item, html_second, html_third)

    assert cmd1.merge_with(cmd2)
    # After merge, undo should go back to "First"
    cmd1.undo()
    assert item.plain_text() == "First"
    # And redo should go to "Third"
    cmd1.redo()
    assert item.plain_text() == "Third"


def test_text_edit_command_no_merge_different_items() -> None:
    item1 = TextItem(text="A")
    item2 = TextItem(text="B")
    cmd1 = TextEditCommand(item1, item1.html(), item1.html())
    cmd2 = TextEditCommand(item2, item2.html(), item2.html())
    assert not cmd1.merge_with(cmd2)


# --- Serialization ---


def test_text_item_serialize_has_html_field() -> None:
    item = TextItem(text="Hello")
    data = item.serialize()
    assert "html" in data
    assert "text" in data  # backward compat
    assert data["text"] == "Hello"


def test_text_item_deserialize_from_html() -> None:
    item = TextItem(text="Hello")
    data = item.serialize()
    restored = TextItem.deserialize(data)
    assert restored.plain_text() == "Hello"
    assert "html" in data


def test_text_item_deserialize_from_legacy() -> None:
    """Deserialize from old plain-text format (no html key)."""
    data = {
        "type": "TextItem",
        "item_id": "abc123",
        "layer_id": "layer1",
        "pos": [10, 20],
        "text": "Legacy text",
        "font_family": "Monospace",
        "font_size": 16,
        "color": "#ffff0000",
        "width": 300.0,
    }
    item = TextItem.deserialize(data)
    assert item.plain_text() == "Legacy text"
    assert item.text_document.defaultFont().pointSize() == 16
    assert item._width == 300.0


def test_callout_serialize_has_html_field() -> None:
    item = CalloutItem(text="Note")
    data = item.serialize()
    assert "html" in data
    assert "text" in data
    assert data["text"] == "Note"


def test_callout_deserialize_from_html() -> None:
    item = CalloutItem(text="Note")
    data = item.serialize()
    restored = CalloutItem.deserialize(data)
    assert restored.plain_text() == "Note"


def test_callout_deserialize_from_legacy() -> None:
    """Deserialize from old plain-text format (no html key)."""
    data = {
        "type": "CalloutItem",
        "item_id": "def456",
        "layer_id": "layer1",
        "pos": [10, 20],
        "text": "Legacy callout",
        "rect": [0, 0, 150, 60],
        "tail_tip": [75, 90],
        "bg_color": "#ffffff00",
        "border_color": "#ff000000",
        "font_family": "Monospace",
        "font_size": 18,
        "text_color": "#ff00ff00",
    }
    item = CalloutItem.deserialize(data)
    assert item.plain_text() == "Legacy callout"
    assert item.text_document.defaultFont().pointSize() == 18


# --- BoundingRect uses document ---


def test_text_item_bounding_rect_positive(qapp: QApplication) -> None:
    item = TextItem(text="Hello World")
    br = item.boundingRect()
    assert br.width() > 0
    assert br.height() > 0


def test_text_item_bounding_rect_changes_with_font(qapp: QApplication) -> None:
    item = TextItem(text="Hello")
    br_small = item.boundingRect()
    item.font = QFont("Sans Serif", 36)
    br_large = item.boundingRect()
    assert br_large.height() > br_small.height()


# --- document_height ---


def test_document_height(qapp: QApplication) -> None:
    item = TextItem(text="Hello World " * 20)
    h_wide = item.document_height(1000)
    h_narrow = item.document_height(50)
    assert h_narrow > h_wide


# --- Empty text removal integration ---


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def test_text_edit_command_pushed_to_stack(scene: SnapScene) -> None:
    """TextEditCommand can be pushed to the command stack."""
    item = TextItem(text="Before")
    scene.addItem(item)
    old_html = item.html()
    item.text = "After"
    new_html = item.html()

    # Revert and push
    item.set_html(old_html)
    cmd = TextEditCommand(item, old_html, new_html)
    scene.command_stack.push(cmd)
    assert item.plain_text() == "After"

    scene.command_stack.undo()
    assert item.plain_text() == "Before"

    scene.command_stack.redo()
    assert item.plain_text() == "After"


# --- Frame property defaults ---


def test_frame_property_defaults() -> None:
    item = TextItem(text="Hello")
    assert item.bg_color.alpha() == 0
    assert item.border_color.alpha() == 0
    assert item.border_width == 0.0
    assert item.border_radius == 0.0
    assert item.padding == 4.0
    assert item.vertical_align == VerticalAlign.TOP
    assert item.auto_size is True
    assert item.text_height is None


# --- Frame property setters + clamping ---


def test_bg_color_setter() -> None:
    item = TextItem(text="Test")
    item.bg_color = QColor("#FF0000FF")
    assert item.bg_color == QColor("#FF0000FF")


def test_border_color_setter() -> None:
    item = TextItem(text="Test")
    item.border_color = QColor("#FF00FF00")
    assert item.border_color == QColor("#FF00FF00")


def test_border_width_clamped() -> None:
    item = TextItem(text="Test")
    item.border_width = -5.0
    assert item.border_width == 0.0
    item.border_width = 3.0
    assert item.border_width == 3.0


def test_border_radius_clamped() -> None:
    item = TextItem(text="Test")
    item.border_radius = -10.0
    assert item.border_radius == 0.0
    item.border_radius = 8.0
    assert item.border_radius == 8.0


def test_padding_clamped() -> None:
    item = TextItem(text="Test")
    item.padding = -1.0
    assert item.padding == 0.0
    item.padding = 10.0
    assert item.padding == 10.0


def test_vertical_align_setter() -> None:
    item = TextItem(text="Test")
    item.vertical_align = VerticalAlign.CENTER
    assert item.vertical_align == VerticalAlign.CENTER
    item.vertical_align = VerticalAlign.BOTTOM
    assert item.vertical_align == VerticalAlign.BOTTOM


def test_auto_size_resets_height() -> None:
    item = TextItem(text="Test")
    item._height = 100.0
    item._auto_size = False
    item.auto_size = True
    assert item.text_height is None
    assert item.auto_size is True


def test_text_height_setter() -> None:
    item = TextItem(text="Test")
    item.text_height = 150.0
    assert item.text_height == 150.0
    item.text_height = None
    assert item.text_height is None


# --- Serialization with frame properties ---


def test_serialize_includes_frame_properties() -> None:
    item = TextItem(text="Hello")
    item.bg_color = QColor("#FFFF0000")
    item.border_color = QColor("#FF00FF00")
    item.border_width = 2.0
    item.border_radius = 5.0
    item.padding = 8.0
    item.vertical_align = VerticalAlign.CENTER
    item._auto_size = False
    item._height = 100.0

    data = item.serialize()
    assert data["bg_color"] == "#ffff0000"
    assert data["border_color"] == "#ff00ff00"
    assert data["border_width"] == 2.0
    assert data["border_radius"] == 5.0
    assert data["padding"] == 8.0
    assert data["vertical_align"] == "center"
    assert data["auto_size"] is False
    assert data["height"] == 100.0


def test_deserialize_frame_properties_roundtrip() -> None:
    item = TextItem(text="Hello")
    item.bg_color = QColor("#FFFF0000")
    item.border_color = QColor("#FF00FF00")
    item.border_width = 2.0
    item.border_radius = 5.0
    item.padding = 8.0
    item.vertical_align = VerticalAlign.CENTER
    item._auto_size = False
    item._height = 100.0

    data = item.serialize()
    restored = TextItem.deserialize(data)

    assert restored.bg_color == QColor("#FFFF0000")
    assert restored.border_color == QColor("#FF00FF00")
    assert restored.border_width == 2.0
    assert restored.border_radius == 5.0
    assert restored.padding == 8.0
    assert restored.vertical_align == VerticalAlign.CENTER
    assert restored.auto_size is False
    assert restored.text_height == 100.0


def test_deserialize_backward_compat_no_frame_keys() -> None:
    """Legacy data without frame keys should use transparent defaults."""
    data = {
        "type": "TextItem",
        "item_id": "legacy1",
        "layer_id": "layer1",
        "pos": [10, 20],
        "text": "Old text",
        "font_family": "Sans Serif",
        "font_size": 14,
        "color": "#ff000000",
        "width": 200.0,
    }
    item = TextItem.deserialize(data)
    assert item.bg_color.alpha() == 0
    assert item.border_color.alpha() == 0
    assert item.border_width == 0.0
    assert item.border_radius == 0.0
    assert item.padding == 4.0
    assert item.vertical_align == VerticalAlign.TOP
    assert item.auto_size is True
    assert item.text_height is None


# --- Auto-size vs fixed height ---


def test_auto_size_height_grows_with_content(qapp: QApplication) -> None:
    item = TextItem(text="Short")
    h_short = item._frame_height()
    item.text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    h_long = item._frame_height()
    assert h_long > h_short


def test_fixed_height_respects_explicit_height(qapp: QApplication) -> None:
    item = TextItem(text="Hello")
    item._auto_size = False
    item._height = 200.0
    assert item._frame_height() == 200.0


# --- BoundingRect includes padding and border_width ---


def test_bounding_rect_includes_padding(qapp: QApplication) -> None:
    item = TextItem(text="Hello")
    item.padding = 20.0
    br = item.boundingRect()
    # Width should be at least the item width
    assert br.width() >= item._width


def test_bounding_rect_expands_for_border_width(qapp: QApplication) -> None:
    item = TextItem(text="Hello")
    br_no_border = item.boundingRect()
    item.border_width = 4.0
    br_with_border = item.boundingRect()
    # With border, bounding rect should be wider by border_width
    assert br_with_border.width() > br_no_border.width()


# --- VerticalAlign serialization ---


def test_vertical_align_serialize_roundtrip() -> None:
    for va in VerticalAlign:
        item = TextItem(text="Test")
        item.vertical_align = va
        data = item.serialize()
        restored = TextItem.deserialize(data)
        assert restored.vertical_align == va


# --- CalloutItem frame property defaults ---


def test_callout_frame_property_defaults() -> None:
    item = CalloutItem(text="Test")
    assert item.bg_color == QColor("#FFFFCC")
    assert item.border_color == QColor("#000000")
    assert item.border_width == 2.0
    assert item.border_radius == 4.0
    assert item.padding == 4.0
    assert item.vertical_align == VerticalAlign.CENTER


# --- CalloutItem frame property setters ---


def test_callout_bg_color_setter() -> None:
    item = CalloutItem(text="Test")
    item.bg_color = QColor("#FF0000FF")
    assert item.bg_color == QColor("#FF0000FF")


def test_callout_border_color_setter() -> None:
    item = CalloutItem(text="Test")
    item.border_color = QColor("#FF00FF00")
    assert item.border_color == QColor("#FF00FF00")


def test_callout_border_width_clamped() -> None:
    item = CalloutItem(text="Test")
    item.border_width = -5.0
    assert item.border_width == 0.0
    item.border_width = 3.0
    assert item.border_width == 3.0


def test_callout_border_radius_clamped() -> None:
    item = CalloutItem(text="Test")
    item.border_radius = -10.0
    assert item.border_radius == 0.0
    item.border_radius = 8.0
    assert item.border_radius == 8.0


def test_callout_padding_clamped() -> None:
    item = CalloutItem(text="Test")
    item.padding = -1.0
    assert item.padding == 0.0
    item.padding = 10.0
    assert item.padding == 10.0


def test_callout_vertical_align_setter() -> None:
    item = CalloutItem(text="Test")
    item.vertical_align = VerticalAlign.TOP
    assert item.vertical_align == VerticalAlign.TOP
    item.vertical_align = VerticalAlign.BOTTOM
    assert item.vertical_align == VerticalAlign.BOTTOM


# --- CalloutItem serialization with frame properties ---


def test_callout_serialize_frame_properties() -> None:
    item = CalloutItem(text="Note")
    item.bg_color = QColor("#FFFF0000")
    item.border_color = QColor("#FF00FF00")
    item.border_width = 3.0
    item.border_radius = 8.0
    item.padding = 6.0
    item.vertical_align = VerticalAlign.BOTTOM

    data = item.serialize()
    assert data["bg_color"] == "#ffff0000"
    assert data["border_color"] == "#ff00ff00"
    assert data["border_width"] == 3.0
    assert data["border_radius"] == 8.0
    assert data["padding"] == 6.0
    assert data["vertical_align"] == "bottom"


def test_callout_deserialize_frame_properties_roundtrip() -> None:
    item = CalloutItem(text="Note")
    item.bg_color = QColor("#FFFF0000")
    item.border_color = QColor("#FF00FF00")
    item.border_width = 3.0
    item.border_radius = 8.0
    item.padding = 6.0
    item.vertical_align = VerticalAlign.BOTTOM

    data = item.serialize()
    restored = CalloutItem.deserialize(data)

    assert restored.bg_color == QColor("#FFFF0000")
    assert restored.border_color == QColor("#FF00FF00")
    assert restored.border_width == 3.0
    assert restored.border_radius == 8.0
    assert restored.padding == 6.0
    assert restored.vertical_align == VerticalAlign.BOTTOM


def test_callout_deserialize_backward_compat() -> None:
    """Legacy data without frame keys loads with defaults."""
    data = {
        "type": "CalloutItem",
        "item_id": "legacy2",
        "layer_id": "layer1",
        "pos": [10, 20],
        "text": "Old callout",
        "rect": [0, 0, 150, 60],
        "tail_tip": [75, 90],
        "bg_color": "#ffffff00",
        "border_color": "#ff000000",
        "font_family": "Sans Serif",
        "font_size": 14,
        "text_color": "#ff000000",
    }
    item = CalloutItem.deserialize(data)
    assert item.border_width == 2.0
    assert item.border_radius == 4.0
    assert item.padding == 4.0
    assert item.vertical_align == VerticalAlign.CENTER
