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
    self._no_bg_check.setChecked(item.bg_color.alpha() == 0)
    self._text_border_color_picker.color = item.border_color
    # ... etc
```

**Auto-size checkbox:** Hidden for `CalloutItem` because callout dimensions come from its `_rect` (set by the callout tool or drag handles), not from a width+auto-height model:
```python
self._text_auto_size_check.setVisible(is_text_item)
```

**Handler type checks:** All seven text box change handlers (`_on_text_bg_color_changed`, `_on_no_bg_toggled`, `_on_text_border_color_changed`, `_on_text_border_w_changed`, `_on_text_corner_radius_changed`, `_on_text_padding_changed`, `_on_text_valign_changed`) changed from `isinstance(item, TextItem)` to `isinstance(item, (TextItem, CalloutItem))`.

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

## Verification

- **307 tests pass** (`uv run pytest`)
- **Lint clean** (`uv run ruff check .`)
- Manual testing confirmed: PropertyPanel controls work for callouts, .smk round-trip preserves properties, backward-compatible loading works, text editing no longer interrupted by focus/scroll issues
