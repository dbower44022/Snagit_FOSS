"""The Highlighter (Blur, Highlighter & Eyedropper PRD Section 3): the item's blend mode
and cap, the tool's bar per 3.5, and the round trip (Vector Item Properties Phase 2)."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt6.QtWidgets import QApplication, QComboBox, QSpinBox

from snapmock.config.constants import (
    DEFAULT_HIGHLIGHT_COLOR,
    HIGHLIGHT_PRESET_COLORS,
    BorderStyle,
    StrokeCap,
)
from snapmock.core.layer import ITEM_BLEND_MODES, normalize_item_blend_mode
from snapmock.items.highlight_item import HighlightItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.tools.highlight_tool import HighlightTool
from snapmock.ui.color_picker import ColorPicker
from snapmock.ui.tool_options_bar import ToolOptionsBar

Button = Qt.MouseButton
Modifier = Qt.KeyboardModifier
ORIGIN = QPointF(40, 40)


def _highlight(points: list[tuple[float, float]]) -> HighlightItem:
    item = HighlightItem()
    for x, y in points:
        item.add_point(x, y)
    return item


def _render(item: HighlightItem, background: QColor) -> QImage:
    image = QImage(200, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(background)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(ORIGIN)
    item.paint(painter, None)
    painter.end()
    return image


def _pixel(image: QImage, local: QPointF) -> QColor:
    return image.pixelColor(int(ORIGIN.x() + local.x()), int(ORIGIN.y() + local.y()))


def _bar(window: MainWindow) -> ToolOptionsBar:
    return window._tool_options  # noqa: SLF001


def _event(kind: QEvent.Type, window: MainWindow, scene_pos: QPointF) -> QMouseEvent:
    view_pos = QPointF(window.view.mapFromScene(scene_pos))
    return QMouseEvent(kind, view_pos, Button.LeftButton, Button.LeftButton, Modifier.NoModifier)


# --- the item (3.4, 3.7) ---


def test_the_item_defaults_are_the_prd_values(qapp: QApplication) -> None:
    item = HighlightItem()
    assert item.stroke_color.name(QColor.NameFormat.HexArgb) == DEFAULT_HIGHLIGHT_COLOR.lower()
    assert item.highlight_color == item.stroke_color
    assert item.stroke_width == 24.0
    assert item.stroke_cap is StrokeCap.FLAT
    assert item.blend_mode == "Multiply"
    assert RectangleItem().blend_mode == "Normal"


def test_each_blend_mode_renders_distinctly_over_a_coloured_background(
    qapp: QApplication,
) -> None:
    item = _highlight([(0, 0), (100, 0)])
    item.stroke_color = QColor(255, 255, 0, 204)
    probe = QPointF(50, 0)
    background = QColor("#4060c0")
    seen: dict[str, str] = {}
    for mode in ("Multiply", "Overlay", "Soft Light", "Normal"):
        item.blend_mode = mode
        seen[mode] = _pixel(_render(item, background), probe).name()
    assert len(set(seen.values())) == 4, seen
    # Multiply darkens: no channel brighter than the background's
    multiplied = QColor(seen["Multiply"])
    assert multiplied.blue() <= background.blue() and multiplied.red() <= background.red()
    # Normal is plain alpha blending: yellow over blue lifts red and green
    normal = QColor(seen["Normal"])
    assert normal.red() > background.red() and normal.green() > background.green()
    # Every mode leaves the painter's composition mode where it found it
    image = QImage(10, 10, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    item.blend_mode = "Multiply"
    item.paint(painter, None)
    assert painter.compositionMode() == QPainter.CompositionMode.CompositionMode_SourceOver
    painter.end()


def test_the_shadow_keeps_normal_composition_under_a_blend_mode(qapp: QApplication) -> None:
    item = _highlight([(0, 0), (100, 0)])
    item.stroke_color = QColor(255, 255, 0, 204)
    item.stroke_width = 10.0
    item.shadow_enabled = True
    item.shadow_color = QColor(255, 255, 255, 255)  # a white shadow: multiply would hide it
    item.shadow_offset_x = 0.0
    item.shadow_offset_y = 20.0
    item.shadow_blur = 0.0
    item.blend_mode = "Multiply"
    background = QColor("#202020")
    image = _render(item, background)
    assert _pixel(image, QPointF(50, 20)).name() == "#ffffff"


def test_the_layer_mode_wins_over_the_item_mode(qapp: QApplication) -> None:
    item = _highlight([(0, 0), (100, 0)])
    item.stroke_color = QColor(255, 255, 0, 255)
    item.blend_mode = "Normal"
    background = QColor("#4060c0")
    plain = _pixel(_render(item, background), QPointF(50, 0)).name()
    item.layer_blend_mode = "Multiply"
    layered = _pixel(_render(item, background), QPointF(50, 0)).name()
    assert plain == "#ffff00" and layered != plain


def test_the_cap_and_style_reach_the_band(qapp: QApplication) -> None:
    item = _highlight([(0, 0), (100, 0)])
    item.stroke_color = QColor(0, 0, 0, 255)
    item.blend_mode = "Normal"
    beyond = QPointF(104.0, 0.0)
    assert _pixel(_render(item, QColor("white")), beyond).name() == "#ffffff"
    item.stroke_cap = StrokeCap.ROUND
    assert _pixel(_render(item, QColor("white")), beyond).name() == "#000000"
    item.stroke_style = BorderStyle.DASHED
    item.stroke_width = 6.0  # dashes scale with the width: 24 px on, 12 px off
    xs = range(2, 98, 2)
    on = sum(_pixel(_render(item, QColor("white")), QPointF(x, 0)).name() == "#000000" for x in xs)
    assert 0 < on < len(xs)


def test_the_blend_mode_round_trips_and_reads_the_prd_spellings(qapp: QApplication) -> None:
    item = _highlight([(0, 0), (50, 0)])
    item.blend_mode = "Soft Light"
    data = item.serialize()
    assert data["blend_mode"] == "Soft Light"
    assert HighlightItem.deserialize(data).blend_mode == "Soft Light"
    data["blend_mode"] = "soft_light"
    assert HighlightItem.deserialize(data).blend_mode == "Soft Light"
    del data["blend_mode"]
    assert HighlightItem.deserialize(data).blend_mode == "Normal"
    assert normalize_item_blend_mode("wavy") == "Normal"
    assert "Soft Light" in ITEM_BLEND_MODES
    item.blend_mode = "nonsense"
    assert item.blend_mode == "Normal"


# --- the tool and its bar (3.5) ---


def test_the_bar_composes_the_prd_controls(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    main_window.tool_manager.activate("highlight")
    assert list(bar.shared_widgets) == [
        "highlight_color",
        "highlight_width",
        "blend_mode",
        "stroke_style",
        "shadow_enabled",
    ]
    colour = bar.shared_widgets["highlight_color"]
    assert isinstance(colour, ColorPicker)
    assert colour.color.name(QColor.NameFormat.HexArgb) == DEFAULT_HIGHLIGHT_COLOR.lower()
    width = bar.shared_widgets["highlight_width"]
    assert isinstance(width, QSpinBox)
    assert (width.minimum(), width.maximum(), width.value()) == (10, 80, 24)
    blend = bar.shared_widgets["blend_mode"]
    assert isinstance(blend, QComboBox)
    assert [blend.itemText(i) for i in range(blend.count())] == [
        "Multiply",
        "Overlay",
        "Soft Light",
        "Normal",
    ]
    assert blend.currentData() == "Multiply"
    tool = main_window.tool_manager.tool("highlight")
    assert isinstance(tool, HighlightTool)
    caps = tool.cap_buttons
    assert list(caps) == [StrokeCap.FLAT, StrokeCap.ROUND, StrokeCap.SQUARE]
    assert caps[StrokeCap.FLAT].isChecked()
    assert len(tool.preset_swatches) == 6
    assert "opacity_pct" not in tool.creation_defaults


def test_bar_edits_and_the_swatches_reach_the_next_stroke(main_window: MainWindow) -> None:
    bar = _bar(main_window)
    tm = main_window.tool_manager
    tm.activate("highlight")
    tool = tm.tool("highlight")
    assert isinstance(tool, HighlightTool)
    width = bar.shared_widgets["highlight_width"]
    assert isinstance(width, QSpinBox)
    width.setValue(40)
    blend = bar.shared_widgets["blend_mode"]
    assert isinstance(blend, QComboBox)
    blend.setCurrentIndex(blend.findData("Overlay"))
    tool.cap_buttons[StrokeCap.SQUARE].click()
    assert tool.creation_defaults["stroke_cap"] is StrokeCap.SQUARE
    tool.preset_swatches[3].click()  # Pink
    assert tool.creation_defaults["highlight_color"] == QColor(HIGHLIGHT_PRESET_COLORS[3][1])
    colour = bar.shared_widgets["highlight_color"]
    assert isinstance(colour, ColorPicker)
    assert colour.color == QColor(HIGHLIGHT_PRESET_COLORS[3][1])
    tm.handle_mouse_press(_event(QEvent.Type.MouseButtonPress, main_window, QPointF(10, 10)))
    for x in (30, 60, 90):
        tm.handle_mouse_move(_event(QEvent.Type.MouseMove, main_window, QPointF(x, 10)))
    tm.handle_mouse_release(_event(QEvent.Type.MouseButtonRelease, main_window, QPointF(90, 10)))
    items = [i for i in main_window.scene.annotation_items() if isinstance(i, HighlightItem)]
    assert len(items) == 1
    item = items[0]
    assert item.stroke_width == 40.0
    assert item.blend_mode == "Overlay"
    assert item.stroke_cap is StrokeCap.SQUARE
    assert item.stroke_color == QColor(HIGHLIGHT_PRESET_COLORS[3][1])
    assert item.opacity() == 1.0


def test_a_preset_captures_the_highlighter_values(main_window: MainWindow) -> None:
    themes = main_window._tool_themes  # noqa: SLF001
    tool = main_window.tool_manager.tool("highlight")
    assert isinstance(tool, HighlightTool)
    tool.creation_defaults.update({"blend_mode": "Normal", "stroke_cap": StrokeCap.ROUND})
    main_window.tool_manager.tool_defaults_changed.emit("highlight")
    themes.save_preset("highlight", "Flat marker")
    themes.reset_to_theme("highlight")
    assert tool.creation_defaults["blend_mode"] == "Multiply"
    assert tool.creation_defaults["stroke_cap"] is StrokeCap.FLAT
    assert themes.apply_preset("highlight", "Flat marker")
    assert tool.creation_defaults["blend_mode"] == "Normal"
    assert tool.creation_defaults["stroke_cap"] is StrokeCap.ROUND
    assert themes.current_label("highlight") == "Flat marker"
