"""The bundled emoji data and the font rule (Numbered Steps, Stamps & Emoji PRD 4.2, 4.7;
decisions 2 and 4)."""

from __future__ import annotations

import json
from pathlib import Path

from snapmock.core.emoji_data import (
    EMOJI_DATA_FILE,
    SKIN_TONE_MODIFIERS,
    EmojiData,
    SkinTone,
    apply_skin_tone,
    emoji_data,
    emoji_font_family,
    set_emoji_data,
    skin_tone_of,
    strip_skin_tone,
)

GROUPS = [
    "Smileys & Emotion",
    "People & Body",
    "Animals & Nature",
    "Food & Drink",
    "Travel & Places",
    "Activities",
    "Objects",
    "Symbols",
    "Flags",
]
THUMBS_UP = "\U0001f44d"
WAVE = "\U0001f44b"
FAMILY = "\U0001f468‍\U0001f469‍\U0001f466"  # man, woman, boy
COUPLE = "\U0001f9d1‍\U0001f91d‍\U0001f9d1"  # people holding hands
RED_HEART = "❤️"


# --- the data file (decision 2) ---


def test_data_file_sits_beside_its_readme_and_licence() -> None:
    folder = EMOJI_DATA_FILE.parent
    assert EMOJI_DATA_FILE.is_file()
    assert (folder / "README.md").is_file()
    assert (folder / "LICENSE").is_file()
    raw = json.loads(EMOJI_DATA_FILE.read_text(encoding="utf-8"))
    assert raw["format_version"] == 1
    assert raw["emoji_version"] == "16.0"
    assert raw["groups"] == GROUPS
    assert f"Unicode emoji {raw['emoji_version']}" in (folder / "README.md").read_text()
    assert EMOJI_DATA_FILE.stat().st_size < 1_000_000


def test_parse_gives_the_nine_groups_and_every_entry_a_name() -> None:
    data = EmojiData()
    assert data.groups() == GROUPS
    everything = data.all()
    assert 1500 < len(everything) < 2500
    assert all(e.name and e.group in GROUPS for e in everything)
    for group in GROUPS:
        assert data.in_group(group), group
    chars = [e.char for e in everything]
    assert len(chars) == len(set(chars))
    # No entry is a toned variant; the capability flag stands for them
    assert not any(any(m in e.char for m in SKIN_TONE_MODIFIERS.values()) for e in everything)


def test_lookup_names_and_capabilities() -> None:
    data = EmojiData()
    thumbs = data.lookup(THUMBS_UP)
    assert thumbs is not None
    assert thumbs.name == "Thumbs up"
    assert thumbs.group == "People & Body"
    assert thumbs.skin_tones is True
    assert "like" in thumbs.keywords
    family = data.lookup(FAMILY)
    assert family is not None and family.name.startswith("Family")
    assert family.skin_tones is False
    heart = data.lookup(RED_HEART)
    assert heart is not None and heart.name == "Red heart"
    assert data.lookup("❤") is heart  # without the presentation selector
    assert data.lookup(THUMBS_UP + SKIN_TONE_MODIFIERS[SkinTone.DARK]) is thumbs  # toned
    assert data.name_of(THUMBS_UP) == "Thumbs up"
    assert data.name_of("not an emoji") == ""
    assert data.lookup("x") is None


def test_search_matches_names_and_keywords() -> None:
    data = EmojiData()
    found = {e.name for e in data.search("happy")}
    assert any("smiling" in n.lower() or "grinning" in n.lower() for n in found)
    assert {e.char for e in data.search("thumbs up")} >= {THUMBS_UP}
    assert data.search("") == data.all()
    assert data.search("zzqx-nothing") == []
    assert {e.char for e in data.search("Like")} >= {THUMBS_UP}  # a keyword, any case


def test_a_missing_or_broken_file_gives_empty_data(tmp_path: Path) -> None:
    broken = tmp_path / "emoji.json"
    broken.write_text("{ not json")
    data = EmojiData(broken)
    assert data.groups() == [] and data.all() == [] and data.search("x") == []
    assert EmojiData(tmp_path / "absent.json").lookup(THUMBS_UP) is None


def test_default_data_is_shared_and_replaceable(tmp_path: Path) -> None:
    original = emoji_data()
    assert emoji_data() is original
    replacement = EmojiData(tmp_path / "none.json")
    set_emoji_data(replacement)
    try:
        assert emoji_data() is replacement
    finally:
        set_emoji_data(None)


# --- the modifier arithmetic (Section 4.7) ---


def test_apply_and_strip_a_skin_tone_round_trip() -> None:
    toned = apply_skin_tone(THUMBS_UP, SkinTone.MEDIUM)
    assert toned == THUMBS_UP + SKIN_TONE_MODIFIERS[SkinTone.MEDIUM]
    assert skin_tone_of(toned) is SkinTone.MEDIUM
    assert strip_skin_tone(toned) == THUMBS_UP
    assert apply_skin_tone(toned, SkinTone.DARK) == THUMBS_UP + SKIN_TONE_MODIFIERS[SkinTone.DARK]
    assert apply_skin_tone(toned, SkinTone.DEFAULT) == THUMBS_UP
    assert skin_tone_of(THUMBS_UP) is SkinTone.DEFAULT


def test_apply_a_tone_to_a_zwj_sequence_tones_the_data_s_slots() -> None:
    data = EmojiData()
    couple = data.lookup(COUPLE)
    assert couple is not None and couple.skin_tones
    assert couple.tone_slots == (0, 2)  # both people, never the handshake between them
    toned = data.toned(COUPLE, SkinTone.LIGHT)
    light = SKIN_TONE_MODIFIERS[SkinTone.LIGHT]
    assert toned == f"\U0001f9d1{light}\u200d\U0001f91d\u200d\U0001f9d1{light}"
    assert strip_skin_tone(toned) == COUPLE
    technologist = "\U0001f468\u200d\U0001f4bb"  # man technologist: the man alone is toned
    info = data.lookup(technologist)
    assert info is not None and info.tone_slots == (0,)
    assert data.toned(technologist, SkinTone.DARK) == (
        "\U0001f468" + SKIN_TONE_MODIFIERS[SkinTone.DARK] + "\u200d\U0001f4bb"
    )
    assert data.toned(FAMILY, SkinTone.DARK) == FAMILY  # no tone for a family
    assert apply_skin_tone(COUPLE, SkinTone.LIGHT, (0, 2)) == toned


def test_apply_a_tone_replaces_the_presentation_selector() -> None:
    victory = "✌️"  # victory hand with the emoji presentation selector
    toned = apply_skin_tone(victory, SkinTone.DARK)
    assert toned == "✌" + SKIN_TONE_MODIFIERS[SkinTone.DARK]
    assert "️" not in toned


# --- the font rule (decision 4) ---


def test_font_family_prefers_the_platform_fonts_then_any_emoji_family() -> None:
    assert emoji_font_family(["Arial", "Noto Color Emoji", "Twemoji"]) == "Noto Color Emoji"
    assert emoji_font_family(["Segoe UI Emoji", "Noto Color Emoji"]) == "Noto Color Emoji"
    assert emoji_font_family(["Arial", "Segoe UI Emoji"]) == "Segoe UI Emoji"
    assert emoji_font_family(["Arial", "Apple Color Emoji"]) == "Apple Color Emoji"
    assert emoji_font_family(["Arial", "Some Emoji Font"]) == "Some Emoji Font"
    assert emoji_font_family(["Arial", "DejaVu Sans"]) is None
    assert emoji_font_family([]) is None


def test_font_family_reads_the_real_font_database_without_raising(qapp: object) -> None:
    family = emoji_font_family()
    assert family is None or isinstance(family, str)
