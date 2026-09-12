# Freeform Blur Brush and Highlighter Straightening Implementation Notes

Last Updated: 09-11-26 20:14 · Revision 1.0

Implements the remainder of the Blur / Pixelate tool and the whole of the Highlighter's drawing behaviour from the Blur, Highlighter, and Eyedropper Tools PRD (`PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html`, version 1.6 at the start), with the General UI PRD (version 2.20) and Technical Architecture PRD (version 1.32) rows they own, in the five phases and the close-out defined by `docs/Freeform-Blur-Highlighter-Kickoff-Prompt.md` (revision 1.0). A session pasting that prompt starts at the first phase not marked done in Section 1. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) governs the standards; the General UI implementation notes (`docs/General-UI-Implementation.md`) hold the walk table of Section 17.2.

Starting state, verified at commit 0029bf7 on 09-11-26 (the kickoff names 035fa5e; 0029bf7 adds only the kickoff prompt and the Basic Shape remainder notes 1.4 pointer): the Blur tool draws Gaussian, Pixelate, and Solid Fill regions over rectangles and ellipses with a corner radius, feathering, an inverted mask, the item's opacity, and a border, cached against `SnapScene.content_revision` and captured through `RenderEngine.render_below`; the Freeform and Whole Layer shapes, `brush_size`, `alpha_mask`, `source_mode`, `source_layer_id`, `ModifyBlurMaskCommand`, and `alpha_mask_data` do not exist. The Highlighter draws the raw mouse points with no smoothing, no simplification, and no straightening; `auto_straighten`, `straighten_threshold`, and `snap_to_axis` exist in neither the item nor the bar nor the file; `HighlightItem` stores its points under `points` and has no point-editing session; the tool's cursor is the crosshair. Point editing is a mode of the Select tool with sessions for the line, the arrow, the arc, the polygon, and the freehand item. The suite at the last code commit (437416d) ran 1358 tests with 13 skipped and one environmental deselection: 1344 passed and one failed, the pre-existing timing-sensitive Zoom tool test, which passes alone. Ruff and mypy are clean.

## 1. Phase status

| Phase | Scope | Status | Commits |
|---|---|---|---|
| 1 | The mask (Blur PRD 2.4, 2.5, 2.7, 5.1, 7.1): the decisions and these notes, the mask on the item, close-out | In progress | this commit |
| 2 | The brush (2.3, 2.6, 2.11): painting, the Freeform toggle, the Brush Size control, the brush cursor, the hints, close-out | Not started | |
| 3 | Brush editing (2.8, 6.1): the editing mode beside point editing, `ModifyBlurMaskCommand`, the panel's Brush size row, close-out | Not started | |
| 4 | Whole Layer, the source modes, and the render (2.4, 2.5, 2.7, 2.10) | Not started | |
| 5 | The Highlighter (3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.9): drawing and straightening, point editing, close-out | Not started | |
| Close-out | PRD rows, the General UI notes' Section 23 pointer, the Basic Shape remainder notes' Section 10 pointer, the display checks owed | Not started | |

## 2. Decisions

### 2.1 Taken at the start of Phase 1 (09-11-26)

Presented with the consequential decision template and chosen by Doug on 09-11-26: the recommendation in every case ("use your recommendations for all of them").

| Decision | Choice | Effect |
|---|---|---|
| 1 What a painted blur region stores | A, the bitmap mask | `BlurItem` gains `alpha_mask`, a `QImage` in canvas pixels aligned to the region's rectangle, where opaque means obscure and transparent means leave alone; it replaces the region's shape in the clip of `_render`, feathering and inverting as the shape does. The rectangle follows the painted bounds, so the transform handles frame the paint rather than the drag. A resize resamples the mask through `scale_geometry`; a rotation leaves it in the item's own coordinates, where the capture already works. The key is `alpha_mask_data` (5.1, 7.1): a base64 PNG inline in `items.json` under 100 KB, and past that a `file:raster/blur_mask_<item_id>.png` reference to a new `raster/` entry in the `.smk` archive, which holds only `manifest.json`, `layers.json`, `items.json`, and one thumbnail today. Each edit stores the mask before and after (`ModifyBlurMaskCommand`, 6.1). The cost: a 1920 by 1080 mask is about 2 MB in memory and 30 to 100 KB per undo entry, and a resize softens the painted edges. The alternative, option B, a stroke list redrawn on demand, would have kept files small and resizes sharp but could not reproduce an eraser's result over overlapping strokes, and departs from 2.5, 7.1, and 6.1, which all describe an image. |
| 2 Where the Highlighter's smoothing comes from | A, 3.2 as written | A moving average over the last five points while drawing, then Ramer-Douglas-Peucker simplification at 2 px on release, the stroke stored as a point list under `path_points` (5.2). A file saved before this work carries the points under `points` and is read as `path_points`. The straightening of 3.3 then works on that list, and the point editing of 3.6 shows two handles for a straightened stroke and the simplified points for a freeform one. The cost: two smoothing pipelines in the code, the Freehand item's fit and this one, and faint facets on a slow curve at a very wide stroke. The alternative, option B, the Freehand item's simplify-then-fit pipeline with the stroke stored as cubic segments, would have shared one pipeline but departs from 5.2's `path_points` and leaves 3.3's arc-length test and 3.6's two handles without a point list to work on. |
| 3 How far the source modes go | A, all three modes of 2.5 | `source_mode` (`all_below`, `active_layer`, `specific_layer`) and `source_layer_id` filter what `RenderEngine.render_below` paints, with a layer dropdown in the Property Panel that follows renames and deletions; a file naming a layer that is gone falls back to `all_below`. Both join the cache key. The cost: the dropdown's upkeep and the fallback. The alternative, option B, the first two modes only, would have left 2.5's third mode unbuilt for the sake of one control. |
| 4 How the Gaussian meets the 100 ms of 2.10 | A, blur a downscaled capture | The Gaussian path captures at half scale, blurs, and scales the result back, at rest as during a drag, since the cache already keys on the zoom rounded to a power of two. About four times faster, so roughly 50 ms at 1000 by 1000 px against the 200 ms measured at the start. Indistinguishable at radius 10 and slightly softer at radius 50, where the content is already unrecognisable. The cost: a departure from 2.10's background thread, recorded as a PRD row, and the quality difference at the largest radii, with measured timings in Section 9. The alternative, option B, the background thread with the progress indicator past 2000 px, would have been the first thread in the code and would show a stale frame while it ran; it stays available if a region ever grows past what A can carry. |

### 2.2 The kickoff's six silences

Each decided as the kickoff recommended, on 09-11-26.

| Silence | Decision |
|---|---|
| Where the mask lives | Canvas pixels, aligned to the region's rectangle. A resize resamples it; a rotation leaves it in the item's own coordinates, where `render_below` already captures. |
| A freeform region's rectangle | The painted bounds, so the transform handles frame the paint rather than the drag. |
| Brush editing beside point editing | Two modes of the Select tool. A double-click on a freeform region enters brush editing, a double-click on a rectangular or elliptical one does nothing, and neither mode starts while the other lasts. |
| The Snagit writer | Keeps skipping a blur region whatever its shape, with its warning; a highlight keeps its present mapping. |
| Auto-straightening and the snap to axis | While drawing only, never retroactively (3.6). The Property Panel shows them for the tool's defaults, not for a placed stroke. |
| The Whole Layer shape | No region to drag: the tool places it with one click and its rectangle is the canvas. |

### 2.3 Corrections to the kickoff, found in the reading

- Blur PRD 2.8 says freeform editing pushes a `ModifyPropertyCommand` storing the old and new `alpha_mask`, while 6.1 defines `ModifyBlurMaskCommand` for exactly that edit. The kickoff names 6.1's command; 6.1 is built and the 2.8 wording is corrected by a PRD row.
- General UI PRD 6.6 carries no row for the brush cursor and none for the marker-tip cursor: it gives every drawing tool the crosshair. Both are additions to 6.6, not corrections of it.
- `BlurTool.status_hint` documents its hints as "2.10", which is the Performance section; the Blur tool's Status Bar Hints are 2.11. A comment fix in Phase 2.
- `HighlightItem` serializes its points under `points`, where 5.2 names `path_points`. Decision 2 renames the key and reads the old one.

### 2.4 Findings decided with the decisions

- The `.smk` archive has no `raster/` directory: `RasterRegionItem` embeds its PNG as base64 inside `items.json`. A mask past 100 KB creates the archive's first `raster/` entry, so `save_project` and `load_project` gain their first side files (Technical Architecture PRD 6.1 already describes the directory).
- `ResizeImageCommand._restore_geometry` is the one walk of the General UI notes' Section 17.2 kind that names item types one by one, and it already restores a blur region's corner radius and feather. The mask joins it in Phase 1.
- `BlurItem.scale_geometry` scales the rectangle, the blur radius, the corner radius, and the feather; the mask is resampled there in the same call.
- `HighlightItem` today keeps `points` as a list of pairs and rebuilds its `QPainterPath` on every added point. The straightening of 3.3 replaces the whole list on release, so the path is rebuilt from the list rather than appended to.

## 3. What Phase 1 built

Step 1, this commit: the decisions of Section 2; Blur PRD 1.7, General UI PRD 2.21, Technical Architecture PRD 1.33.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-11-26 20:14 | Claude (Claude Code) | Initial notes: the starting state at commit 0029bf7, the phase table, the four decisions (1 A, 2 A, 3 A, 4 A) and the kickoff's six silences as chosen 09-11-26, four corrections to the kickoff found in the reading, four findings decided with the decisions. Blur PRD 1.7, General UI PRD 2.21, Technical Architecture PRD 1.33. |
