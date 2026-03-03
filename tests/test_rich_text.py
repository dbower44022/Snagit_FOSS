"""Tests for the rich text engine: QTextDocument-based TextItem/CalloutItem."""

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QApplication

from snapmock.commands.move_tail_command import MoveTailCommand
from snapmock.commands.text_edit_command import TextEditCommand
from snapmock.commands.text_format_command import TextFormatCommand
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
    assert item.padding == 8.0
    assert item.vertical_align == VerticalAlign.TOP
    assert item.auto_size is True
    assert item.auto_width is True
    assert item.text_scale_factor == 1.0
    assert item.min_width == 200.0
    assert item.min_height is None
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
    item._auto_width = False
    item._text_scale_factor = 0.5
    item._min_width = 300.0
    item._min_height = 50.0

    data = item.serialize()
    assert data["bg_color"] == "#ffff0000"
    assert data["border_color"] == "#ff00ff00"
    assert data["border_width"] == 2.0
    assert data["border_radius"] == 5.0
    assert data["padding"] == 8.0
    assert data["vertical_align"] == "center"
    assert data["auto_size"] is False
    assert data["height"] == 100.0
    assert data["auto_width"] is False
    assert data["text_scale_factor"] == 0.5
    assert data["min_width"] == 300.0
    assert data["min_height"] == 50.0


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
    item._auto_width = False
    item._text_scale_factor = 0.75
    item._min_width = 300.0
    item._min_height = 60.0

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
    assert restored.auto_width is False
    assert restored.text_scale_factor == 0.75
    assert restored.min_width == 300.0
    assert restored.min_height == 60.0


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
    assert item.padding == 8.0
    assert item.vertical_align == VerticalAlign.TOP
    assert item.auto_size is True
    assert item.auto_width is True
    assert item.text_scale_factor == 1.0
    assert item.min_width == 200.0
    assert item.min_height is None
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
    assert item.border_color == QColor("#333333")
    assert item.border_width == 2.0
    assert item.border_radius == 12.0
    assert item.padding == 10.0
    assert item.vertical_align == VerticalAlign.TOP


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
    assert item.border_radius == 12.0
    assert item.padding == 10.0
    assert item.vertical_align == VerticalAlign.TOP


# --- Phase 1: auto_width, text_scale_factor, min_width, min_height ---


def test_auto_width_property() -> None:
    item = TextItem(text="Hello")
    assert item.auto_width is True
    item.auto_width = False
    assert item.auto_width is False


def test_text_scale_factor_property() -> None:
    item = TextItem(text="Hello")
    assert item.text_scale_factor == 1.0
    item.text_scale_factor = 0.5
    assert item.text_scale_factor == 0.5
    # Clamped to minimum
    item.text_scale_factor = 0.0
    assert item.text_scale_factor == 0.01


def test_min_width_property() -> None:
    item = TextItem(text="Hello")
    assert item.min_width == 200.0
    item.min_width = 300.0
    assert item.min_width == 300.0
    # Clamped to MIN_TEXT_BOX_WIDTH (20.0)
    item.min_width = 5.0
    assert item.min_width == 20.0


def test_min_height_property() -> None:
    item = TextItem(text="Hello")
    assert item.min_height is None
    item.min_height = 50.0
    assert item.min_height == 50.0
    item.min_height = None
    assert item.min_height is None


def test_auto_width_expands_for_long_text(qapp: QApplication) -> None:
    item = TextItem(text="Short")
    item._auto_width = True
    w_short = item._item_width()
    item.text = "This is a much longer line of text that should expand the width"
    w_long = item._item_width()
    assert w_long > w_short


def test_auto_width_respects_min_width(qapp: QApplication) -> None:
    item = TextItem(text="Hi")
    item._auto_width = True
    item._min_width = 200.0
    w = item._item_width()
    assert w >= 200.0


def test_min_height_enforced(qapp: QApplication) -> None:
    item = TextItem(text="Short")
    item._min_height = 200.0
    h = item._frame_height()
    assert h >= 200.0


def test_scale_geometry_scales_min_dimensions(qapp: QApplication) -> None:
    item = TextItem(text="Test")
    item._min_width = 200.0
    item._min_height = 100.0
    item.scale_geometry(2.0, 2.0)
    assert item._min_width == 400.0
    assert item._min_height == 200.0


def test_serialize_new_fields() -> None:
    item = TextItem(text="Test")
    item._auto_width = False
    item._text_scale_factor = 2.0
    item._min_width = 150.0
    item._min_height = 80.0
    data = item.serialize()
    assert data["auto_width"] is False
    assert data["text_scale_factor"] == 2.0
    assert data["min_width"] == 150.0
    assert data["min_height"] == 80.0


def test_deserialize_new_fields_roundtrip() -> None:
    item = TextItem(text="Test")
    item._auto_width = False
    item._text_scale_factor = 1.5
    item._min_width = 250.0
    item._min_height = 70.0
    data = item.serialize()
    restored = TextItem.deserialize(data)
    assert restored.auto_width is False
    assert restored.text_scale_factor == 1.5
    assert restored.min_width == 250.0
    assert restored.min_height == 70.0


def test_deserialize_backward_compat_new_fields() -> None:
    """Legacy data without new fields uses defaults."""
    data = {
        "type": "TextItem",
        "item_id": "legacy3",
        "layer_id": "layer1",
        "pos": [10, 20],
        "text": "Legacy",
        "font_family": "Sans Serif",
        "font_size": 14,
        "color": "#ff000000",
        "width": 200.0,
    }
    item = TextItem.deserialize(data)
    assert item.auto_width is True
    assert item.text_scale_factor == 1.0
    assert item.min_width == 200.0
    assert item.min_height is None


# --- Phase 2: CalloutItem shapes, tail styles, new properties ---


def test_callout_bubble_shape_default() -> None:
    from snapmock.config.constants import BubbleShape

    item = CalloutItem(text="Test")
    assert item.bubble_shape == BubbleShape.ROUNDED_RECT


def test_callout_bubble_shape_setter() -> None:
    from snapmock.config.constants import BubbleShape

    item = CalloutItem(text="Test")
    for shape in BubbleShape:
        item.bubble_shape = shape
        assert item.bubble_shape == shape


def test_callout_tail_style_default() -> None:
    from snapmock.config.constants import TailStyle

    item = CalloutItem(text="Test")
    assert item.tail_style == TailStyle.STRAIGHT


def test_callout_tail_style_setter() -> None:
    from snapmock.config.constants import TailStyle

    item = CalloutItem(text="Test")
    for style in TailStyle:
        item.tail_style = style
        assert item.tail_style == style


def test_callout_tail_width_default() -> None:
    item = CalloutItem(text="Test")
    assert item.tail_width == 20.0


def test_callout_tail_width_clamped() -> None:
    item = CalloutItem(text="Test")
    item.tail_width = 2.0
    assert item.tail_width == 4.0
    item.tail_width = 200.0
    assert item.tail_width == 100.0


def test_callout_tail_base_position_default() -> None:
    item = CalloutItem(text="Test")
    assert item.tail_base_position == 0.5


def test_callout_tail_base_position_clamped() -> None:
    item = CalloutItem(text="Test")
    item.tail_base_position = -0.5
    assert item.tail_base_position == 0.0
    item.tail_base_position = 1.5
    assert item.tail_base_position == 1.0


def test_callout_tail_base_edge_default() -> None:
    from snapmock.config.constants import TailBaseEdge

    item = CalloutItem(text="Test")
    assert item.tail_base_edge == TailBaseEdge.AUTO


def test_callout_tail_control_point() -> None:
    item = CalloutItem(text="Test")
    assert item.tail_control_point is None
    item.tail_control_point = QPointF(50, 100)
    assert item.tail_control_point is not None
    assert item.tail_control_point.x() == 50
    item.tail_control_point = None
    assert item.tail_control_point is None


def test_callout_border_style_default() -> None:
    from snapmock.config.constants import BorderStyle

    item = CalloutItem(text="Test")
    assert item.border_style == BorderStyle.SOLID


def test_callout_auto_height_default() -> None:
    item = CalloutItem(text="Test")
    assert item.auto_height is True


def test_callout_starburst_points_clamped() -> None:
    item = CalloutItem(text="Test")
    item.starburst_points = 5
    assert item.starburst_points == 8
    item.starburst_points = 30
    assert item.starburst_points == 24


def test_callout_serialize_new_properties() -> None:
    from snapmock.config.constants import BorderStyle, BubbleShape, TailBaseEdge, TailStyle

    item = CalloutItem(text="Test")
    item._bubble_shape = BubbleShape.ELLIPSE
    item._tail_style = TailStyle.CURVED
    item._tail_width = 30.0
    item._tail_base_position = 0.3
    item._tail_base_edge = TailBaseEdge.RIGHT
    item._tail_control_point = QPointF(50, 75)
    item._border_style = BorderStyle.DASHED
    item._starburst_points = 16
    item._auto_height = False

    data = item.serialize()
    assert data["bubble_shape"] == "ellipse"
    assert data["tail_style"] == "curved"
    assert data["tail_width"] == 30.0
    assert data["tail_base_position"] == 0.3
    assert data["tail_base_edge"] == "right"
    assert data["tail_control_point"] == [50.0, 75.0]
    assert data["border_style"] == "dashed"
    assert data["starburst_points"] == 16
    assert data["auto_height"] is False


def test_callout_deserialize_new_properties_roundtrip() -> None:
    from snapmock.config.constants import BorderStyle, BubbleShape, TailBaseEdge, TailStyle

    item = CalloutItem(text="Test")
    item._bubble_shape = BubbleShape.STARBURST
    item._tail_style = TailStyle.ELBOW
    item._tail_width = 40.0
    item._tail_base_position = 0.7
    item._tail_base_edge = TailBaseEdge.LEFT
    item._tail_control_point = QPointF(30, 60)
    item._border_style = BorderStyle.DOTTED
    item._starburst_points = 20
    item._auto_height = False

    data = item.serialize()
    restored = CalloutItem.deserialize(data)

    assert restored.bubble_shape == BubbleShape.STARBURST
    assert restored.tail_style == TailStyle.ELBOW
    assert restored.tail_width == 40.0
    assert restored.tail_base_position == 0.7
    assert restored.tail_base_edge == TailBaseEdge.LEFT
    assert restored.tail_control_point is not None
    assert restored.tail_control_point.x() == 30.0
    assert restored.border_style == BorderStyle.DOTTED
    assert restored.starburst_points == 20
    assert restored.auto_height is False


def test_callout_deserialize_backward_compat_new_properties() -> None:
    """Legacy data without new properties uses defaults."""
    from snapmock.config.constants import BorderStyle, BubbleShape, TailBaseEdge, TailStyle

    data = {
        "type": "CalloutItem",
        "item_id": "legacy4",
        "layer_id": "layer1",
        "pos": [10, 20],
        "text": "Old callout",
        "rect": [0, 0, 150, 60],
        "tail_tip": [75, 90],
    }
    item = CalloutItem.deserialize(data)
    assert item.bubble_shape == BubbleShape.ROUNDED_RECT
    assert item.tail_style == TailStyle.STRAIGHT
    assert item.tail_width == 20.0
    assert item.tail_base_position == 0.5
    assert item.tail_base_edge == TailBaseEdge.AUTO
    assert item.tail_control_point is None
    assert item.border_style == BorderStyle.SOLID
    assert item.auto_height is True


def test_callout_combined_path_has_area(qapp: QApplication) -> None:
    item = CalloutItem(text="Test")
    path = item._combined_path()
    assert not path.isEmpty()


def test_callout_scale_geometry_scales_tail_width() -> None:
    item = CalloutItem(text="Test")
    item._tail_width = 20.0
    item._tail_control_point = QPointF(50, 100)
    item.scale_geometry(2.0, 2.0)
    assert item._tail_width == 40.0
    assert item._tail_control_point is not None
    assert item._tail_control_point.x() == 100.0


# --- Phase 4: TextFormatCommand and MoveTailCommand ---


def test_text_format_command_redo(qapp: QApplication) -> None:
    item = TextItem(text="Hello")
    # Capture old bold values for each char
    old_values = {}
    for i in range(5):
        cursor = QTextCursor(item.text_document)
        cursor.setPosition(i)
        cursor.setPosition(i + 1, QTextCursor.MoveMode.KeepAnchor)
        old_values[i] = cursor.charFormat().fontWeight() >= QFont.Weight.Bold

    cmd = TextFormatCommand(item, 0, 5, "bold", old_values, True)
    cmd.redo()

    # All characters should be bold
    for i in range(5):
        cursor = QTextCursor(item.text_document)
        cursor.setPosition(i)
        cursor.setPosition(i + 1, QTextCursor.MoveMode.KeepAnchor)
        assert cursor.charFormat().fontWeight() >= QFont.Weight.Bold


def test_text_format_command_undo(qapp: QApplication) -> None:
    item = TextItem(text="Hello")
    # Store original format values
    old_values = {}
    for i in range(5):
        cursor = QTextCursor(item.text_document)
        cursor.setPosition(i)
        cursor.setPosition(i + 1, QTextCursor.MoveMode.KeepAnchor)
        old_values[i] = False  # not bold

    cmd = TextFormatCommand(item, 0, 5, "bold", old_values, True)
    cmd.redo()
    cmd.undo()

    # Should be restored to not bold
    for i in range(5):
        cursor = QTextCursor(item.text_document)
        cursor.setPosition(i)
        cursor.setPosition(i + 1, QTextCursor.MoveMode.KeepAnchor)
        assert cursor.charFormat().fontWeight() < QFont.Weight.Bold


def test_text_format_command_description() -> None:
    item = TextItem(text="Hello")
    cmd = TextFormatCommand(item, 0, 5, "bold", {}, True)
    assert "bold" in cmd.description.lower()


def test_text_edit_command_no_merge_format_change() -> None:
    item = TextItem(text="Test")
    html1 = item.html()
    item.text = "After1"
    html2 = item.html()
    item.text = "After2"
    html3 = item.html()

    cmd1 = TextEditCommand(item, html1, html2, is_format_change=True)
    cmd2 = TextEditCommand(item, html2, html3)
    assert not cmd1.merge_with(cmd2)


def test_text_edit_command_no_merge_paragraph_op() -> None:
    item = TextItem(text="Test")
    html1 = item.html()
    item.text = "After1"
    html2 = item.html()
    item.text = "After2"
    html3 = item.html()

    cmd1 = TextEditCommand(item, html1, html2)
    cmd2 = TextEditCommand(item, html2, html3, is_paragraph_op=True)
    assert not cmd1.merge_with(cmd2)


def test_move_tail_command_redo() -> None:
    from snapmock.config.constants import TailBaseEdge

    item = CalloutItem(text="Test")
    old_tip = QPointF(100, 160)
    new_tip = QPointF(200, 200)
    item.tail_tip = old_tip

    cmd = MoveTailCommand(item, old_tip, new_tip, 0.5, 0.7, "auto", "bottom")
    cmd.redo()
    assert item.tail_tip.x() == 200.0
    assert item.tail_base_position == 0.7
    assert item.tail_base_edge == TailBaseEdge.BOTTOM


def test_move_tail_command_undo() -> None:
    from snapmock.config.constants import TailBaseEdge

    item = CalloutItem(text="Test")
    old_tip = QPointF(100, 160)
    new_tip = QPointF(200, 200)
    item.tail_tip = old_tip

    cmd = MoveTailCommand(item, old_tip, new_tip, 0.5, 0.7, "auto", "bottom")
    cmd.redo()
    cmd.undo()
    assert item.tail_tip.x() == 100.0
    assert item.tail_base_position == 0.5
    assert item.tail_base_edge == TailBaseEdge.AUTO


def test_move_tail_command_merge() -> None:
    item = CalloutItem(text="Test")
    cmd1 = MoveTailCommand(item, QPointF(100, 160), QPointF(110, 165), 0.5, 0.5, "auto", "auto")
    cmd2 = MoveTailCommand(item, QPointF(110, 165), QPointF(120, 170), 0.5, 0.6, "auto", "auto")
    assert cmd1.merge_with(cmd2)
    # After merge, undo goes back to original
    cmd1.undo()
    assert item.tail_tip.x() == 100.0
    cmd1.redo()
    assert item.tail_tip.x() == 120.0


# --- TextItem hit testing / shape() ---


def test_text_shape_full_rect_with_bg(qapp: QApplication) -> None:
    """With visible background, shape() returns the full frame rect."""
    item = TextItem(text="Hello")
    item.bg_color = QColor("#FFFF0000")  # opaque red
    shape = item.shape()
    br = item.boundingRect()
    # Shape bounding rect should cover the full frame
    assert shape.boundingRect().width() >= br.width() - 1


def test_text_shape_full_rect_with_border(qapp: QApplication) -> None:
    """With visible border, shape() returns the full frame rect."""
    item = TextItem(text="Hello")
    item.border_color = QColor("#FF000000")
    item.border_width = 2.0
    shape = item.shape()
    assert not shape.isEmpty()
    assert shape.boundingRect().width() >= item._item_width() - 1


def test_text_shape_text_only_when_invisible(qapp: QApplication) -> None:
    """With transparent bg and no border, shape() returns just the text area."""
    item = TextItem(text="Hello")
    # Default: bg alpha=0, border_width=0
    shape = item.shape()
    shape_rect = shape.boundingRect()
    frame_w = item._item_width()
    # The shape should be smaller than the full frame (inset by padding)
    assert shape_rect.width() < frame_w


# --- TextItem border_style ---


def test_text_border_style_default() -> None:
    from snapmock.config.constants import BorderStyle

    item = TextItem(text="Test")
    assert item.border_style == BorderStyle.SOLID


def test_text_border_style_setter() -> None:
    from snapmock.config.constants import BorderStyle

    item = TextItem(text="Test")
    for style in BorderStyle:
        item.border_style = style
        assert item.border_style == style


def test_text_border_style_serialize() -> None:
    from snapmock.config.constants import BorderStyle

    item = TextItem(text="Test")
    item.border_style = BorderStyle.DASHED
    data = item.serialize()
    assert data["border_style"] == "dashed"


def test_text_border_style_deserialize_roundtrip() -> None:
    from snapmock.config.constants import BorderStyle

    item = TextItem(text="Test")
    item.border_style = BorderStyle.DOTTED
    data = item.serialize()
    restored = TextItem.deserialize(data)
    assert restored.border_style == BorderStyle.DOTTED


def test_text_border_style_backward_compat() -> None:
    """Legacy data without border_style defaults to SOLID."""
    from snapmock.config.constants import BorderStyle

    data = {
        "type": "TextItem",
        "item_id": "legacy_bs",
        "layer_id": "layer1",
        "pos": [0, 0],
        "text": "Test",
        "width": 200.0,
    }
    item = TextItem.deserialize(data)
    assert item.border_style == BorderStyle.SOLID


def test_move_tail_command_no_merge_different_items() -> None:
    item1 = CalloutItem(text="A")
    item2 = CalloutItem(text="B")
    cmd1 = MoveTailCommand(item1, QPointF(0, 0), QPointF(1, 1), 0.5, 0.5, "auto", "auto")
    cmd2 = MoveTailCommand(item2, QPointF(0, 0), QPointF(1, 1), 0.5, 0.5, "auto", "auto")
    assert not cmd1.merge_with(cmd2)


# --- Paragraph-level formatting ---


def test_set_alignment() -> None:
    item = TextItem(text="Hello World")
    item.set_alignment(Qt.AlignmentFlag.AlignCenter)
    fmt = item.get_block_format()
    assert fmt.alignment() == Qt.AlignmentFlag.AlignCenter


def test_set_alignment_right() -> None:
    item = TextItem(text="Hello")
    item.set_alignment(Qt.AlignmentFlag.AlignRight)
    fmt = item.get_block_format()
    assert fmt.alignment() == Qt.AlignmentFlag.AlignRight


def test_set_space_before() -> None:
    item = TextItem(text="Hello")
    item.set_space_before(12.0)
    fmt = item.get_block_format()
    assert fmt.topMargin() == 12.0


def test_set_space_after() -> None:
    item = TextItem(text="Hello")
    item.set_space_after(8.0)
    fmt = item.get_block_format()
    assert fmt.bottomMargin() == 8.0


def test_set_text_indent() -> None:
    item = TextItem(text="Hello")
    item.set_text_indent(20.0)
    fmt = item.get_block_format()
    assert fmt.textIndent() == 20.0


def test_set_indent_level() -> None:
    item = TextItem(text="Hello")
    item.set_indent(2)
    fmt = item.get_block_format()
    assert fmt.indent() == 2


def test_set_line_height() -> None:
    item = TextItem(text="Hello")
    item.set_line_height(150)
    fmt = item.get_block_format()
    assert fmt.lineHeight() == 150.0


def test_toggle_list_bullet() -> None:
    from PyQt6.QtGui import QTextCursor, QTextListFormat

    item = TextItem(text="Item one")
    cursor = QTextCursor(item.text_document)
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    item.toggle_list(QTextListFormat.Style.ListDisc, cursor)
    assert cursor.currentList() is not None
    assert cursor.currentList().format().style() == QTextListFormat.Style.ListDisc


def test_toggle_list_removes_existing() -> None:
    from PyQt6.QtGui import QTextCursor, QTextListFormat

    item = TextItem(text="Item one")
    cursor = QTextCursor(item.text_document)
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    # Add to list
    item.toggle_list(QTextListFormat.Style.ListDisc, cursor)
    assert cursor.currentList() is not None
    # Toggle off same style
    cursor2 = QTextCursor(item.text_document)
    cursor2.movePosition(QTextCursor.MoveOperation.Start)
    item.toggle_list(QTextListFormat.Style.ListDisc, cursor2)
    assert cursor2.currentList() is None


def test_toggle_list_numbered() -> None:
    from PyQt6.QtGui import QTextCursor, QTextListFormat

    item = TextItem(text="Item one")
    cursor = QTextCursor(item.text_document)
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    item.toggle_list(QTextListFormat.Style.ListDecimal, cursor)
    assert cursor.currentList() is not None
    assert cursor.currentList().format().style() == QTextListFormat.Style.ListDecimal


# --- FindReplaceBar ---


def test_find_replace_bar_find_matches(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="hello world hello")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("hello")
    assert bar.match_count == 2
    assert bar.current_match_index == 0


def test_find_replace_bar_find_next(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="abc abc abc")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("abc")
    assert bar.match_count == 3
    assert bar.current_match_index == 0
    bar.find_next()
    assert bar.current_match_index == 1
    bar.find_next()
    assert bar.current_match_index == 2
    bar.find_next()
    assert bar.current_match_index == 0  # wraps


def test_find_replace_bar_find_prev(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="abc abc abc")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("abc")
    assert bar.current_match_index == 0
    bar.find_prev()
    assert bar.current_match_index == 2  # wraps backward


def test_find_replace_bar_case_sensitive(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="Hello hello HELLO")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("hello")
    assert bar.match_count == 3  # case insensitive by default
    bar._case_cb.setChecked(True)
    assert bar.match_count == 1  # only "hello"


def test_find_replace_bar_no_match(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="Hello world")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("xyz")
    assert bar.match_count == 0
    assert bar.current_match_index == -1


def test_find_replace_bar_replace_all(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="foo bar foo baz foo")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("foo")
    bar._replace_field.setText("qux")
    assert bar.match_count == 3
    bar._replace_all()
    assert item.plain_text() == "qux bar qux baz qux"


def test_find_replace_bar_replace_current(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="aa bb aa")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("aa")
    bar._replace_field.setText("cc")
    assert bar.match_count == 2
    bar._replace_current()  # replaces first match
    assert "cc" in item.plain_text()


def test_find_replace_bar_detach(qapp: QApplication) -> None:
    from snapmock.ui.find_replace_bar import FindReplaceBar

    item = TextItem(text="test")
    bar = FindReplaceBar()
    bar.attach(item.text_document)
    bar._search_field.setText("test")
    assert bar.match_count == 1
    bar.detach()
    assert bar.match_count == 0
