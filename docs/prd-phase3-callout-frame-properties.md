# Phase 3: CalloutItem Frame Property Migration — Implementation PRD

## Overview

Phase 3 migrates `CalloutItem` to use the same configurable frame property system that was added to `TextItem` in Phase 2. Previously, `CalloutItem` used hardcoded values for its border, padding, and corner radius. After this phase, users can configure callout appearance (background color, border color/width, corner radius, padding, vertical text alignment) through the PropertyPanel — the same controls already available for text boxes.

This phase also includes three bug fixes in `SnapView` that were discovered during testing.

---

## Problem Statement

After Phase 2, `TextItem` had a full set of frame properties (`bg_color`, `border_color`, `border_width`, `border_radius`, `padding`, `vertical_align`) with PropertyPanel controls and Snagit I/O support. `CalloutItem` still used hardcoded values:

- Background color: `#FFFFCC` (stored, but no property getter/setter)
- Border color: `#000000` (stored, but no property getter/setter)
- Border width: implicit 1px (default `QPen` width)
- Border radius: hardcoded `4` in `drawRoundedRect()`
- Padding: hardcoded `4` in `self._rect.adjusted(4, 4, -4, -4)`
- Vertical alignment: none (text always drawn from top of padded rect)
- Snagit writer: hardcoded `StrokeWidth: 3`, `ToolPadding: 4`, `ToolVerticalAlign: "Center"`

This meant callout appearance could not be customized through the UI and Snagit round-trip fidelity was limited.

---

## Changes Made

### 1. CalloutItem Frame Properties (`snapmock/items/callout_item.py`)

**What:** Added four new instance fields and six property getter/setter pairs.

**New fields** (in `__init__`, after `_border_color`):
| Field | Type | Default | Rationale |
|-------|------|---------|-----------|
| `_border_width` | `float` | `2.0` | Matches Snagit's typical callout border. Previously implicit 1px. |
| `_border_radius` | `float` | `4.0` | Was hardcoded in `drawRoundedRect()`. Now configurable. |
| `_padding` | `float` | `4.0` | Was hardcoded in `_rect.adjusted()`. Now configurable. |
| `_vertical_align` | `VerticalAlign` | `CENTER` | Snagit default for callouts. TextItem defaults to TOP. |

**New property accessors** (following the TextItem pattern):
- `bg_color` — getter returns `QColor(self._bg_color)`, setter copies + calls `update()`
- `border_color` — same pattern
- `border_width` — setter clamps `>= 0`, calls `prepareGeometryChange()` + `update()`
- `border_radius` — setter clamps `>= 0`, calls `update()`
- `padding` — setter clamps `>= 0`, calls `prepareGeometryChange()` + `update()`
- `vertical_align` — setter calls `update()`

**Why properties instead of direct field access:** The property setters enforce clamping (no negative values), call `prepareGeometryChange()` when the bounding rect may change, and call `update()` to trigger a repaint. This is the same pattern used by `TextItem` and `VectorItem`, ensuring the `ModifyPropertyCommand` undo system works correctly.

#### Paint Refactoring

**Before:**
```python
painter.setPen(self._border_color)          # implicit 1px pen
painter.drawRoundedRect(self._rect, 4, 4)   # hardcoded radius
text_rect = self._rect.adjusted(4, 4, -4, -4)  # hardcoded padding
self.draw_document(painter, text_rect)      # no vertical alignment
```

**After:**
```python
pen = QPen(self._border_color, self._border_width)  # configurable width
painter.setPen(pen)

if self._border_radius > 0:                         # configurable radius
    painter.drawRoundedRect(self._rect, self._border_radius, self._border_radius)
else:
    painter.drawRect(self._rect)

# Compute text rect with padding and vertical alignment
p = self._padding
content_w = max(1.0, self._rect.width() - 2 * p)
content_h = max(1.0, self._rect.height() - 2 * p)
doc_h = self.document_height(content_w)

y_offset = self._rect.y() + p
if self._vertical_align == VerticalAlign.CENTER:
    y_offset += max(0.0, (content_h - doc_h) / 2)
elif self._vertical_align == VerticalAlign.BOTTOM:
    y_offset += max(0.0, content_h - doc_h)

text_rect = QRectF(self._rect.x() + p, y_offset, content_w, doc_h)
self.draw_document(painter, text_rect)
```

**Why:** The tail path also uses the configurable pen so the tail border matches the box border width. The vertical alignment logic mirrors TextItem's implementation exactly.

#### BoundingRect

**Before:** `r.adjusted(-2, -2, 2, 2)` — hardcoded 2px margin.

**After:** `margin = max(self._border_width / 2, 1.0)` — the margin adapts to the border width so thick borders aren't clipped. The `max(..., 1.0)` ensures at least 1px margin even with `border_width=0`.

#### Scale Geometry

**Added** after existing rect/tail scaling:
```python
avg = (sx + sy) / 2.0
self._border_width = max(0.0, self._border_width * avg)
self._border_radius = max(0.0, self._border_radius * avg)
self._padding = max(0.0, self._padding * avg)
```

**Why average of sx/sy:** Border width, radius, and padding are scalar values (not directional), so scaling by the average of the two axes produces a visually proportional result. This matches the TextItem approach.

#### Serialization

**Added keys to `serialize()`:** `border_width`, `border_radius`, `padding`, `vertical_align` (as string via `_vertical_align.value`).

**Added to `deserialize()`:** Reads new fields with backward-compatible defaults (`2.0`, `4.0`, `4.0`, `"center"`). Uses `try/except ValueError` for the `VerticalAlign` enum parse, falling back to `CENTER`.

**Why these defaults:** They match the hardcoded values that were previously in the code, ensuring existing serialized callouts look identical after upgrading.

---

### 2. PropertyPanel Widening (`snapmock/ui/property_panel.py`)

**What:** The "Text Box" section (background, border, corner radius, padding, vertical align, auto-size) now appears for both `TextItem` and `CalloutItem`.

**Visibility change:**
```python
# Before
self._text_box_section.setVisible(has_selection and is_text_item)

# After
self._text_box_section.setVisible(has_selection and has_text)
```

Where `has_text = isinstance(item, (TextItem, CalloutItem))`.

**Refresh logic:** The block that populates the text box controls now runs for both item types. Since both `TextItem` and `CalloutItem` expose the same property names (`bg_color`, `border_color`, `border_width`, `border_radius`, `padding`, `vertical_align`), the same code works for both:
```python
if has_text:
    assert isinstance(item, (TextItem, CalloutItem))
    self._text_bg_color_picker.color = item.bg_color
    self._text_border_color_picker.color = item.border_color
    # ... etc
```

Note: The `ColorPicker` widget itself handles transparent colors natively — each color picker includes a `∅` transparent toggle button and displays a checkerboard swatch when the color has alpha < 255. This replaces the previous `_no_fill_check` and `_no_bg_check` checkboxes that were separate from the color picker.

**Auto-size checkbox:** Hidden for `CalloutItem` because callout dimensions come from its `_rect` (set by the callout tool or drag handles), not from a width+auto-height model:
```python
self._text_auto_size_check.setVisible(is_text_item)
```

**Handler type checks:** All six text box change handlers (`_on_text_bg_color_changed`, `_on_text_border_color_changed`, `_on_text_border_w_changed`, `_on_text_corner_radius_changed`, `_on_text_padding_changed`, `_on_text_valign_changed`) changed from `isinstance(item, TextItem)` to `isinstance(item, (TextItem, CalloutItem))`. The previous `_on_no_bg_toggled` handler was removed — transparent is now handled directly by the `ColorPicker` widget's built-in transparent toggle.

**Why shared handlers:** Both types have identical property names and semantics, so the same `ModifyPropertyCommand` calls work. No code duplication needed.

---

### 3. Snagit Writer (`snapmock/io/snagit_writer.py`)

**What:** `_item_to_callout()` now writes actual property values instead of hardcoded constants.

| Field | Before | After |
|-------|--------|-------|
| `StrokeWidth` | `3` | `int(item._border_width)` |
| `ToolPadding` | `4` | `int(item._padding)` |
| `ToolVerticalAlign` | `"Center"` | Mapped from `item._vertical_align.value` |

**Why:** Enables round-trip fidelity — callout frame properties modified in SnapMock are preserved when saving to .snagx format.

---

### 4. Snagit Reader (`snapmock/io/snagit_reader.py`)

**What:** `_convert_callout()` now reads frame properties from the Snagit JSON.

**Added after existing `_bg_color` / `_border_color` assignment:**
```python
item._border_width = float(obj.get("StrokeWidth", 2))
item._padding = float(obj.get("ToolPadding", 4))
valign_map = {"Top": VerticalAlign.TOP, "Center": VerticalAlign.CENTER, "Bottom": VerticalAlign.BOTTOM}
item._vertical_align = valign_map.get(obj.get("ToolVerticalAlign", "Center"), VerticalAlign.CENTER)
```

**Why:** Ensures callout properties from Snagit files are imported accurately rather than silently replaced with defaults.

---

### 5. Bug Fix: focusOutEvent Killing Text Editor (`snapmock/core/view.py`)

**Problem:** When `_start_editing()` calls `editor.setFocus()`, the `SnapView` loses focus, triggering `focusOutEvent`. That handler unconditionally called `active.cancel()`, which called `_finish_editing()`, destroying the editor immediately after creation.

- **Drag-to-create:** Item created with `text=""` → `_finish_editing` removed it (empty text cleanup) → user saw nothing.
- **Click-to-place:** Item created with `text="Text"` → `_finish_editing` restored it (text unchanged) → text appeared but was never editable.
- **Click to re-edit:** Editor created and immediately destroyed — user couldn't edit.

**Fix:** Check if focus moved to a child of the viewport (e.g., the inline text editor) before cancelling:
```python
focus_widget = QApplication.focusWidget()
vp = self.viewport()
focus_to_child = (
    focus_widget is not None
    and vp is not None
    and vp.isAncestorOf(focus_widget)
)

if self._tool_manager is not None and not focus_to_child:
    # ... restore previous tool, cancel active operation
```

**Why `isAncestorOf`:** The editor is created as `_RichTextEditor(viewport)`, making it a child of the viewport. This check correctly distinguishes "focus moved to our own editor" from "focus moved to an unrelated widget."

---

### 6. Bug Fix: Auto-scroll Not Stopping (`snapmock/core/view.py`)

**Problem:** When the mouse moved to the viewport edge, auto-scroll started via a timer. When the mouse left the viewport (to reach the toolbar or ruler), `mouseMoveEvent` stopped firing but the timer kept running — causing the canvas to scroll indefinitely.

**Fix (two parts):**

**A. `leaveEvent` override:** Stops auto-scroll when the mouse leaves the view entirely:
```python
def leaveEvent(self, event: object) -> None:
    self._stop_auto_scroll()
    super().leaveEvent(event)
```

**B. `_do_auto_scroll` viewport check:** Each timer tick verifies the cursor is still over the viewport using `vp.underMouse()`:
```python
def _do_auto_scroll(self) -> None:
    vp = self.viewport()
    if vp is not None and not vp.underMouse():
        self._stop_auto_scroll()
        return
    # ... proceed with scrolling
```

**Why `underMouse()` instead of `rect.contains(mapFromGlobal())`:** The initial implementation used coordinate mapping, but the ruler's bottom/right edge shares the exact pixel boundary with the viewport's top/left edge, causing false positives. `underMouse()` is a Qt built-in that precisely identifies which widget the cursor is actually over, accounting for overlapping sibling widgets.

---

### 7. Bug Fix: Auto-scroll During Text Editing (`snapmock/core/view.py`)

**Problem:** The TextTool's `is_active_operation` returns `True` during inline editing (`_editing_item is not None`). This caused auto-scroll to trigger whenever the user moved the mouse near the viewport edge while editing text — even without holding a mouse button. Auto-scroll only makes sense during button-held drag operations.

**Fix:** Added a mouse button check to the auto-scroll trigger condition:
```python
# Before
if (... and self._tool_manager.active_tool.is_active_operation):

# After
if (... and self._tool_manager.active_tool.is_active_operation
    and event.buttons() != Qt.MouseButton.NoButton):
```

**Why not change `is_active_operation`:** That property is also used for space-bar pan suppression, which should remain active during text editing (so spacebar inserts a space rather than triggering pan). The mouse button check precisely targets the auto-scroll use case.

---

## Tests Added

### `tests/test_rich_text.py` (10 new tests)

| Test | What it verifies |
|------|-----------------|
| `test_callout_frame_property_defaults` | Default values: bg=#FFFFCC, border=#000000, border_width=2.0, border_radius=4.0, padding=4.0, vertical_align=CENTER |
| `test_callout_bg_color_setter` | bg_color property setter works |
| `test_callout_border_color_setter` | border_color property setter works |
| `test_callout_border_width_clamped` | Negative values clamped to 0.0 |
| `test_callout_border_radius_clamped` | Negative values clamped to 0.0 |
| `test_callout_padding_clamped` | Negative values clamped to 0.0 |
| `test_callout_vertical_align_setter` | VerticalAlign enum setter works |
| `test_callout_serialize_frame_properties` | All frame properties appear in serialized dict |
| `test_callout_deserialize_frame_properties_roundtrip` | Full serialize → deserialize preserves all values |
| `test_callout_deserialize_backward_compat` | Legacy data without frame keys loads with correct defaults |

### `tests/test_transform_resize.py` (1 new test)

| Test | What it verifies |
|------|-----------------|
| `test_callout_scale_geometry_frame_properties` | `scale_geometry(2.0, 2.0)` doubles border_width, border_radius, and padding |

---

## Design Decisions

1. **Visible defaults for CalloutItem** (`border_width=2.0`, `border_radius=4.0`, `padding=4.0`, `vertical_align=CENTER`): These match the previously hardcoded behavior, ensuring existing callouts look identical after the upgrade.

2. **No `auto_size` / `_height` for CalloutItem**: CalloutItem dimensions come from its `_rect`, which is set by the callout tool and drag handles. Adding auto-size would require rethinking the rect model — deferred to a future phase.

3. **Shared handler approach in PropertyPanel**: Using `isinstance(item, (TextItem, CalloutItem))` in all text box handlers because both types expose identical property names. No abstraction or interface needed.

4. **`underMouse()` for auto-scroll check**: More reliable than coordinate-based containment checks because it correctly handles overlapping sibling widgets (rulers) that share pixel boundaries with the viewport.

5. **Mouse button check for auto-scroll**: Simpler and more correct than adding a new `wants_auto_scroll` property to BaseTool. Auto-scroll is inherently a drag-time behavior.

---

## Files Modified

| File | Type | Summary |
|------|------|---------|
| `snapmock/items/callout_item.py` | Modified | Added frame properties, property accessors, refactored paint/boundingRect/scale_geometry, updated serialize/deserialize |
| `snapmock/ui/property_panel.py` | Modified | Widened Text Box section for CalloutItem, hidden auto-size checkbox for callouts |
| `snapmock/io/snagit_writer.py` | Modified | Use actual callout property values instead of hardcoded constants |
| `snapmock/io/snagit_reader.py` | Modified | Read callout frame properties from Snagit JSON |
| `snapmock/core/view.py` | Modified | Three bug fixes: focusOutEvent, auto-scroll stop, auto-scroll trigger |
| `tests/test_rich_text.py` | Modified | 10 new callout frame property tests |
| `tests/test_transform_resize.py` | Modified | 1 new callout scale_geometry test |

---

### 8. Tool Defaults Mode in PropertyPanel

**Problem:** When the text or callout tool was active with no item selected, the PropertyPanel showed only the Canvas section. Users had no way to pre-configure text properties (font, colors, border, padding, etc.) before creating new items — they had to create the item first, then modify its properties.

**Solution:** The PropertyPanel now detects when the active tool is "text" or "callout" with no selection and enters a "tool-defaults mode," displaying the Text and Text Box sections populated with the tool's creation defaults. Changes made in this mode are stored on the tool instance and applied to every subsequent item created.

#### BaseTool: Creation Defaults (`snapmock/tools/base_tool.py`)

Added a `_creation_defaults: dict[str, Any]` field to `BaseTool.__init__` and a read-only `creation_defaults` property that returns the mutable dict. This allows PropertyPanel to read/write default values without needing a new class or data structure.

#### TextTool: Defaults + Apply (`snapmock/tools/text_tool.py`)

**`__init__`:** Initializes `_creation_defaults` with TextItem's constructor defaults:
| Key | Default | Source |
|-----|---------|--------|
| `font_family` | `DEFAULT_FONT_FAMILY` | constants.py |
| `font_size` | `DEFAULT_FONT_SIZE` | constants.py |
| `bold` | `False` | |
| `italic` | `False` | |
| `underline` | `False` | |
| `text_color` | `QColor(black)` | |
| `bg_color` | `QColor(DEFAULT_TEXT_BG_COLOR)` | transparent |
| `border_color` | `QColor(DEFAULT_TEXT_BORDER_COLOR)` | transparent |
| `border_width` | `DEFAULT_TEXT_BORDER_WIDTH` | 0.0 |
| `border_radius` | `DEFAULT_TEXT_BORDER_RADIUS` | 0.0 |
| `padding` | `DEFAULT_TEXT_PADDING` | 8.0 |
| `vertical_align` | `VerticalAlign.TOP` | |
| `auto_size` | `True` | |

**`_apply_creation_defaults(item)`:** Reads the dict and sets all properties on the item via property setters (font, text_color, bg_color, border_color, border_width, border_radius, padding, vertical_align, auto_size).

**`mouse_release`:** Calls `_apply_creation_defaults(item)` in both the drag-to-create and click-to-create paths, after constructing the `TextItem` but before `AddItemCommand`.

**`_start_editing`:** Now calls `self._selection_manager.select_items([item])` so the newly created item is in the selection, allowing PropertyPanel to show and modify its live properties during editing.

#### CalloutTool: Defaults + Apply (`snapmock/tools/callout_tool.py`)

Same pattern as TextTool with callout-specific defaults:
| Key | Default | Rationale |
|-----|---------|-----------|
| `bg_color` | `QColor("#FFFFCC")` | Callout yellow |
| `border_color` | `QColor("#333333")` | Visible border |
| `border_width` | `2.0` | Callout default |
| `border_radius` | `12.0` | Rounded bubble |
| `padding` | `10.0` | Callout default |

No `auto_size` key — callout dimensions are controlled by `_rect`.

**`_apply_creation_defaults(item)`** and **`mouse_release`** follow the same pattern as TextTool.

#### PropertyPanel: Tool-Defaults Mode (`snapmock/ui/property_panel.py`)

**New fields:**
- `_tool_manager: ToolManager | None` — set via `set_tool_manager()`
- `_active_tool_id: str` — updated on `tool_changed` signal

**`set_tool_manager(tm)`:** Connects `tm.tool_changed` to `_on_tool_changed`.

**`_on_tool_changed(tool_id)`:** Stores the tool_id and calls `_refresh_from_selection()`.

**`_refresh_from_selection` changes:**
```python
in_tool_defaults = (
    not has_selection and self._active_tool_id in ("text", "callout")
)
```
When `in_tool_defaults` is True:
- Text and Text Box sections are shown; Transform, Appearance, Info, and Canvas sections are hidden
- `_populate_from_tool_defaults()` fills widgets from the active tool's `creation_defaults` dict
- Auto-size checkbox is hidden for callout tool (matches behavior when a CalloutItem is selected)

**Handler early-return paths:** All 13 text/text-box change handlers have an early-return path that writes to the `creation_defaults` dict (no command stack) when in tool-defaults mode:
- `_on_font_family_changed`, `_on_font_size_changed`, `_on_bold_changed`, `_on_italic_changed`, `_on_underline_changed`, `_on_text_color_changed`
- `_on_text_bg_color_changed`, `_on_text_border_color_changed`, `_on_text_border_w_changed`, `_on_text_corner_radius_changed`, `_on_text_padding_changed`, `_on_text_valign_changed`, `_on_text_auto_size_changed`

Note: `_on_no_bg_toggled` and `_on_no_fill_toggled` were removed — transparent colors are now handled natively by the `ColorPicker` widget, which includes a `∅` transparent toggle button and emits `QColor(0,0,0,0)` through the normal `color_changed` signal.

**Helper methods:**
- `_in_tool_defaults_mode()` — returns True if no selection and text/callout tool active
- `_active_tool_defaults()` — returns the active tool's `creation_defaults` dict
- `_populate_from_tool_defaults()` — populates all Text + Text Box widgets from the defaults dict

#### MainWindow Wiring (`snapmock/main_window.py`)

Added one line after PropertyPanel creation:
```python
self._property_panel.set_tool_manager(self._tool_manager)
```

#### Design Decisions

1. **Defaults stored on tool instances** — matches existing pattern where tools own their options. Defaults persist for the tool's lifetime (session), reset when the application restarts.

2. **No undo/redo for defaults** — changing defaults is a UI preference, not a document mutation. Handlers write directly to the dict without touching the command stack.

3. **Auto-size checkbox hidden for callout tool** — same logic as when a CalloutItem is selected, since callout dimensions come from `_rect`.

4. **Dict-based storage** — simple, no new classes needed. PropertyPanel reads/writes the same dict the tool reads during item creation.

5. **Item selected on edit start** — `_start_editing()` now calls `select_items([item])` so the PropertyPanel transitions from tool-defaults mode to live-item mode as soon as editing begins. This ensures property changes during the initial create-edit session affect the actual item.

---

### 9. ColorPicker Transparent Color Support (`snapmock/ui/color_picker.py`)

**Problem:** The `ColorPicker` widget opened Qt's `QColorDialog` with no alpha/transparency support. A few color properties (fill, text background) had separate "No fill" / "No background" checkboxes, but most color pickers (stroke, text color, text border, canvas background) had no way to select transparent. The approach was inconsistent and incomplete.

**Solution:** The `ColorPicker` widget now natively supports transparency, so every color picker in the app gets the feature automatically:

- **Widget restructured:** Changed from `QPushButton` to `QWidget` containing a custom `_SwatchButton` (with `paintEvent` override) and a `∅` transparent toggle button.
- **`allow_transparent` parameter** (default `True`): Controls whether the transparent toggle appears. When `True`, a checkable `∅` button appears next to the swatch.
- **Transparent toggle behavior:** Clicking `∅` saves the current opaque color and emits `QColor(0, 0, 0, 0)`. Clicking again restores the last opaque color. This gives users a quick way to toggle transparent on any color property.
- **Checkerboard swatch:** `_SwatchButton.paintEvent()` draws a checkerboard pattern behind the color fill when `alpha < 255`. For fully transparent colors, only the checkerboard is visible, making it obvious the color is transparent. For semi-transparent colors, the checkerboard shows through proportionally.
- **Alpha channel in QColorDialog:** The dialog now uses `ShowAlphaChannel` option, so users can also fine-tune alpha values directly.

**Redundant controls removed from PropertyPanel:**
- `_no_fill_check` checkbox and its container widget — fill color transparency is now handled by the fill `ColorPicker`'s transparent toggle
- `_no_bg_check` checkbox and its container widget — text background transparency is now handled by the background `ColorPicker`'s transparent toggle
- `_on_no_fill_toggled()` and `_on_no_bg_toggled()` handler methods — no longer needed
- Related `setChecked()` calls in `_refresh_from_selection()` and `_populate_from_tool_defaults()`

**Why a widget-level solution:** Every `ColorPicker` instance in the app (stroke, fill, text color, text background, text border, canvas background) automatically gains transparent support without any per-picker changes in `PropertyPanel` or `ItemPropertiesDialog`.

---

## Files Modified

| File | Type | Summary |
|------|------|---------|
| `snapmock/items/callout_item.py` | Modified | Added frame properties, property accessors, refactored paint/boundingRect/scale_geometry, updated serialize/deserialize |
| `snapmock/ui/property_panel.py` | Modified | Widened Text Box section for CalloutItem, hidden auto-size checkbox for callouts, added tool-defaults mode with 14 handler early-return paths |
| `snapmock/io/snagit_writer.py` | Modified | Use actual callout property values instead of hardcoded constants |
| `snapmock/io/snagit_reader.py` | Modified | Read callout frame properties from Snagit JSON |
| `snapmock/core/view.py` | Modified | Three bug fixes: focusOutEvent, auto-scroll stop, auto-scroll trigger |
| `snapmock/tools/base_tool.py` | Modified | Added `_creation_defaults` dict and `creation_defaults` property |
| `snapmock/tools/text_tool.py` | Modified | Initialized creation defaults, added `_apply_creation_defaults()`, select item on edit start |
| `snapmock/tools/callout_tool.py` | Modified | Initialized creation defaults, added `_apply_creation_defaults()` |
| `snapmock/main_window.py` | Modified | Wired PropertyPanel to ToolManager via `set_tool_manager()` |
| `snapmock/ui/color_picker.py` | Modified | Rewrote as QWidget with `_SwatchButton` (checkerboard paint), `∅` transparent toggle, `ShowAlphaChannel` in dialog; removed `_no_fill_check`/`_no_bg_check` from PropertyPanel |
| `tests/test_rich_text.py` | Modified | 10 new callout frame property tests |
| `tests/test_transform_resize.py` | Modified | 1 new callout scale_geometry test |

---

## Verification

- **371 tests pass** (`uv run pytest`)
- **Lint clean** (`uv run ruff check .`)
- Manual testing confirmed: PropertyPanel controls work for callouts, .smk round-trip preserves properties, backward-compatible loading works, text editing no longer interrupted by focus/scroll issues
- Manual testing confirmed: activate text tool with nothing selected → PropertyPanel shows Text + Text Box sections with defaults → change properties → create text item → item has modified properties
- Manual testing confirmed: same for callout tool → shows callout defaults (yellow bg, visible border) → modify → create callout → properties match
- Manual testing confirmed: select an existing item → panel shows item properties (not tool defaults) → deselect → panel returns to tool defaults
- Manual testing confirmed: property changes during initial create-edit session affect the active item
- Manual testing confirmed: every ColorPicker shows a `∅` transparent toggle button
- Manual testing confirmed: clicking `∅` sets color to alpha=0 and shows checkerboard swatch; clicking again restores the previous opaque color
- Manual testing confirmed: QColorDialog includes an alpha channel slider

---

### 10. Universal Flip/Mirror (`snapmock/items/base_item.py` + all items)

**Problem:** There was no way to flip/mirror an annotation item horizontally or vertically. Users needing a mirrored arrow, flipped stamp, or reversed text callout had no option.

**Solution:** Added `flip_horizontal` and `flip_vertical` as universal bool properties on the `SnapGraphicsItem` base class, rendered via QPainter transforms, with UI in three locations (Arrange menu, Property Panel, context menu).

#### Base Class: Properties + Paint Helpers (`snapmock/items/base_item.py`)

**New fields** (in `__init__`):
| Field | Type | Default |
|-------|------|---------|
| `_flip_horizontal` | `bool` | `False` |
| `_flip_vertical` | `bool` | `False` |

**Property accessors:** `flip_horizontal` and `flip_vertical` getter/setter pairs. Setters call `self.update()` to trigger repaint.

**Paint helper methods:**
```python
def _apply_flip(self, painter: QPainter) -> None:
    if self._flip_horizontal or self._flip_vertical:
        painter.save()
        br = self.boundingRect()
        cx, cy = br.center().x(), br.center().y()
        painter.translate(cx, cy)
        painter.scale(
            -1.0 if self._flip_horizontal else 1.0,
            -1.0 if self._flip_vertical else 1.0,
        )
        painter.translate(-cx, -cy)

def _end_flip(self, painter: QPainter) -> None:
    if self._flip_horizontal or self._flip_vertical:
        painter.restore()
```

**Why translate-scale-translate:** The flip must be around the item's visual center, not the origin. Translating to the bounding rect center, scaling with -1, and translating back produces a mirror about the center axis. The `save()`/`restore()` pairs ensure the transform doesn't leak to other items.

**Why no-op when both flags are False:** The `if` guard avoids unnecessary `save()`/`restore()` calls during normal (unflipped) painting.

#### All 12 Item `paint()` Methods Updated

Each item's `paint()` method was updated with `self._apply_flip(painter)` after the null check and `self._end_flip(painter)` at the end:

| Item Class | Base | File |
|-----------|------|------|
| RectangleItem | VectorItem | `items/rectangle_item.py` |
| EllipseItem | VectorItem | `items/ellipse_item.py` |
| LineItem | VectorItem | `items/line_item.py` |
| ArrowItem | VectorItem | `items/arrow_item.py` |
| FreehandItem | VectorItem | `items/freehand_item.py` |
| HighlightItem | VectorItem | `items/highlight_item.py` |
| BlurItem | SnapGraphicsItem | `items/blur_item.py` |
| TextItem | SnapGraphicsItem | `items/text_item.py` |
| CalloutItem | SnapGraphicsItem | `items/callout_item.py` |
| NumberedStepItem | SnapGraphicsItem | `items/numbered_step_item.py` |
| StampItem | SnapGraphicsItem | `items/stamp_item.py` |
| RasterRegionItem | SnapGraphicsItem | `items/raster_region_item.py` |

**Why per-item rather than overriding `QGraphicsItem.paint` in the base:** `SnapGraphicsItem.paint` is abstract — subclasses implement it directly. The helper pair is the cleanest way to inject the transform without changing the abstract contract.

#### Serialization

**VectorItem** (`items/vector_item.py`): Added `flip_horizontal` and `flip_vertical` keys to `_base_data()` and reading them in `_apply_base_data()` with `data.get("flip_horizontal", False)`. This automatically covers all 6 VectorItem subclasses (Rectangle, Ellipse, Line, Arrow, Freehand, Highlight).

**Non-VectorItem items** (BlurItem, TextItem, CalloutItem, NumberedStepItem, StampItem, RasterRegionItem): Each item's `serialize()` includes `flip_horizontal` and `flip_vertical` keys, and `deserialize()` reads them with `False` defaults for backward compatibility.

**Why `False` default:** Existing serialized data without flip keys loads correctly — items display unflipped, matching their original appearance.

#### Arrange Menu (`snapmock/main_window.py`)

**Added to `_setup_arrange_menu()`:** Two new actions ("Flip Horizontal", "Flip Vertical") between the z-order actions and the Align submenu, with a separator above and below.

**Action references:** `self._flip_h_action` and `self._flip_v_action` stored on `MainWindow.__init__` alongside other arrange action refs.

**Handler methods:**
```python
def _arrange_flip_horizontal(self) -> None:
    items = self._selected_snap_items()
    cmds: list[BaseCommand] = [
        ModifyPropertyCommand(
            item, "flip_horizontal", item.flip_horizontal, not item.flip_horizontal
        )
        for item in items
    ]
    self._scene.command_stack.push(MacroCommand(cmds, "Flip Horizontal"))
```

**Why `MacroCommand`:** When multiple items are selected, each gets its own `ModifyPropertyCommand` toggling its flip state. Wrapping in a `MacroCommand` makes the entire operation a single undo step.

**Why toggle (`not item.flip_horizontal`):** Each item's current flip state is toggled independently. If some items are already flipped and others aren't, each toggles to the opposite state.

**Menu state updates:** Both flip actions are added to the `_update_menu_states()` loop that enables/disables actions based on `has_selection`.

#### Context Menu (`snapmock/ui/context_menus.py`)

**Added to `build_item_context_menu()`:** "Flip Horizontal" and "Flip Vertical" entries after the Distribute submenu, before the final separator + Properties. Both are enabled when `has_sel` is True. Handlers connect to `parent._arrange_flip_horizontal` and `parent._arrange_flip_vertical`.

#### Property Panel Transform Section (`snapmock/ui/property_panel.py`)

**New widgets:** Two checkable `QPushButton`s ("Flip H", "Flip V") in a horizontal layout, added as a "Flip:" row after the Rotation row in the Transform section.

**Signal connections:** `toggled` signals connected to `_on_flip_h_changed` and `_on_flip_v_changed`.

**Refresh:** In `_refresh_from_selection()`, after setting rotation:
```python
self._flip_h_btn.setChecked(item.flip_horizontal)
self._flip_v_btn.setChecked(item.flip_vertical)
```

**Handlers:** Standard `ModifyPropertyCommand` pattern:
```python
def _on_flip_h_changed(self, checked: bool) -> None:
    if self._updating:
        return
    item = self._first_selected_item()
    if item is None:
        return
    cmd = ModifyPropertyCommand(item, "flip_horizontal", item.flip_horizontal, checked)
    self._scene.command_stack.push(cmd)
```

#### Design Decisions

1. **Paint-time transform, not geometry mutation:** Flipping via `painter.scale(-1, 1)` preserves the original geometry (rects, paths, points). This means `boundingRect()`, `shape()`, hit-testing, and serialized data all remain unchanged. The flip is purely visual.

2. **No keyboard shortcuts for flip:** Flip is a less common operation than z-order changes. Menu and panel access is sufficient.

3. **Checkable QPushButton instead of QCheckBox:** Buttons provide clearer visual feedback for a binary toggle that represents a spatial transform rather than a boolean preference.

---

### 11. Text Property Panel — Mixed Formatting (`snapmock/ui/property_panel.py`)

**Problem:** When inline-editing a text item containing mixed formatting (e.g., some bold and some non-bold text), the PropertyPanel always showed the item's default font properties. If the user selected a range with mixed bold/non-bold, the Bold checkbox showed the default font's bold state — not the actual selection. There was no indication that the selection contained mixed formatting, and no way to see cursor-position formatting in real time.

**Solution:** The PropertyPanel now connects to the active text editor's cursor/selection/format signals during editing, analyzes the selection for mixed states, and displays indeterminate indicators when formatting values differ across the selection.

#### Editor Signal Management

**New state fields** (in `__init__`):
| Field | Type | Purpose |
|-------|------|---------|
| `_editor_connected` | `bool` | Guards against duplicate signal connections |
| `_connected_editor` | `QWidget \| None` | Reference to the currently connected editor |

**`_ensure_editor_connected()`:** Gets the active editor via `_get_active_editor()`. If it's a different editor (or first connection), disconnects the old one and connects three signals:
- `cursorPositionChanged` → `_on_editor_cursor_changed`
- `selectionChanged` → `_on_editor_cursor_changed`
- `currentCharFormatChanged` → `_on_editor_format_changed`

**`_disconnect_editor()`:** Safely disconnects all three signals with `try/except (TypeError, RuntimeError)` to handle cases where the editor has already been destroyed (Qt deletes C++ objects independently of Python refs).

**Why three signals:**
- `cursorPositionChanged` — fires when cursor moves (arrow keys, click), updates panel to show format at cursor position
- `selectionChanged` — fires when selection changes (shift+arrows, mouse drag), triggers mixed-state analysis
- `currentCharFormatChanged` — fires when formatting changes via keyboard shortcuts (Ctrl+B, Ctrl+I, Ctrl+U) without cursor movement, keeps panel in sync

#### Refresh Logic Changes

In `_refresh_from_selection()`, the text refresh block was split into two paths:

```python
if has_text:
    if item.is_editing:
        self._ensure_editor_connected()
        self._refresh_text_from_cursor()
    else:
        self._disconnect_editor()
        self._bold_check.setTristate(False)
        self._italic_check.setTristate(False)
        self._underline_check.setTristate(False)
        # ... show item's default font properties as before
```

**Why disconnect when not editing:** Prevents stale signal connections from a previous editing session. Also resets tristate on checkboxes to ensure clean two-state behavior when viewing item defaults.

#### `_refresh_text_from_cursor()` Method

**No selection path:** Reads `cursor.charFormat()` → shows definite values for all properties.

**Selection path:** Iterates `QTextBlock` / `QTextFragment` across the document, checking each fragment that overlaps the selection range:

```python
block = doc.begin()
while block.isValid():
    it = block.begin()
    while not it.atEnd():
        fragment = it.fragment()
        if fragment.isValid():
            frag_start = fragment.position()
            frag_end = frag_start + fragment.length()
            if frag_end > sel_start and frag_start < sel_end:
                # Collect font properties into sets
                ...
        it += 1
    block = block.next()
```

**Why fragment iteration instead of sampling cursor positions:** Fragment iteration is O(n) over the document structure (not selection length), handles all formatting boundaries correctly, and doesn't miss short formatted runs. Sampling at positions could miss a 1-character bold run in the middle of a long selection.

**Property sets collected:** `families`, `sizes`, `bolds`, `italics`, `underlines`, `colors` — each a `set` collecting unique values across overlapping fragments.

#### Mixed State Display

| Property | Single value | Multiple values (mixed) |
|----------|-------------|------------------------|
| Font family | `setCurrentFont(QFont(family))` | `lineEdit().setText("")` (blank) |
| Font size | `setValue(size)` | `setValue(0)` — displays blank via `setSpecialValueText(" ")` |
| Bold | `setTristate(False)` + `setChecked(value)` | `setTristate(True)` + `setCheckState(PartiallyChecked)` |
| Italic | same as Bold | same as Bold |
| Underline | same as Bold | same as Bold |
| Text color | `color = QColor(...)` | Last known color shown (no indeterminate state for ColorPicker) |

**Font size range change:** `setRange(0, 200)` with `setSpecialValueText(" ")`. Value 0 displays as blank, indicating mixed sizes. The `_on_font_size_changed` handler guards `if value == 0: return` to prevent applying a 0pt font size.

#### User Interaction from Mixed State

When Bold/Italic/Underline checkboxes are in `PartiallyChecked` state, the next click transitions to `Checked` or `Unchecked`. The change handlers call `setTristate(False)` before processing to ensure the checkbox returns to two-state mode:

```python
def _on_bold_changed(self, checked: bool) -> None:
    if self._updating:
        return
    self._bold_check.setTristate(False)
    # ... proceed with mergeCharFormat to apply uniform value
```

**Why `setTristate(False)` in handler:** Without this, Qt's tristate checkbox cycles through three states on each click (checked → partially checked → unchecked), which is confusing for formatting toggles. Resetting to two-state after the first user click ensures the expected toggle behavior.

**Existing `mergeCharFormat()` logic:** Already correctly applies a uniform formatting value to the entire selection — no changes needed in the font/bold/italic/underline/color handlers.

#### Feedback Loop Prevention

The `_on_editor_cursor_changed` and `_on_editor_format_changed` slots wrap `_refresh_text_from_cursor()` in the `_updating` flag:

```python
def _on_editor_cursor_changed(self) -> None:
    if self._updating:
        return
    self._updating = True
    try:
        self._refresh_text_from_cursor()
    finally:
        self._updating = False
```

**Why:** Without this guard, changing a widget value from `_refresh_text_from_cursor()` would trigger the widget's `valueChanged` signal, which would call a handler that modifies the editor's format, which would emit `currentCharFormatChanged`, which would call `_refresh_text_from_cursor()` again — an infinite loop.

#### Design Decisions

1. **Fragment-based analysis** — more reliable than sampling cursor positions. Correctly handles all formatting boundaries regardless of fragment length.

2. **No indeterminate state for ColorPicker** — the existing `ColorPicker` widget has no concept of "mixed" (it always shows a color swatch). Adding a mixed state would require a UI redesign of the color picker. For now, the last known color is shown when mixed, which is acceptable since text color differences are visually obvious in the editor.

3. **`setSpecialValueText(" ")` for font size** — using a space instead of empty string because Qt requires at least one character for special value text. Visually appears blank in the spin box.

4. **Editor signals connected lazily** — `_ensure_editor_connected()` is only called when `item.is_editing` is True, avoiding unnecessary signal connections when items are selected but not being edited.

5. **Safe disconnect with try/except** — Qt can destroy C++ objects before Python `__del__` runs, so disconnect attempts on a destroyed editor raise `RuntimeError`. The try/except handles this gracefully.

---

### 12. Horizontal Alignment PropertyPanel Control

**What:** Added a QComboBox for horizontal text alignment (Left / Center / Right / Justify) to the PropertyPanel Text section, with full support for tool-defaults mode, live editing mode, non-editing mode, and Snagit I/O.

**Background:** Horizontal alignment was already functional via keyboard shortcuts (Ctrl+L/E/R/J) in the text editor and stored at the `QTextBlockFormat` level in the `QTextDocument` HTML. However, there was no PropertyPanel control for it, and the Snagit writer hardcoded alignment values.

#### PropertyPanel (`snapmock/ui/property_panel.py`)

**Combo widget** — added after the Bold/Italic/Underline row:
```python
self._text_align_combo = QComboBox()
self._text_align_combo.addItem("Left", Qt.AlignmentFlag.AlignLeft)
self._text_align_combo.addItem("Center", Qt.AlignmentFlag.AlignHCenter)
self._text_align_combo.addItem("Right", Qt.AlignmentFlag.AlignRight)
self._text_align_combo.addItem("Justify", Qt.AlignmentFlag.AlignJustify)
```

**`_set_align_combo()` helper** — masks the input flag to horizontal component before matching:
```python
def _set_align_combo(self, alignment: Qt.AlignmentFlag) -> None:
    h_align = alignment & Qt.AlignmentFlag.AlignHorizontal_Mask
    for i in range(self._text_align_combo.count()):
        if self._text_align_combo.itemData(i) == h_align:
            self._text_align_combo.setCurrentIndex(i)
            return
    self._text_align_combo.setCurrentIndex(0)
```

**`_on_text_align_changed()` handler** — supports three modes:
1. **Tool-defaults mode:** writes `horizontal_align` to active tool defaults dict
2. **Edit mode:** calls `editor.setAlignment(alignment)` on the active `QTextEdit`
3. **Non-editing mode:** calls `item.set_alignment(alignment)` on the item

**Refresh paths:**
- **Non-editing:** reads first block alignment via `item.get_block_format().alignment()`
- **During editing, no selection:** reads current block alignment via `cursor.blockFormat().alignment()`
- **During editing, with selection:** collects alignment across all blocks in selection; if mixed, sets `setCurrentIndex(-1)` (blank)

#### AlignCenter vs AlignHCenter

`Qt.AlignmentFlag.AlignCenter` (132) is a composite flag equal to `AlignHCenter | AlignVCenter`. When masked to horizontal component via `& AlignHorizontal_Mask`, it becomes `AlignHCenter` (4). The combo stores `AlignHCenter` directly so that masking and comparison work consistently.

#### Tool Creation Defaults

**`snapmock/tools/text_tool.py`** and **`snapmock/tools/callout_tool.py`:**
- Added `"horizontal_align": Qt.AlignmentFlag.AlignLeft` to `_creation_defaults`
- Added alignment application in `_apply_creation_defaults()`:
  ```python
  ha = d.get("horizontal_align", Qt.AlignmentFlag.AlignLeft)
  if isinstance(ha, Qt.AlignmentFlag):
      item.set_alignment(ha)
  ```
- `_populate_from_tool_defaults()` reads the `horizontal_align` key and calls `_set_align_combo()`

#### Snagit I/O

**`snapmock/io/snagit_reader.py`:**
- Added horizontal alignment reading in both `_convert_callout` and `_convert_text`:
  ```python
  halign_map = {
      "Left": Qt.AlignmentFlag.AlignLeft,
      "Center": Qt.AlignmentFlag.AlignCenter,
      "Right": Qt.AlignmentFlag.AlignRight,
  }
  ha = halign_map.get(obj.get("ToolHorizontalAlign", "Center"))
  if ha is not None:
      item.set_alignment(ha)
  ```

**`snapmock/io/snagit_writer.py`:**
- Added `_get_halign_str()` helper that reads the first block's alignment and maps to Snagit string:
  ```python
  def _get_halign_str(item: TextItem | CalloutItem) -> str:
      block_fmt = item.get_block_format()
      align = block_fmt.alignment() & Qt.AlignmentFlag.AlignHorizontal_Mask
      return {
          Qt.AlignmentFlag.AlignLeft: "Left",
          Qt.AlignmentFlag.AlignHCenter: "Center",
          Qt.AlignmentFlag.AlignRight: "Right",
          Qt.AlignmentFlag.AlignJustify: "Justify",
      }.get(align, "Left")
  ```
- Replaced hardcoded `"ToolHorizontalAlign": "Center"` and `"Left"` with `_get_halign_str(item)` calls in both `_item_to_callout` and `_item_to_text`

---

## Files Modified (Updated)

| File | Type | Summary |
|------|------|---------|
| `snapmock/items/base_item.py` | Modified | Added `flip_horizontal`/`flip_vertical` properties, `_apply_flip()`/`_end_flip()` paint helpers |
| `snapmock/items/vector_item.py` | Modified | Added flip fields to `_base_data()` and `_apply_base_data()` |
| `snapmock/items/rectangle_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()` |
| `snapmock/items/ellipse_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()` |
| `snapmock/items/line_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()` |
| `snapmock/items/arrow_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()` |
| `snapmock/items/freehand_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()` |
| `snapmock/items/highlight_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()` |
| `snapmock/items/blur_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()`, flip in serialize/deserialize |
| `snapmock/items/text_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()`, flip in serialize/deserialize |
| `snapmock/items/callout_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()`, flip in serialize/deserialize |
| `snapmock/items/numbered_step_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()`, flip in serialize/deserialize |
| `snapmock/items/stamp_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()`, flip in serialize/deserialize |
| `snapmock/items/raster_region_item.py` | Modified | Added `_apply_flip`/`_end_flip` in `paint()`, flip in serialize/deserialize |
| `snapmock/main_window.py` | Modified | Added Flip Horizontal/Vertical to Arrange menu with handlers, menu state updates |
| `snapmock/ui/context_menus.py` | Modified | Added Flip Horizontal/Vertical to item context menu |
| `snapmock/ui/property_panel.py` | Modified | Added flip buttons, editor signal management for mixed formatting, `_refresh_text_from_cursor()` with fragment analysis, mixed state display, horizontal alignment combo |
| `snapmock/tools/text_tool.py` | Modified | Added `horizontal_align` to creation defaults and `_apply_creation_defaults()` |
| `snapmock/tools/callout_tool.py` | Modified | Added `horizontal_align` to creation defaults and `_apply_creation_defaults()` |
| `snapmock/io/snagit_reader.py` | Modified | Added `ToolHorizontalAlign` reading for callout and text items |
| `snapmock/io/snagit_writer.py` | Modified | Added `_get_halign_str()` helper, writes actual alignment instead of hardcoded values |

---

## Verification (Updated)

- **371 tests pass** (`uv run pytest`)
- **No new lint errors** (`uv run ruff check .` — only pre-existing F841 in test file)
- **No new mypy errors** (`uv run mypy snapmock` — only pre-existing errors in other files)
- Manual: create items, flip via all 3 UI surfaces (Arrange menu, context menu, Property Panel), verify rendering, undo/redo, save/load round-trip
- Manual: edit text with mixed formatting (bold some words, different sizes), verify panel shows indeterminate states (partial-check for bold/italic/underline, blank font size, blank font family)
- Manual: from mixed state, click Bold checkbox → applies uniform bold to selection, checkbox returns to two-state
- Manual: move cursor within edited text → panel updates to show formatting at cursor position
- Manual: use Ctrl+B/Ctrl+I/Ctrl+U in editor → panel updates via `currentCharFormatChanged` signal
- Manual: change horizontal alignment via PropertyPanel combo while editing text → block alignment updates immediately
- Manual: select text spanning blocks with different alignments → combo shows blank (mixed state)
- Manual: change alignment in tool-defaults mode → new items created with that alignment
- Manual: load Snagit .snagx file with Center/Left/Right aligned text → alignment preserved
- Manual: save file with non-default alignment → `ToolHorizontalAlign` value reflects actual alignment
