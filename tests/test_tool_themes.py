"""Tool presets and themes: the codec, the stores, the Default theme, the live state
(General UI PRD 5.2, 11.8, 11.9, 15.4; Phase 7 decisions 7.1 B and 7.2 A)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from snapmock.config.constants import BubbleShape, TailStyle, VerticalAlign
from snapmock.config.settings import AppSettings
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.core.tool_themes import (
    CUSTOM_LABEL,
    DEFAULT_THEME_NAME,
    PresetStore,
    ThemeFileError,
    ThemeStore,
    ToolPreset,
    ToolTheme,
    ToolThemeManager,
    decode_value,
    decode_values,
    encode_value,
    encode_values,
    read_theme_file,
    unique_name,
    values_equal,
    write_theme_file,
)
from snapmock.tools.arrow_tool import ArrowTool
from snapmock.tools.callout_tool import CalloutTool
from snapmock.tools.numbered_step_tool import NumberedStepTool
from snapmock.tools.rectangle_tool import RectangleTool
from snapmock.tools.select_tool import SelectTool
from snapmock.tools.tool_manager import ToolManager


@pytest.fixture()
def tool_manager(scene: SnapScene) -> ToolManager:
    tm = ToolManager(scene, SelectionManager(scene))
    for tool in (SelectTool(), RectangleTool(), ArrowTool(), CalloutTool(), NumberedStepTool()):
        tm.register(tool)
    return tm


@pytest.fixture()
def manager(tool_manager: ToolManager, tmp_path: Path) -> ToolThemeManager:
    return ToolThemeManager(tool_manager, AppSettings(), tmp_path / "data")


# ---- the codec ----


def test_codec_round_trips_every_value_type() -> None:
    values = {
        "stroke_color": QColor(255, 0, 0, 128),
        "stroke_width": 2.5,
        "font_size": 14,
        "bold": True,
        "font_family": "Serif",
        "horizontal_align": Qt.AlignmentFlag.AlignRight,
        "vertical_align": VerticalAlign.CENTER,
        "bubble_shape": BubbleShape.CLOUD,
        "tail_style": TailStyle.ELBOW,
    }
    encoded = encode_values(values)
    text = json.dumps(encoded)
    decoded = decode_values(json.loads(text))
    assert decoded == values
    assert isinstance(decoded["bold"], bool)
    assert isinstance(decoded["font_size"], int)
    assert isinstance(decoded["stroke_width"], float)
    assert encoded["stroke_color"] == {"$color": "#80FF0000"}


def test_codec_rejects_unknown_types_and_forms() -> None:
    with pytest.raises(TypeError):
        encode_value(object())
    with pytest.raises(ValueError):
        decode_value({"$enum": "Nope", "value": 1})
    with pytest.raises(ValueError):
        decode_value({"$color": "not a colour"})
    assert encode_values({"ok": 1, "bad": object()}) == {"ok": 1}
    assert decode_values({"ok": 1, "bad": {"$what": 1}}) == {"ok": 1}
    assert decode_values("nope") == {}


def test_values_equal_compares_by_value() -> None:
    assert values_equal({"c": QColor("#FF0000"), "w": 2}, {"c": QColor(255, 0, 0), "w": 2.0})
    assert not values_equal({"c": QColor("#FF0000")}, {"c": QColor("#FF0001")})


def test_unique_name_numbers_collisions() -> None:
    assert unique_name("Red", set()) == "Red"
    assert unique_name("Red", {"Red"}) == "Red 2"
    assert unique_name("Red", {"Red", "Red 2"}) == "Red 3"


# ---- the stores ----


def test_preset_store_saves_lists_renames_and_deletes(tmp_path: Path) -> None:
    store = PresetStore(tmp_path)
    store.save(ToolPreset("arrow", "Zed", {"stroke_width": 3.0}))
    store.save(ToolPreset("arrow", "alpha", {"stroke_width": 1.0}))
    store.save(ToolPreset("rectangle", "Other", {"stroke_width": 9.0}))
    assert store.names("arrow") == ["alpha", "Zed"]
    assert store.names("rectangle") == ["Other"]
    assert (tmp_path / "presets" / "arrow" / "zed.json").is_file()
    preset = store.preset("arrow", "Zed")
    assert preset is not None and preset.values == {"stroke_width": 3.0}
    store.save(ToolPreset("arrow", "Zed", {"stroke_width": 4.0}))
    assert store.preset("arrow", "Zed").values == {"stroke_width": 4.0}  # type: ignore[union-attr]
    assert len(list((tmp_path / "presets" / "arrow").glob("*.json"))) == 2
    store.rename("arrow", "Zed", "Zee")
    assert store.names("arrow") == ["alpha", "Zee"]
    store.delete("arrow", "alpha")
    assert store.names("arrow") == ["Zee"]
    store.delete("arrow", "missing")


def test_preset_store_slug_collisions_get_numbered_files(tmp_path: Path) -> None:
    store = PresetStore(tmp_path)
    store.save(ToolPreset("arrow", "Red!", {}))
    store.save(ToolPreset("arrow", "Red?", {}))
    files = sorted(p.name for p in (tmp_path / "presets" / "arrow").glob("*.json"))
    assert files == ["red-2.json", "red.json"]
    assert store.names("arrow") == ["Red!", "Red?"]


def test_preset_store_skips_foreign_and_broken_files(tmp_path: Path) -> None:
    store = PresetStore(tmp_path)
    directory = tmp_path / "presets" / "arrow"
    directory.mkdir(parents=True)
    (directory / "broken.json").write_text("{not json")
    (directory / "other.json").write_text(json.dumps({"tool_id": "line", "name": "X"}))
    (directory / "unnamed.json").write_text(json.dumps({"tool_id": "arrow", "name": ""}))
    assert store.names("arrow") == []


def test_theme_file_round_trip_and_errors(tmp_path: Path) -> None:
    theme = ToolTheme("Blue Review", {"arrow": {"stroke_color": QColor("#0000FF")}})
    path = tmp_path / "blue.smktheme"
    write_theme_file(theme, path)
    data = json.loads(path.read_text())
    assert data["format"] == "smktheme" and data["format_version"] == 1
    assert data["app_version"]
    loaded = read_theme_file(path)
    assert loaded.name == "Blue Review"
    assert loaded.tools["arrow"]["stroke_color"] == QColor("#0000FF")
    assert not loaded.builtin

    (tmp_path / "bad.smktheme").write_text("{")
    with pytest.raises(ThemeFileError):
        read_theme_file(tmp_path / "bad.smktheme")
    (tmp_path / "kind.smktheme").write_text(json.dumps({"format": "other", "name": "x"}))
    with pytest.raises(ThemeFileError):
        read_theme_file(tmp_path / "kind.smktheme")
    data["format_version"] = 99
    (tmp_path / "new.smktheme").write_text(json.dumps(data))
    with pytest.raises(ThemeFileError, match="newer"):
        read_theme_file(tmp_path / "new.smktheme")
    with pytest.raises(ThemeFileError):
        read_theme_file(tmp_path / "missing.smktheme")


def test_theme_store_ignores_a_file_named_default(tmp_path: Path) -> None:
    store = ThemeStore(tmp_path)
    store.save(ToolTheme("Zulu", {}))
    store.save(ToolTheme("alpha", {}))
    write_theme_file(ToolTheme(DEFAULT_THEME_NAME, {}), tmp_path / "themes" / "default.json")
    assert store.names() == ["alpha", "Zulu"]
    store.rename("Zulu", "Yankee")
    assert store.names() == ["alpha", "Yankee"]
    store.delete("alpha")
    assert store.names() == ["Yankee"]


# ---- the Default theme (decision 7.2 A) ----


def test_default_theme_is_factory_defaults_under_preferences(manager: ToolThemeManager) -> None:
    default = manager.default_theme()
    assert default.builtin and default.name == DEFAULT_THEME_NAME
    assert set(default.tools) == {"rectangle", "arrow", "callout", "numbered_step"}
    assert default.tools["arrow"]["stroke_color"] == QColor("#FF0000")
    assert default.tools["callout"]["bubble_shape"] is BubbleShape.ROUNDED_RECT
    settings = AppSettings()
    settings.set_default_stroke_color(QColor("#123456"))
    settings.set_numbered_step_start(5)
    manager.preferences_changed()
    default = manager.default_theme()
    assert default.tools["arrow"]["stroke_color"] == QColor("#123456")
    assert default.tools["numbered_step"]["start_number"] == 5


def test_preferences_reach_unoverridden_tools_only(
    manager: ToolThemeManager, tool_manager: ToolManager
) -> None:
    manager.load_session()
    arrow = tool_manager.tool("arrow")
    rect = tool_manager.tool("rectangle")
    assert arrow is not None and rect is not None
    rect.creation_defaults["stroke_color"] = QColor("#00FF00")  # a Custom edit
    AppSettings().set_default_stroke_color(QColor("#0000FF"))
    manager.preferences_changed()
    assert arrow.creation_defaults["stroke_color"] == QColor("#0000FF")
    assert rect.creation_defaults["stroke_color"] == QColor("#00FF00")
    assert manager.current_label("arrow") == DEFAULT_THEME_NAME
    assert manager.current_label("rectangle") == CUSTOM_LABEL


def test_preferences_do_not_reach_tools_under_another_theme(
    manager: ToolThemeManager, tool_manager: ToolManager
) -> None:
    manager.load_session()
    manager.capture_theme("Blue")
    manager.apply_theme("Blue")
    AppSettings().set_default_stroke_color(QColor("#0000FF"))
    manager.preferences_changed()
    arrow = tool_manager.tool("arrow")
    assert arrow is not None
    assert arrow.creation_defaults["stroke_color"] == QColor("#FF0000")
    assert manager.current_label("arrow") == "Blue"


# ---- presets and the labels ----


def test_presets_apply_label_custom_update_and_reset(
    manager: ToolThemeManager, tool_manager: ToolManager
) -> None:
    manager.load_session()
    arrow = tool_manager.tool("arrow")
    assert arrow is not None
    assert manager.tool_ids == ["rectangle", "arrow", "callout", "numbered_step"]
    assert manager.current_label("arrow") == DEFAULT_THEME_NAME
    assert not manager.is_overridden("arrow") and not manager.is_modified()

    arrow.creation_defaults["stroke_width"] = 6.0
    assert manager.current_label("arrow") == CUSTOM_LABEL
    assert manager.is_overridden("arrow") and manager.is_modified()

    manager.save_preset("arrow", "Thick")
    assert manager.applied_preset("arrow") == "Thick"
    assert manager.current_label("arrow") == "Thick"
    assert not manager.preset_is_modified("arrow")

    arrow.creation_defaults["stroke_width"] = 7.0
    assert manager.current_label("arrow") == CUSTOM_LABEL
    assert manager.preset_is_modified("arrow")
    assert manager.update_preset("arrow")
    assert manager.current_label("arrow") == "Thick"
    assert manager.presets("arrow")[0].values["stroke_width"] == 7.0

    arrow.creation_defaults["stroke_width"] = 1.0
    changed: list[str] = []
    tool_manager.tool_defaults_changed.connect(changed.append)
    assert manager.apply_preset("arrow", "Thick")
    assert arrow.creation_defaults["stroke_width"] == 7.0
    assert changed == ["arrow"]

    manager.reset_to_theme("arrow")
    assert arrow.creation_defaults["stroke_width"] == 2.0
    assert manager.applied_preset("arrow") is None
    assert manager.current_label("arrow") == DEFAULT_THEME_NAME
    assert not manager.apply_preset("arrow", "missing")
    assert not manager.update_preset("arrow")


def test_preset_rename_duplicate_delete_follow_the_applied_name(
    manager: ToolThemeManager,
) -> None:
    manager.load_session()
    manager.save_preset("arrow", "Thick")
    manager.rename_preset("arrow", "Thick", "Wide")
    assert manager.applied_preset("arrow") == "Wide"
    assert manager.preset_names("arrow") == ["Wide"]
    duplicate = manager.duplicate_preset("arrow", "Wide")
    assert duplicate is not None and duplicate.name == "Wide Copy"
    assert manager.duplicate_preset("arrow", "Wide").name == "Wide Copy 2"  # type: ignore[union-attr]
    assert manager.preset_names("arrow") == ["Wide", "Wide Copy", "Wide Copy 2"]
    assert manager.duplicate_preset("arrow", "missing") is None
    manager.delete_preset("arrow", "Wide")
    assert manager.applied_preset("arrow") is None
    assert manager.current_label("arrow") == DEFAULT_THEME_NAME
    assert manager.preset_names("arrow") == ["Wide Copy", "Wide Copy 2"]


# ---- themes ----


def test_apply_theme_resets_every_tool_and_clears_overrides(
    manager: ToolThemeManager, tool_manager: ToolManager
) -> None:
    manager.load_session()
    arrow = tool_manager.tool("arrow")
    rect = tool_manager.tool("rectangle")
    assert arrow is not None and rect is not None
    arrow.creation_defaults["stroke_color"] = QColor("#0000FF")
    theme = manager.capture_theme("Blue")
    assert theme.tools["arrow"]["stroke_color"] == QColor("#0000FF")
    assert manager.theme_names() == ["Blue", DEFAULT_THEME_NAME]

    manager.save_preset("rectangle", "Green")
    rect.creation_defaults["stroke_width"] = 9.0
    names: list[str] = []
    manager.active_theme_changed.connect(names.append)
    assert manager.apply_theme("Blue")
    assert names == ["Blue"]
    assert manager.active_theme_name == "Blue"
    assert AppSettings().active_tool_theme() == "Blue"
    assert manager.applied_preset("rectangle") is None
    assert rect.creation_defaults["stroke_width"] == 2.0
    assert arrow.creation_defaults["stroke_color"] == QColor("#0000FF")
    assert not manager.is_modified()
    assert manager.current_label("arrow") == "Blue"
    assert not manager.apply_theme("missing")


def test_theme_values_fall_back_to_default_for_missing_tools_and_keys(
    manager: ToolThemeManager,
) -> None:
    manager.load_session()
    partial = ToolTheme("Partial", {"arrow": {"stroke_width": 8.0, "unknown_key": 1}})
    manager.theme_store.save(partial)
    values = manager.theme_values("arrow", partial)
    assert values["stroke_width"] == 8.0
    assert values["stroke_color"] == QColor("#FF0000")
    assert "unknown_key" not in values
    assert manager.theme_values("rectangle", partial) == manager.default_theme().tools["rectangle"]


def test_theme_duplicate_rename_delete_import_export(
    manager: ToolThemeManager, tmp_path: Path
) -> None:
    manager.load_session()
    copy = manager.duplicate_theme(DEFAULT_THEME_NAME)
    assert copy is not None and copy.name == "Default Copy" and not copy.builtin
    manager.rename_theme(DEFAULT_THEME_NAME, "Nope")
    manager.delete_theme(DEFAULT_THEME_NAME)
    assert DEFAULT_THEME_NAME in manager.theme_names()

    manager.apply_theme("Default Copy")
    manager.rename_theme("Default Copy", "Mine")
    assert manager.active_theme_name == "Mine"
    assert manager.theme_names() == [DEFAULT_THEME_NAME, "Mine"]

    out = tmp_path / "mine.smktheme"
    assert manager.export_theme("Mine", out)
    assert not manager.export_theme("missing", out)
    imported = manager.import_theme(out)
    assert imported.name == "Mine 2"
    with pytest.raises(ThemeFileError):
        manager.import_theme(tmp_path / "missing.smktheme")

    manager.delete_theme("Mine")
    assert manager.active_theme_name == DEFAULT_THEME_NAME
    assert manager.theme_names() == [DEFAULT_THEME_NAME, "Mine 2"]
    AppSettings().set_active_tool_theme("gone")
    assert manager.active_theme_name == DEFAULT_THEME_NAME


# ---- session state (PRD 15.4) ----


def test_session_state_round_trips_values_and_presets(
    tool_manager: ToolManager, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    manager = ToolThemeManager(tool_manager, AppSettings(), root)
    manager.load_session()
    arrow = tool_manager.tool("arrow")
    callout = tool_manager.tool("callout")
    assert arrow is not None and callout is not None
    manager.save_preset("arrow", "Thick")
    callout.creation_defaults["tail_style"] = TailStyle.CURVED
    callout.creation_defaults["text_color"] = QColor("#112233")
    tool_manager.tool_defaults_changed.emit("callout")
    manager.save_session()
    assert (root / "tool_state.json").is_file()

    # A second process: fresh tools, the same directory.
    scene = SnapScene()
    tm2 = ToolManager(scene, SelectionManager(scene))
    for tool in (RectangleTool(), ArrowTool(), CalloutTool(), NumberedStepTool()):
        tm2.register(tool)
    manager2 = ToolThemeManager(tm2, AppSettings(), root)
    manager2.load_session()
    callout2 = tm2.tool("callout")
    assert callout2 is not None
    assert callout2.creation_defaults["tail_style"] is TailStyle.CURVED
    assert callout2.creation_defaults["text_color"] == QColor("#112233")
    assert manager2.applied_preset("arrow") == "Thick"
    assert manager2.current_label("arrow") == "Thick"
    assert manager2.current_label("callout") == CUSTOM_LABEL


def test_load_session_without_state_applies_the_theme(
    manager: ToolThemeManager, tool_manager: ToolManager
) -> None:
    AppSettings().set_default_stroke_width(4.5)
    manager.preferences_changed()
    manager.load_session()
    rect = tool_manager.tool("rectangle")
    assert rect is not None
    assert rect.creation_defaults["stroke_width"] == 4.5
    assert not manager.state_path.exists()
