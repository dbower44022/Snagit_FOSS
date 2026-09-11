"""EmojiItem (Numbered Steps, Stamps & Emoji PRD 4.4, 4.7, 4.8, 5.3, 7.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QFontDatabase, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.config.constants import MARKER_MIN_HIT_SIZE
from snapmock.core.emoji_data import SKIN_TONE_MODIFIERS, SkinTone
from snapmock.core.scene import SnapScene
from snapmock.io.project_serializer import ITEM_REGISTRY, load_project, save_project
from snapmock.items.emoji_item import EmojiItem, resolved_emoji_family
from snapmock.items.shadow import SHADOW_KEYS

THUMBS_UP = "\U0001f44d"
COUPLE = "\U0001f9d1‍\U0001f91d‍\U0001f9d1"
FAMILY = "\U0001f468‍\U0001f469‍\U0001f466"


def _require_colour_emoji_font() -> None:
    """Skip when no colour emoji family is installed (the kickoff's font guard); a font
    database needs the application, so this runs inside the test, not at collection."""
    if not any("emoji" in f.casefold() for f in QFontDatabase.families()):
        pytest.skip("no colour emoji font installed")


def _render(item: EmojiItem, size: int = 200) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.translate(size / 2, size / 2)
    item.paint(painter, None)
    painter.end()
    return image


def _colours(image: QImage, rect: QRectF) -> set[str]:
    return {
        image.pixelColor(x, y).name()
        for x in range(int(rect.left()), int(rect.right()))
        for y in range(int(rect.top()), int(rect.bottom()))
    }


# --- the item (Sections 4.4 and 5.3) ---


def test_defaults_name_and_registry(qapp: QApplication) -> None:
    item = EmojiItem(THUMBS_UP)
    assert item.emoji_char == THUMBS_UP
    assert item.emoji_name == "Thumbs up"
    assert item.emoji_size == 48.0
    assert item.skin_tone is SkinTone.DEFAULT
    assert item.supports_skin_tones is True
    assert item.shadow_enabled is False
    assert item.opacity() == 1.0
    assert item.type_name == "Emoji"
    assert ITEM_REGISTRY["EmojiItem"] is EmojiItem
    assert item.emoji_rect() == QRectF(-24, -24, 48, 48)
    named = EmojiItem(THUMBS_UP, emoji_name="Yes!")
    assert named.emoji_name == "Yes!"


def test_size_is_clamped_and_shape_keeps_the_minimum(qapp: QApplication) -> None:
    item = EmojiItem(THUMBS_UP, emoji_size=4.0)
    assert item.emoji_size == 16.0
    assert item.shape().boundingRect().width() >= MARKER_MIN_HIT_SIZE
    item.emoji_size = 9999.0
    assert item.emoji_size == 256.0
    assert item.shape().boundingRect() == QRectF(-128, -128, 256, 256)
    item.scale_geometry(0.5, 0.5)
    assert item.emoji_size == 128.0


def test_skin_tone_property_retones_the_sequence(qapp: QApplication) -> None:
    item = EmojiItem(THUMBS_UP)
    item.skin_tone = SkinTone.MEDIUM_DARK
    assert item.emoji_char == THUMBS_UP + SKIN_TONE_MODIFIERS[SkinTone.MEDIUM_DARK]
    assert item.base_char == THUMBS_UP
    item.skin_tone = SkinTone.DEFAULT
    assert item.emoji_char == THUMBS_UP
    couple = EmojiItem(COUPLE)
    couple.skin_tone = SkinTone.LIGHT
    assert couple.emoji_char.count(SKIN_TONE_MODIFIERS[SkinTone.LIGHT]) == 2
    family = EmojiItem(FAMILY)
    assert family.supports_skin_tones is False
    family.skin_tone = SkinTone.DARK
    assert family.emoji_char == FAMILY  # untoned: it takes none
    toned = EmojiItem(THUMBS_UP + SKIN_TONE_MODIFIERS[SkinTone.LIGHT])
    assert toned.skin_tone is SkinTone.LIGHT  # read from the sequence
    assert toned.emoji_name == "Thumbs up"


def test_set_emoji_changes_char_name_and_tone(qapp: QApplication) -> None:
    item = EmojiItem(THUMBS_UP)
    item.set_emoji("\U0001f600")
    assert item.emoji_name == "Grinning face"
    assert item.supports_skin_tones is False
    item.set_emoji(THUMBS_UP + SKIN_TONE_MODIFIERS[SkinTone.DARK], "Custom name")
    assert item.emoji_name == "Custom name"
    assert item.skin_tone is SkinTone.DARK


# --- rendering (Section 4.7) ---


def test_renders_in_colour_through_the_emoji_font(qapp: QApplication) -> None:
    _require_colour_emoji_font()
    assert resolved_emoji_family() is not None
    item = EmojiItem(THUMBS_UP, emoji_size=64.0)
    image = _render(item)
    colours = _colours(image, QRectF(100 - 32, 100 - 32, 64, 64))
    assert len(colours) > 20  # a colour glyph, not a monochrome outline
    outside = _colours(image, QRectF(0, 0, 200, 100 - 40))
    assert outside == {"#ffffff"}  # the glyph stays inside its square


def test_flip_and_shadow_render(qapp: QApplication) -> None:
    _require_colour_emoji_font()
    item = EmojiItem("\U0001f449", emoji_size=64.0)  # backhand index pointing right
    plain = _render(item)
    item.flip_horizontal = True
    flipped = _render(item)
    assert plain != flipped
    item.shadow_enabled = True
    item.shadow_offset_x = 12.0
    item.shadow_offset_y = 12.0
    shadowed = _render(item)
    assert shadowed.pixelColor(100 + 38, 100 + 30).name() != "#ffffff"  # beyond the square
    assert item.boundingRect().width() > 64.0


# --- serialization (Sections 5.3 and 7.3) ---


def test_round_trip_keeps_zwj_sequences_and_tones(qapp: QApplication) -> None:
    item = EmojiItem(COUPLE, emoji_size=72.0)
    item.setPos(5, 6)
    item.skin_tone = SkinTone.MEDIUM
    item.flip_vertical = True
    item.shadow_enabled = True
    data = item.serialize()
    assert data["type"] == "EmojiItem"
    assert data["emoji_char"] == item.emoji_char
    assert data["skin_tone"] == "medium"
    assert data["emoji_name"].startswith("People holding hands")
    assert set(SHADOW_KEYS) <= set(data)
    restored = EmojiItem.deserialize(data)
    assert restored.emoji_char == item.emoji_char
    assert restored.skin_tone is SkinTone.MEDIUM
    assert restored.emoji_size == 72.0
    assert restored.pos() == QPointF(5, 6)
    assert restored.flip_vertical is True
    assert restored.shadow_enabled is True
    assert restored.serialize() == data


def test_deserialize_rebuilds_the_tone_from_the_property_when_the_sequence_lacks_it(
    qapp: QApplication,
) -> None:
    data = {"type": "EmojiItem", "emoji_char": THUMBS_UP, "skin_tone": "dark"}
    item = EmojiItem.deserialize(data)
    assert item.skin_tone is SkinTone.DARK
    assert item.emoji_char == THUMBS_UP + SKIN_TONE_MODIFIERS[SkinTone.DARK]
    bad = EmojiItem.deserialize({"type": "EmojiItem", "emoji_char": THUMBS_UP, "skin_tone": "x"})
    assert bad.skin_tone is SkinTone.DEFAULT


def test_project_round_trip_and_clone(
    qapp: QApplication, scene: SnapScene, tmp_path: Path
) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item = EmojiItem(FAMILY, emoji_size=40.0)
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    path = tmp_path / "emoji.smk"
    save_project(scene, path)
    loaded = load_project(path)
    (restored,) = loaded.annotation_items()
    assert isinstance(restored, EmojiItem)
    assert restored.emoji_char == FAMILY
    assert restored.emoji_size == 40.0
    copy = item.clone()
    assert isinstance(copy, EmojiItem)
    assert copy.item_id != item.item_id and copy.emoji_char == FAMILY
