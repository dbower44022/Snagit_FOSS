# Snagit .snagx File Format — Read/Write Support

## 1. Overview

SnapMock now supports reading and writing TechSmith Snagit `.snagx` files, enabling users to open Snagit captures with their annotations intact, edit them in SnapMock, and save them back in a format Snagit can consume. This eliminates the need for lossy PNG/JPEG export when migrating between tools.

### What is .snagx?

A `.snagx` file is a **ZIP archive** containing JSON metadata and PNG images — not XML. Each archive contains:

| File | Purpose |
|------|---------|
| `index.json` | Manifest listing page filenames |
| `metadata.json` | Capture metadata (app name, date, OS, window title) |
| `{GUID}.json` | Page data: canvas dimensions, background reference, annotation objects |
| `{GUID}.png` | Background screenshot image |
| `thumbnail.png` | Preview thumbnail |

Annotations are stored as a `CaptureObjects` array in the page JSON. Each object has a `ToolMode` string identifying its type, plus tool-specific properties.

### Validation Dataset

Implementation was validated against **237 sample `.snagx` files** from real Snagit usage containing:

- 80 files with annotations (157 files are screenshots without annotations)
- 176 total annotation objects across 8 ToolMode types
- Distribution: Text (35), Callout (34), Image (33), Highlight (29), Shape (25), Arrow (18), Line (1), Stamp (1)

**Result: 236 of 237 files load successfully.** The single failure is a corrupt archive missing its page JSON file.

---

## 2. Architecture

Three new modules in `snapmock/io/` follow the existing patterns established by `project_serializer.py`:

```
snapmock/io/
    rtf_utils.py        # RTF base64 encode/decode for Snagit text fields
    snagit_reader.py     # load_snagx(path) → SnapScene
    snagit_writer.py     # save_snagx(scene, path) → list[str] warnings
```

### Design Decisions

**1. No new dependencies.** RTF parsing is a lightweight custom implementation covering the subset Snagit actually uses (`\fonttbl`, `\colortbl`, `\fs`, `\cf`, `\b`, `\par`). No external RTF library is required.

**2. Round-trip fidelity via `_snagit_data`.** When reading, each item stores the original Snagit JSON dict as `_snagit_data`. When writing, if this attribute exists, the writer updates positions and re-emits the original data rather than generating from scratch. This preserves Snagit-specific fields (shadow settings, border styles, control points) that SnapMock doesn't model.

**3. Highlights become RectangleItems.** Snagit's `Highlight` is a semi-transparent colored rectangle. Since SnapMock's `HighlightItem` is a freehand stroke path (not a rectangle), Snagit highlights are mapped to `RectangleItem` with transparent stroke and semi-transparent fill, tagged with `_snagit_highlight = True` for correct round-trip export.

**4. Scene structure.** Loaded `.snagx` files create two layers: "Background" (containing the screenshot as a `RasterRegionItem`) and "Annotations" (containing all markup objects). This mirrors Snagit's implicit layer model.

**5. Graceful degradation.** Unsupported item types are skipped with warnings rather than causing failures. The writer returns a list of warning strings that the UI displays to the user.

---

## 3. Format Mapping

### 3.1 Reading: Snagit → SnapMock

| Snagit ToolMode | Snagit Properties | SnapMock Item | Key Mapping |
|---|---|---|---|
| `Arrow` | PointsArray, ForegroundColor, StrokeWidth | `ArrowItem` | PointsArray → QLineF endpoints, ForegroundColor → stroke_color |
| `Line` | PointsArray, ForegroundColor, StrokeWidth | `LineItem` | Same as Arrow without arrowhead |
| `Shape` (Rectangle) | PointsArray, ForegroundColor, BackgroundColor, StrokeWidth | `RectangleItem` | PointsArray corners → setPos + local QRectF(0,0,w,h) |
| `Shape` (RoundedRectangle) | + CornerRadiusRatio | `RectangleItem` | CornerRadiusRatio × min(w,h) → corner_radius |
| `Highlight` | PointsArray, BackgroundColor, Opacity | `RectangleItem` | Rectangle with semi-transparent fill, zero stroke, tagged `_snagit_highlight` |
| `Callout` | PointsArray, RTFEncodedText, CalloutTails, BackgroundColor, ForegroundColor | `CalloutItem` | RTF → text/font/color, CalloutTails → tail_tip (converted to local coords) |
| `Text` | PointsArray, RTFEncodedText | `TextItem` | RTF → text/font/color, PointsArray width → item _width |
| `Image` | PointsArray, Image (base64 PNG) | `RasterRegionItem` | Base64 decode → QPixmap, scaled to PointsArray bounding box |
| `Stamp` | PointsArray, Image (base64 PDF/PNG) | `RasterRegionItem` or skipped | PNG stamps decode normally; PDF stamps are skipped with warning |

### 3.2 Writing: SnapMock → Snagit

| SnapMock Item | Snagit ToolMode | Key Mapping |
|---|---|---|
| `ArrowItem` | `Arrow` | QLineF + pos → PointsArray, stroke_color → ForegroundColor |
| `LineItem` | `Line` | QLineF + pos → PointsArray |
| `RectangleItem` | `Shape` | QRectF + pos → PointsArray, corner_radius > 0 → RoundedRectangle + CornerRadiusRatio |
| `RectangleItem` (highlight-tagged) | `Highlight` | fill_color → BackgroundColor |
| `HighlightItem` | `Highlight` | Bounding rect → PointsArray, stroke_color → BackgroundColor |
| `CalloutItem` | `Callout` | Text/font/color → RTFEncodedText, tail_tip + pos → CalloutTails |
| `TextItem` | `Text` | Text/font/color → RTFEncodedText |
| `RasterRegionItem` | `Image` | QPixmap → base64 PNG in Image field |
| `EllipseItem` | — | **Skipped** (no Snagit equivalent) |
| `FreehandItem` | — | **Skipped** (no Snagit equivalent) |
| `BlurItem` | — | **Skipped** (no Snagit equivalent) |
| `NumberedStepItem` | — | **Skipped** (would need stamp PDF generation) |
| `StampItem` | — | **Skipped** (would need stamp PDF embedding) |

### 3.3 Coordinate System

- **PointsArray** format: Array of `"x,y"` strings (e.g., `["133,49", "586,85"]`)
- For Arrow/Line: `[start_point, end_point]`
- For Rectangle/Shape/Highlight/Text/Callout: `[top_left, bottom_right]`
- SnapMock items use local coordinates with `setPos()` for scene positioning. Reading converts PointsArray to `setPos(x, y)` + local geometry at origin. Writing adds `pos()` back to local coordinates.

### 3.4 Color Format

Snagit uses `#AARRGGBB` (ARGB hex). Qt's `QColor.NameFormat.HexArgb` produces the same format. Direct string pass-through works in both directions.

### 3.5 RTF Text Encoding

Snagit stores formatted text as **base64-encoded RTF** in `RTFEncodedText` fields.

**Reading:**
1. Base64-decode to get raw RTF string
2. Parse `\fonttbl` for font family name
3. Parse `\fs` for font size (RTF half-points ÷ 2 = points)
4. Parse `\colortbl` for text color (RGB)
5. Strip all control words to get plain text content

**Writing:**
1. Generate minimal RTF with `\fonttbl`, `\colortbl`, `\fs` from item properties
2. Escape special characters (`\`, `{`, `}`) in text content
3. Convert newlines to `\par`
4. Base64-encode the RTF string

**Limitation:** Only plain text with a single font/size/color is currently supported. Mixed formatting (bold words within a paragraph, multiple fonts) is lost on read and cannot be generated on write. See Future Work item #5.

---

## 4. UI Integration

### File > Open

The Open dialog now shows:
- "All Supported (*.smk *.snagx)" — default filter
- "SnapMock Projects (*.smk)"
- "Snagit Files (*.snagx)"
- "All Files (*)"

Extension detection in `_open_project()` routes `.snagx` files to `load_snagx()` and all others to `load_project()`.

### File > Save / Save As

Save As offers:
- "SnapMock Projects (*.smk)" — default
- "Snagit Files (*.snagx)"

If saving as `.snagx` produces warnings (unsupported items skipped), a warning dialog is shown listing each skipped item type.

Save (`Ctrl+S`) re-saves to the current file path using the correct serializer based on extension.

### Recent Files

Both `.smk` and `.snagx` files are added to the recent files list and can be reopened from the File menu.

---

## 5. Module Reference

### `snapmock/io/rtf_utils.py`

| Function | Signature | Description |
|---|---|---|
| `extract_text_from_rtf` | `(base64_rtf: str) → str` | Decode base64 RTF, strip control words, return plain text |
| `extract_font_from_rtf` | `(base64_rtf: str) → tuple[str, int, QColor]` | Parse font family, size (pt), color from RTF |
| `text_to_rtf_base64` | `(text, font_family, font_size, color) → str` | Generate minimal RTF, return base64-encoded |

### `snapmock/io/snagit_reader.py`

| Function | Signature | Description |
|---|---|---|
| `load_snagx` | `(path: Path) → SnapScene` | Load .snagx file, create scene with Background + Annotations layers |

Internal converters: `_convert_arrow`, `_convert_line`, `_convert_shape`, `_convert_highlight`, `_convert_callout`, `_convert_text`, `_convert_image`, `_convert_stamp`.

### `snapmock/io/snagit_writer.py`

| Function | Signature | Description |
|---|---|---|
| `save_snagx` | `(scene: SnapScene, path: Path) → list[str]` | Save scene as .snagx ZIP, return list of warnings |

Internal converters: `_item_to_arrow`, `_item_to_line`, `_item_to_shape`, `_item_to_highlight`, `_item_to_highlight_rect`, `_item_to_callout`, `_item_to_text`, `_item_to_image`.

### `snapmock/config/constants.py` (additions)

| Constant | Value | Description |
|---|---|---|
| `SNAGIT_EXTENSION` | `".snagx"` | File extension for Snagit files |
| `SNAGIT_FORMAT_VERSION` | `"1.0"` | Format version written to index.json |

---

## 6. Testing & Verification

### Automated

| Test Type | Method | Result |
|---|---|---|
| Lint | `uv run ruff check .` | All new/modified files pass |
| Type check | `uv run mypy snapmock/io/rtf_utils.py snagit_reader.py snagit_writer.py` | Pass (strict mode) |
| Existing tests | `uv run pytest` | 251 pass, 0 regressions |
| Bulk load | Load all 237 sample .snagx files | 236/237 succeed (1 corrupt archive) |
| Round-trip | Load .snagx → save .snagx → reload → compare item counts | Pass for all tested files |

### Manual Verification Checklist

- [ ] `uv run python -m snapmock` → File > Open → select .snagx → annotations visible over background
- [ ] Annotations are editable (select, move, resize)
- [ ] File > Save As → select "Snagit Files" → saves .snagx
- [ ] Reopen the saved .snagx → annotations match
- [ ] Open .snagx with unsupported items → items silently skipped on load
- [ ] Save scene with EllipseItem as .snagx → warning dialog shown
- [ ] File > Save on a .snagx file → saves correctly (no format conversion)
- [ ] Recent files list includes .snagx files

---

## 7. Known Limitations

1. **PDF stamps cannot be rendered.** Snagit stamps are stored as base64-encoded PDF. Qt6 does not have a built-in PDF-to-image renderer available on all platforms. PDF stamps are skipped with a log warning.

2. **Single-page only.** Only the first page of multi-page `.snagx` files is loaded. Multi-page documents are rare but possible.

3. **Rich text is flattened.** Mixed formatting within a single text block (e.g., "Hello **world**") is reduced to plain text with the first font/size/color found.

4. **Shadow properties are preserved but not rendered.** Drop shadow data round-trips through `_snagit_data` but SnapMock does not visually render shadows.

5. **Some Snagit-only properties are pass-through only.** BorderStyle, DashType, ControlPoints, TailStyle, TextOutlineColor, ToolPadding, etc. are preserved in round-trip but not mapped to SnapMock visual properties.

---

## 8. Future Work — TODO

### High Priority

- [ ] **Rich text support** — Parse bold (`\b`), italic (`\i`), underline (`\ul`), and mixed fonts within RTF blocks. This affects both Callout and Text items. Would require switching from plain `str` text storage to a rich text model (QTextDocument or custom).

- [ ] **Drop shadow rendering** — Map `DropShadowEnabled`, `ShadowBlur`, `ShadowColor`, `ShadowDirectionX/Y`, `ShadowOpacity` to `QGraphicsDropShadowEffect`. Affects Arrow, Line, Shape, Callout, Text, Stamp items.

- [ ] **Dash/line styles** — Map `DashType` (Solid, Dash, Dot, DashDot, DashDotDot) to `QPen.setDashPattern()`. Affects Arrow, Line, Shape, Callout, Text items.

- [ ] **PDF stamp rendering** — Use `QPdfDocument` (available in Qt 6.4+) or an external library (e.g., `pymupdf`) to render PDF stamp data to QPixmap. Would enable loading the Stamp ToolMode objects that currently get skipped.

### Medium Priority

- [ ] **Border styles** — Map `BorderStyle` (Inset, Middle, Outset) to stroke offset logic. Currently all borders are drawn as "Middle" (centered on the edge).

- [ ] **Text alignment** — Map `ToolHorizontalAlign` (Left, Center, Right) and `ToolVerticalAlign` (Top, Center, Bottom) to Qt text alignment flags in TextItem and CalloutItem.

- [ ] **Text padding** — Map `ToolPadding` to internal margin in TextItem and CalloutItem rendering.

- [ ] **Multiple callout shapes** — Map `CalloutShape` values (`CTBalloon1` through `CTBalloon6`, `CTBasicSpeechBubble1`, etc.) to different visual callout styles. Currently all callouts render as rounded rectangles.

- [ ] **Callout tail styles** — Map `TailStyle` (Triangle, Remix, None) and `ControlPoints` (bezier curves) to different tail rendering paths.

- [ ] **Multi-page documents** — Support loading all pages from `index.json.Pages[]`, either as separate scenes or as a page navigation UI.

- [ ] **Ellipse shape in Snagit** — While not found in our 237 samples, `ToolShape: "Ellipse"` likely exists. If encountered, map to `EllipseItem`. The reverse mapping (SnapMock → Snagit) would also need this.

### Low Priority

- [ ] **Text outline** — Map `TextOutlineColor` and `TextOutlineWidth` to stroked text rendering (QPainterPath text with stroke pen).

- [ ] **Image expansion** — Handle `ImageExpansionFromObjects` and `ViewBoxExpansionFromObjects` which describe how the canvas was expanded to accommodate annotations that extend beyond the original screenshot.

- [ ] **Simplify mode** — Parse and apply `SimplifySettings` (Snagit's "Simplify" feature that replaces UI elements with simplified blocks).

- [ ] **Freehand ↔ Snagit** — If Snagit adds a freehand/pen tool (or if one exists outside our sample set), add bidirectional mapping.

- [ ] **NumberedStep → Stamp export** — Render `NumberedStepItem` as a PNG image and export as a Snagit `Image` object, rather than skipping it entirely.

- [ ] **EllipseItem → Image export** — Same approach: render unsupported vector items as raster `Image` objects for lossless (if not editable) export.

- [ ] **BlurItem export** — Render blur effect to raster and export as `Image`, or investigate whether Snagit has a blur/redaction ToolMode not present in our samples.

- [ ] **Unit tests for snagit I/O** — Add dedicated pytest tests for:
  - RTF extraction (plain text, font parsing, color parsing, generation)
  - Coordinate conversion (PointsArray ↔ QRectF/QLineF)
  - Color format pass-through
  - Reader: load specific .snagx fixtures and verify item types/positions
  - Writer: save and verify ZIP structure and JSON content
  - Round-trip: load → save → reload → compare
  - Error handling: corrupt archives, missing fields, unknown ToolModes

- [ ] **Preserve metadata on re-save** — Currently `metadata.json` is preserved on round-trip but new saves get minimal metadata. Could populate `AppName`, `CaptureDate`, `WindowName` more accurately.

- [ ] **Thumbnail generation with annotations** — Current thumbnail is just the background image. Could render the full scene (background + annotations) to the thumbnail for more accurate previews.
