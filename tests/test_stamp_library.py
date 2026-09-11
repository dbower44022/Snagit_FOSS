"""The stamp library (Numbered Steps, Stamps & Emoji PRD 3.2, 3.3, 3.8, 7.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from snapmock.core.stamp_library import (
    BUILTIN,
    BUILTIN_STAMPS_DIR,
    CUSTOM,
    CUSTOM_CATEGORY,
    INDEX_FILENAME,
    PLACEHOLDER_SVG,
    StampInfo,
    StampLibrary,
    has_secondary_region,
    set_stamp_library,
    stamp_library,
    substitute_colors,
)

CATEGORY_IDS = ("status", "arrows", "ui", "shapes", "decorative")

SIMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
    '<rect x="8" y="8" width="48" height="48" fill="#FF0000"/>'
    '<circle cx="32" cy="32" r="10" fill="#0000ff"/></svg>'
)


@pytest.fixture()
def library(tmp_path: Path) -> StampLibrary:
    return StampLibrary(custom_dir=tmp_path / "custom")


def _render(svg_renderer: object, size: int = 64) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    svg_renderer.render(painter, QRectF(0, 0, size, size))  # type: ignore[attr-defined]
    painter.end()
    return image


# --- the built-in index (Sections 3.2 and 3.3) ---


def test_builtin_index_has_the_five_categories_and_fifty_to_sixty_stamps(
    qapp: QApplication, library: StampLibrary
) -> None:
    categories = library.categories()
    assert [c for c, _ in categories] == [*CATEGORY_IDS, CUSTOM_CATEGORY]
    stamps = library.stamps()
    assert 50 <= len(stamps) <= 60
    for category in CATEGORY_IDS:
        assert library.in_category(category), category
    ids = [s.id for s in stamps]
    assert len(ids) == len(set(ids))
    for stamp in stamps:
        assert stamp.source == BUILTIN
        assert stamp.id == f"{stamp.category}/{stamp.filename.rsplit('/', 1)[-1][:-4]}"
        assert stamp.path is not None and stamp.path.is_file(), stamp.id
        assert stamp.default_size == 48.0
        assert stamp.tags


def test_the_named_stamps_of_section_3_3_are_present(library: StampLibrary) -> None:
    ids = {s.id for s in library.stamps()}
    for expected in (
        "status/approved",
        "status/rejected",
        "status/draft",
        "arrows/pointer-hand",
        "arrows/target",
        "ui/click",
        "ui/tap",
        "shapes/lock",
        "shapes/eye-off",
        "decorative/starburst",
        "decorative/brackets",
        "decorative/box-highlight",
    ):
        assert expected in ids


def test_every_builtin_stamp_parses_and_uses_the_primary_placeholder(
    qapp: QApplication, library: StampLibrary
) -> None:
    for stamp in library.stamps():
        svg = library.svg_data(stamp.id)
        assert svg is not None, stamp.id
        assert "#FF0000" in svg.upper(), stamp.id
        renderer = library.renderer(svg, QColor("#00aa00"), QColor("#0000aa"))
        assert renderer.isValid(), stamp.id


def test_readme_and_licence_sit_beside_the_index() -> None:
    assert (BUILTIN_STAMPS_DIR / INDEX_FILENAME).is_file()
    assert (BUILTIN_STAMPS_DIR / "README.md").is_file()
    assert (BUILTIN_STAMPS_DIR / "LICENSE").is_file()
    index = json.loads((BUILTIN_STAMPS_DIR / INDEX_FILENAME).read_text())
    sources = {e["source"] for e in index["stamps"]}
    assert "snapmock" in sources
    assert any(s.startswith("tabler:") for s in sources)


# --- search (Section 3.4) ---


def test_search_matches_name_and_tags_case_insensitively(library: StampLibrary) -> None:
    found = {s.id for s in library.search("Approve")}
    assert "status/approved" in found
    assert "status/thumbs-up" in found  # the "approve" tag
    assert {s.id for s in library.search("thumbs down")} == {"status/thumbs-down"}
    assert library.search("") == library.stamps()
    assert library.search("no-such-stamp-anywhere") == []


# --- colour substitution (Sections 3.2 and 3.9) ---


def test_substitute_colors_replaces_both_placeholders_in_any_case(qapp: QApplication) -> None:
    out = substitute_colors(SIMPLE_SVG, QColor("#123456"), QColor("#abcdef"))
    assert "#FF0000" not in out.upper()
    assert "#0000FF" not in out.upper()
    assert "#123456" in out and "#abcdef" in out
    assert has_secondary_region(SIMPLE_SVG)
    assert not has_secondary_region(SIMPLE_SVG.replace("#0000ff", "#00ff00"))


def test_renderer_recolours_a_colorizable_stamp_and_leaves_a_fixed_one(
    qapp: QApplication, library: StampLibrary
) -> None:
    coloured = _render(library.renderer(SIMPLE_SVG, QColor("#00aa00"), QColor("#0000aa")))
    assert coloured.pixelColor(12, 12).name() == "#00aa00"
    assert coloured.pixelColor(32, 32).name() == "#0000aa"
    fixed = _render(
        library.renderer(SIMPLE_SVG, QColor("#00aa00"), QColor("#0000aa"), colorizable=False)
    )
    assert fixed.pixelColor(12, 12).name() == "#ff0000"
    assert fixed.pixelColor(32, 32).name() == "#0000ff"


def test_renderer_is_cached_per_svg_and_colours(qapp: QApplication, library: StampLibrary) -> None:
    a = library.renderer(SIMPLE_SVG, QColor("red"), QColor("blue"))
    assert library.renderer(SIMPLE_SVG, QColor("red"), QColor("blue")) is a
    assert library.renderer(SIMPLE_SVG, QColor("green"), QColor("blue")) is not a


# --- a missing stamp (Section 7.2) ---


def test_unknown_id_gives_no_data_and_the_placeholder_renders(
    qapp: QApplication, library: StampLibrary
) -> None:
    assert library.stamp("status/no-such") is None
    assert library.svg_data("status/no-such") is None
    image = _render(library.placeholder_renderer())
    assert _frame_drawn(image)  # the dashed frame
    broken = library.renderer("<svg><not closed", QColor("red"), QColor("blue"))
    assert broken.isValid()  # the placeholder stands in
    assert _frame_drawn(_render(broken))


def _frame_drawn(image: QImage) -> bool:
    return any(image.pixelColor(x, 6).name() != "#ffffff" for x in range(6, 58))


def test_placeholder_svg_is_valid(qapp: QApplication) -> None:
    from PyQt6.QtSvg import QSvgRenderer

    assert QSvgRenderer(PLACEHOLDER_SVG.encode()).isValid()


# --- custom stamps (Section 3.8) ---


def test_import_copies_the_file_writes_the_index_and_merges(
    qapp: QApplication, library: StampLibrary, tmp_path: Path
) -> None:
    source = tmp_path / "My Badge.svg"
    source.write_text(SIMPLE_SVG)
    info = library.import_svg(source, name="My Badge", tags=("badge", "mine"), colorizable=False)
    assert info.id == "custom/my-badge"
    assert info.source == CUSTOM
    assert info.category == CUSTOM_CATEGORY
    assert (library.custom_directory / "my-badge.svg").read_text() == SIMPLE_SVG
    index = json.loads((library.custom_directory / INDEX_FILENAME).read_text())
    assert index["stamps"][0]["id"] == "custom/my-badge"
    assert index["stamps"][0]["colorizable"] is False
    assert library.stamp("custom/my-badge") == info
    assert library.in_category(CUSTOM_CATEGORY) == [info]
    assert "custom/my-badge" in {s.id for s in library.search("mine")}
    assert library.svg_data("custom/my-badge") == SIMPLE_SVG
    # A second library over the same directories sees the import
    again = StampLibrary(custom_dir=library.custom_directory)
    assert again.stamp("custom/my-badge") is not None
    # A second import of the same name gets a numbered id
    second = library.import_svg(source)
    assert second.id == "custom/my-badge-2"
    assert second.name == "My Badge"


def test_import_rejects_a_file_that_is_not_svg(library: StampLibrary, tmp_path: Path) -> None:
    bad = tmp_path / "photo.svg"
    bad.write_text("not an svg at all")
    with pytest.raises(ValueError):
        library.import_svg(bad)
    assert library.in_category(CUSTOM_CATEGORY) == []


def test_update_and_remove_custom(
    qapp: QApplication, library: StampLibrary, tmp_path: Path
) -> None:
    source = tmp_path / "one.svg"
    source.write_text(SIMPLE_SVG)
    info = library.import_svg(source)
    renamed = StampInfo(**{**info.__dict__, "name": "Renamed", "tags": ("x",)})
    library.update_custom(renamed)
    updated = library.stamp(info.id)
    assert updated is not None and updated.name == "Renamed" and updated.tags == ("x",)
    assert library.remove_custom(info.id)
    assert library.stamp(info.id) is None
    assert not (library.custom_directory / "one.svg").exists()
    assert library.remove_custom("status/approved") is False


def test_a_broken_custom_index_is_ignored(qapp: QApplication, tmp_path: Path) -> None:
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / INDEX_FILENAME).write_text("{ not json")
    library = StampLibrary(custom_dir=custom)
    assert library.in_category(CUSTOM_CATEGORY) == []
    assert len(library.stamps()) >= 50


def test_default_library_is_shared_and_replaceable(tmp_path: Path) -> None:
    original = stamp_library()
    assert stamp_library() is original
    replacement = StampLibrary(custom_dir=tmp_path)
    set_stamp_library(replacement)
    try:
        assert stamp_library() is replacement
    finally:
        set_stamp_library(None)
