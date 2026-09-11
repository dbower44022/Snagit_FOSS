"""NumberedStepItem (Numbered Steps, Stamps & Emoji PRD Section 2) and the shadow helper."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from snapmock.config.constants import (
    DEFAULT_BADGE_COLOR,
    MARKER_MIN_HIT_SIZE,
    BadgeShape,
    BorderStyle,
    DisplayMode,
    FontWeight,
    LabelPosition,
)
from snapmock.items.numbered_step_item import NumberedStepItem, letter_for, roman_for
from snapmock.items.shadow import SHADOW_KEYS, blur_image
from snapmock.items.vector_item import VectorItem

SIZE = 300
ORIGIN = QPointF(150, 180)


def _render(item: NumberedStepItem) -> QImage:
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.translate(ORIGIN)
    item.paint(painter, None)
    painter.end()
    return image


def _pixel(image: QImage, local: QPointF) -> QColor:
    return image.pixelColor(int(ORIGIN.x() + local.x()), int(ORIGIN.y() + local.y()))


# --- the class and its defaults (Sections 2.1 and 2.4) ---


def test_numbered_step_is_a_vector_item_with_the_prd_defaults(qapp: QApplication) -> None:
    item = NumberedStepItem()
    assert isinstance(item, VectorItem)
    assert item.number_value == 1
    assert item.display_mode is DisplayMode.NUMBER
    assert item.badge_shape is BadgeShape.CIRCLE
    assert item.badge_color.name() == DEFAULT_BADGE_COLOR.lower()
    assert item.badge_size == 32.0
    assert item.text_color.name() == "#ffffff"
    assert item.font_family == "Arial"
    assert item.font_size == 0.0
    assert item.font_weight is FontWeight.BOLD
    assert item.border_color.name() == "#ffffff"
    assert item.border_width == 2.0
    assert item.border_style is BorderStyle.SOLID
    assert item.shadow_enabled is True
    assert item.shadow_color.name(QColor.NameFormat.HexArgb) == "#66000000"
    assert (item.shadow_offset_x, item.shadow_offset_y, item.shadow_blur) == (2.0, 2.0, 4.0)
    assert item.label_text == ""
    assert item.label_position is LabelPosition.RIGHT
    assert item.label_font_size == 12.0
    assert item.label_color.name() == "#000000"
    assert item.label_background.name(QColor.NameFormat.HexArgb) == "#ccffffff"
    assert item.label_background_enabled is False
    assert (item.fill_opacity, item.stroke_opacity) == (1.0, 1.0)
    assert item.type_name == "Numbered Step"


def test_badge_colour_and_border_are_the_vector_fill_and_stroke(qapp: QApplication) -> None:
    item = NumberedStepItem()
    item.badge_color = QColor("#123456")
    item.border_color = QColor("#abcdef")
    item.border_width = 3.5
    assert item.fill_color.name() == "#123456"
    assert item.stroke_color.name() == "#abcdef"
    assert item.stroke_width == 3.5
    item.fill_color = QColor("#654321")
    assert item.badge_color.name() == "#654321"


def test_badge_size_is_clamped_to_the_prd_range(qapp: QApplication) -> None:
    item = NumberedStepItem(badge_size=4.0)
    assert item.badge_size == 16.0
    item.badge_size = 500.0
    assert item.badge_size == 128.0


# --- the eight shapes (Section 2.5) ---


@pytest.mark.parametrize("shape", list(BadgeShape))
def test_every_shape_has_a_bounding_rect_and_a_shape_path(
    qapp: QApplication, shape: BadgeShape
) -> None:
    item = NumberedStepItem(badge_size=48.0)
    item.badge_shape = shape
    item.shadow_enabled = False
    body = item.badge_path().boundingRect()
    if shape is BadgeShape.STAR:
        assert body.width() == pytest.approx(48.0 * 0.951, abs=0.5)  # the points' span
    else:
        assert body.width() == pytest.approx(48.0, abs=0.5)
    if shape is BadgeShape.OVAL:
        assert body.height() == pytest.approx(48.0 * 0.7, abs=0.5)
    elif shape is BadgeShape.PIN:
        assert body.height() > 48.0
    elif shape is BadgeShape.HEXAGON:
        assert body.height() == pytest.approx(48.0 * 0.866, abs=0.5)
    elif shape is BadgeShape.STAR:
        assert body.height() == pytest.approx(48.0 * 0.905, abs=0.5)  # top point to feet
    else:
        assert body.height() == pytest.approx(48.0, abs=3.0)
    assert item.boundingRect().contains(body)
    assert item.shape().contains(item.badge_center())
    assert item.boundingRect().contains(item.shape().boundingRect())


def test_pin_anchors_at_its_point_and_the_head_sits_above(qapp: QApplication) -> None:
    item = NumberedStepItem(badge_size=40.0)
    item.badge_shape = BadgeShape.PIN
    path = item.badge_path()
    assert path.contains(QPointF(0.0, -1.0))
    assert path.boundingRect().bottom() == pytest.approx(0.0, abs=0.01)
    assert item.badge_center() == QPointF(0.0, -40.0)
    assert item.badge_rect().center() == item.badge_center()
    circle = NumberedStepItem(badge_size=40.0)
    assert circle.badge_center() == QPointF(0.0, 0.0)


def test_small_badges_keep_a_24_px_hit_area(qapp: QApplication) -> None:
    item = NumberedStepItem(badge_size=16.0)
    rect = item.shape().boundingRect()
    assert rect.width() >= MARKER_MIN_HIT_SIZE
    assert rect.height() >= MARKER_MIN_HIT_SIZE
    assert item.shape().contains(QPointF(11.0, 11.0))
    big = NumberedStepItem(badge_size=64.0)
    assert not big.shape().contains(QPointF(31.0, 31.0))  # outside the circle


# --- the display modes (Section 2.3) ---


def test_letter_mode_runs_a_to_z_then_aa(qapp: QApplication) -> None:
    letters = [letter_for(n) for n in range(1, 27)]
    assert letters == [chr(ord("A") + i) for i in range(26)]
    assert (letter_for(27), letter_for(28), letter_for(52), letter_for(53)) == (
        "AA",
        "AB",
        "AZ",
        "BA",
    )
    assert letter_for(0) == "0"


def test_roman_mode_covers_one_to_3999() -> None:
    assert [roman_for(n) for n in range(1, 11)] == [
        "I",
        "II",
        "III",
        "IV",
        "V",
        "VI",
        "VII",
        "VIII",
        "IX",
        "X",
    ]
    assert (roman_for(14), roman_for(40), roman_for(90), roman_for(400)) == (
        "XIV",
        "XL",
        "XC",
        "CD",
    )
    assert (roman_for(1994), roman_for(3999)) == ("MCMXCIV", "MMMCMXCIX")
    assert (roman_for(4000), roman_for(0)) == ("4000", "0")


def test_display_string_follows_the_mode(qapp: QApplication) -> None:
    item = NumberedStepItem(number_value=3)
    assert item.display_string() == "3"
    item.display_mode = DisplayMode.LETTER
    assert item.display_string() == "C"
    item.display_mode = DisplayMode.ROMAN
    assert item.display_string() == "III"
    item.display_mode = DisplayMode.TEXT
    item.custom_text = "OK"
    assert item.display_string() == "OK"


# --- auto font sizing (Section 2.9) ---


@pytest.mark.parametrize("size", [16.0, 128.0])
def test_auto_font_size_fits_the_badge(qapp: QApplication, size: float) -> None:
    item = NumberedStepItem(number_value=8, badge_size=size)
    pixel = item.auto_font_pixel_size()
    assert 4.0 <= pixel <= size * 0.55 + 0.01
    item.number_value = 888
    assert item.auto_font_pixel_size() < pixel  # three digits shrink the text
    assert item.auto_font_pixel_size() >= 4.0


def test_explicit_font_size_is_used_as_given(qapp: QApplication) -> None:
    item = NumberedStepItem()
    item.font_size = 9.0
    assert item._badge_font().pointSizeF() == pytest.approx(9.0)  # noqa: SLF001


# --- the label line (Section 2.6) ---


@pytest.mark.parametrize("position", list(LabelPosition))
def test_label_sits_on_the_configured_side(qapp: QApplication, position: LabelPosition) -> None:
    item = NumberedStepItem(badge_size=32.0)
    item.label_text = "Click Login"
    item.label_position = position
    badge = item.badge_rect()
    label = item.label_rect()
    assert not label.isNull()
    if position is LabelPosition.RIGHT:
        assert label.left() > badge.right()
    elif position is LabelPosition.LEFT:
        assert label.right() < badge.left()
    elif position is LabelPosition.TOP:
        assert label.bottom() < badge.top()
    else:
        assert label.top() > badge.bottom()
    assert item.boundingRect().contains(label)
    assert item.shape().contains(label.center())


def test_no_label_means_no_label_rect(qapp: QApplication) -> None:
    item = NumberedStepItem()
    assert item.label_rect().isNull()
    item.label_text = "x"
    assert not item.label_rect().isNull()
    item.label_background_enabled = True
    padded = item.label_rect()
    item.label_background_enabled = False
    assert padded.width() > item.label_rect().width()


# --- rendering (Section 2.9) ---


def test_rendered_badge_colour_at_the_centre_and_border_at_the_edge(
    qapp: QApplication,
) -> None:
    item = NumberedStepItem(badge_size=64.0)
    item.badge_shape = BadgeShape.SQUARE
    item.display_mode = DisplayMode.TEXT  # no glyph over the sampled centre
    item.custom_text = ""
    item.border_color = QColor("#0000ff")
    item.border_width = 4.0
    image = _render(item)
    assert _pixel(image, QPointF(0, 0)).name() == DEFAULT_BADGE_COLOR.lower()
    assert _pixel(image, QPointF(32, 0)).name() == "#0000ff"


def test_shadow_paints_outside_the_badge_when_enabled(qapp: QApplication) -> None:
    item = NumberedStepItem(badge_size=64.0)
    item.badge_shape = BadgeShape.SQUARE
    item.shadow_offset_x = 8.0
    item.shadow_offset_y = 8.0
    item.shadow_blur = 2.0
    with_shadow = _render(item)
    item.shadow_enabled = False
    without = _render(item)
    probe = QPointF(37.0, 37.0)  # beyond the square's corner, inside the shadow's
    assert _pixel(without, probe).name() == "#ffffff"
    assert _pixel(with_shadow, probe).name() != "#ffffff"
    assert item.boundingRect().contains(probe) is False
    item.shadow_enabled = True
    assert item.boundingRect().contains(probe)


def test_fill_and_stroke_opacity_lighten_the_paint(qapp: QApplication) -> None:
    item = NumberedStepItem(badge_size=64.0)
    item.badge_shape = BadgeShape.SQUARE
    item.display_mode = DisplayMode.TEXT
    item.shadow_enabled = False
    item.border_color = QColor("#0000ff")
    item.border_width = 4.0
    solid = _render(item)
    item.fill_opacity = 0.5
    item.stroke_opacity = 0.5
    faded = _render(item)
    assert _pixel(faded, QPointF(0, 0)).red() > _pixel(solid, QPointF(0, 0)).red()
    assert _pixel(faded, QPointF(32, 0)).red() > _pixel(solid, QPointF(32, 0)).red()


def test_blur_image_spreads_a_hard_edge() -> None:
    image = QImage(20, 20, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.fillRect(5, 5, 10, 10, QColor("black"))
    painter.end()
    blurred = blur_image(image, 3.0)
    assert blurred.pixelColor(3, 10).alpha() > 0  # outside the original square
    assert blurred.pixelColor(10, 10).alpha() < 255  # the centre lost some weight
    assert blur_image(image, 0.1).pixelColor(3, 10).alpha() == 0  # a tiny radius is a copy


# --- geometry scaling and cloning ---


def test_scale_geometry_scales_the_badge_and_the_fonts(qapp: QApplication) -> None:
    item = NumberedStepItem(badge_size=32.0)
    item.font_size = 10.0
    item.label_font_size = 12.0
    item.scale_geometry(2.0, 2.0)
    assert item.badge_size == 64.0
    assert item.font_size == 20.0
    assert item.label_font_size == 24.0
    assert item.border_width == 4.0


def test_clone_copies_every_property_with_a_new_id(qapp: QApplication) -> None:
    item = NumberedStepItem(number_value=5)
    item.label_text = "Go"
    item.badge_shape = BadgeShape.STAR
    copy = item.clone()
    assert isinstance(copy, NumberedStepItem)
    assert copy.item_id != item.item_id
    assert copy.number_value == 5
    assert copy.label_text == "Go"
    assert copy.badge_shape is BadgeShape.STAR


# --- serialization (Sections 5 and 7) ---


def test_serialize_writes_the_section_5_keys_and_round_trips(qapp: QApplication) -> None:
    item = NumberedStepItem(number_value=7, badge_size=40.0)
    item.setPos(10, 20)
    item.display_mode = DisplayMode.ROMAN
    item.custom_text = "AB"
    item.badge_shape = BadgeShape.HEXAGON
    item.badge_color = QColor("#112233")
    item.text_color = QColor("#445566")
    item.font_family = "DejaVu Sans"
    item.font_size = 11.0
    item.font_weight = FontWeight.NORMAL
    item.border_color = QColor("#778899")
    item.border_width = 3.0
    item.border_style = BorderStyle.DASHDOT
    item.fill_opacity = 0.75
    item.stroke_opacity = 0.25
    item.shadow_enabled = False
    item.shadow_color = QColor("#80ff0000")
    item.shadow_offset_x = 5.0
    item.shadow_offset_y = -3.0
    item.shadow_blur = 1.5
    item.label_text = "Click"
    item.label_position = LabelPosition.BOTTOM
    item.label_font_size = 9.0
    item.label_color = QColor("#0000aa")
    item.label_background = QColor("#8000ff00")
    item.label_background_enabled = True
    item.flip_horizontal = True
    data = item.serialize()
    assert data["type"] == "NumberedStepItem"
    expected_keys = {
        "number_value",
        "display_mode",
        "custom_text",
        "badge_shape",
        "badge_color",
        "badge_size",
        "text_color",
        "font_family",
        "font_size",
        "font_weight",
        "border_color",
        "border_width",
        "border_style",
        "fill_opacity",
        "stroke_opacity",
        "label_text",
        "label_position",
        "label_font_size",
        "label_color",
        "label_background",
        "label_background_enabled",
        *SHADOW_KEYS,
    }
    assert expected_keys <= set(data)
    assert "stroke_color" not in data and "fill_color" not in data
    assert data["display_mode"] == "roman"
    assert data["badge_shape"] == "hexagon"
    assert data["font_weight"] == "normal"
    assert data["border_style"] == "dashdot"
    assert data["label_position"] == "bottom"
    restored = NumberedStepItem.deserialize(data)
    assert restored.serialize() == data
    assert restored.pos() == QPointF(10, 20)
    assert restored.badge_shape is BadgeShape.HEXAGON
    assert restored.shadow_enabled is False
    assert restored.shadow_offset_y == -3.0
    assert restored.label_background_enabled is True
    assert restored.flip_horizontal is True


def test_deserialize_reads_the_first_pass_stub_keys(qapp: QApplication) -> None:
    """A file saved before this work carried ``number`` and ``bg_color`` (silence 2)."""
    old = {
        "type": "NumberedStepItem",
        "item_id": "abc",
        "layer_id": "L1",
        "pos": [5, 6],
        "number": 9,
        "bg_color": "#ffff0000",
        "flip_horizontal": True,
        "flip_vertical": False,
    }
    item = NumberedStepItem.deserialize(old)
    assert item.item_id == "abc"
    assert item.number_value == 9
    assert item.badge_color.name() == "#ff0000"
    assert item.border_color.name() == "#ffffff"
    assert item.flip_horizontal is True
    assert item.pos() == QPointF(5, 6)


def test_deserialize_ignores_unknown_enum_values(qapp: QApplication) -> None:
    item = NumberedStepItem.deserialize(
        {"type": "NumberedStepItem", "badge_shape": "blob", "display_mode": "emoji"}
    )
    assert item.badge_shape is BadgeShape.CIRCLE
    assert item.display_mode is DisplayMode.NUMBER
