# Kickoff Prompt: The Freeform Blur Brush and the Highlighter's Straightening

Last Updated: 09-11-26 20:04 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory: this work changes the Blur item and tool, the Highlight item and tool, the Select tool's modes, the Tool Options Bar, the Property Panel, and the project file, which every other session touches too.

This is the work the Basic Shape remainder close-out named on 09-11-26 (`docs/Basic-Shape-Remainder-Implementation.md`, Section 10): everything of the Blur / Pixelate tool that decision 4 of that work (option A) deferred, and the Highlighter's drawing behaviour, which no work has built. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) still governs the standards; this one governs the work. Where the two disagree, the general prompt wins and this one is corrected. The work is five phases and a close-out; a session pasting this prompt starts at the first phase not marked done in Section 1 of the notes document this work creates.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Finish the Blur, Highlighter, and Eyedropper Tools PRD's first two tools:

- `PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html` (version 1.6), the Blur / Pixelate tool: the brush-painted region of 2.3, the Freeform and Whole Layer shapes of 2.4, `brush_size`, `alpha_mask`, `source_mode`, and `source_layer_id` of 2.5, the Brush Size control and the Freeform toggle of 2.6, the mask clipping and the source rule of 2.7, the brush editing mode of 2.8, the performance of 2.10, the freeform hints of 2.11, `alpha_mask_data` of 5.1 and 7.1, `ModifyBlurMaskCommand` of 6.1, and the 8.1 rows those sections own.
- The same PRD's Highlighter, Section 3: the real-time smoothing and the release simplification of 3.2, the auto-straightening, manual straight mode, and snap-to-axis of 3.3, the `auto_straighten`, `straighten_threshold`, and `snap_to_axis` properties of 3.4, the Auto-Straighten and Snap to Axis toggles of 3.5, the point editing of 3.6, the hints of 3.9, the angled marker-tip cursor of 3.1, and the keys of 5.2 and 7.2, with the 8.2 rows.
- `PRDs/SnapMock-General-UI-PRD.html` (version 2.20): the 5.3 rows for both tools, the 6.6 cursor rows for the brush and the marker tip, and the Section 8 rows for the Property Panel's new controls.
- `PRDs/SnapMock-Technical-Architecture-PRD.html` (version 1.32): Section 6.1's `items.json` entries for both items, Section 3.9 where the capture's source rule changes, and Section 10 for any module this work adds.

The session opens by presenting the four decisions below with the consequential decision template and waits. Nothing is built before they are taken.

## Read first, in this order

1. `docs/Basic-Shape-Remainder-Implementation.md` (revision 1.3 or later), whole: Section 2 (the four decisions, the kickoff's silences, and the four corrections the reading found), Section 7 (what Phase 5 built: `RenderEngine.render_below`, `SnapScene.content_revision`, the cache key, the mask and the feather), Section 8 (the deviations, including the Blur PRD rows left open), Section 9 (the suite runs and the timing-sensitive tests), Section 10 (the close-out and the display checks owed).
2. `docs/Vector-Item-Properties-Implementation.md` (revision 1.4): Section 2.2's silence on Auto-Straighten and Snap to Axis, which says why they are not shown today, and Section 4, which says what the Highlighter's bar became.
3. `docs/General-UI-Implementation.md` (revision 1.34): Section 5.1's decisions, Section 6's open bullets, Section 17.2's walk table (a walk that names item types one by one takes every new item), and Sections 19 to 22 as the pattern.
4. `PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html`, Sections 2 and 3 whole, with 5.1, 5.2, 6.1, 7.1, 7.2, 8.1, 8.2, and the 1.5 and 1.6 rows. The Highlighter's hit testing is 3.8 and its status hints 3.9; earlier notes called the hints 3.8, and this prompt's numbers are the PRD's.
5. `PRDs/SnapMock-General-UI-PRD.html`: 5.2, 5.3, 6.6, Section 8, 12.2, and the 2.13 to 2.20 rows.
6. `PRDs/SnapMock-Technical-Architecture-PRD.html`: 3.1.4, 3.5 (the raster pipeline), 3.7 (the command types), 3.9 (the rendering pipeline), 6.1, 9.1 (the dependency policy), 10, and the 1.29 to 1.32 rows.
7. `snapmock/items/blur_item.py` (`region_path`, `effect_rect`, `rendered`, `_render`, `_key`, the watch on the command stack), `snapmock/core/render_engine.py` (`render_below`), `snapmock/core/scene.py` (`content_revision`), `snapmock/tools/blur_tool.py` (the bar's groups and their visibility rules, `region_for`), `snapmock/items/highlight_item.py` (points only), `snapmock/tools/highlight_tool.py` (the bar, `cap_icon`, the preset swatches), `snapmock/tools/point_edit.py` (`PointEditSession` and the five sessions, `PointHandlesItem`), `snapmock/tools/select_tool.py` (how a mode is entered and left), `snapmock/commands/geometry_commands.py`, `snapmock/items/freehand_item.py` (the pipeline the Highlighter may borrow), `snapmock/items/raster_region_item.py` (how a PNG is embedded as base64), `snapmock/io/project_serializer.py` (the archive holds `manifest.json`, `layers.json`, `items.json`, and one thumbnail; there is no `raster/` directory yet), `snapmock/ui/cursors.py`, `snapmock/ui/property_panel.py` (the Blur section), `snapmock/ui/tool_options_bar.py` (`set_control_visible`).
8. `tests/test_blur_modes.py`, `tests/test_tools/test_highlight_tool.py`, `tests/test_point_edit.py`, `tests/test_freehand_point_edit.py`, `tests/test_io/test_project_serializer.py`, `tests/test_accessibility.py`: read the test names to know what each area already asserts.

Do not write anything until all eight are read.

## Starting state, verified at commit 035fa5e on 09-11-26

- The Blur tool draws Gaussian, Pixelate, and Solid Fill regions over rectangles and ellipses, with a corner radius, feathering, an inverted mask, the item's opacity, and a border. `RenderEngine.render_below` captures what lies under a region, `SnapScene.content_revision` rises on every command and layer change, and the result is cached until the region, a property, the scene transform, the zoom (rounded to a power of two), or that revision changes. The bar of 2.6 and the Property Panel's Blur section are built.
- Not built, and this work's first four phases: the brush of 2.3, the Freeform and Whole Layer shapes of 2.4 (`BlurRegionShape` has two members, and a file naming either unbuilt shape reads as a rectangle), `brush_size`, `alpha_mask`, `source_mode`, and `source_layer_id` of 2.5, the brush editing of 2.8, `ModifyBlurMaskCommand` of 6.1, `alpha_mask_data` of 5.1 and 7.1, and the background render, the progress indicator, and the half-resolution drag preview of 2.10.
- The Highlighter draws the raw mouse points with no smoothing, no simplification, and no straightening; `auto_straighten`, `straighten_threshold`, and `snap_to_axis` exist in neither the item nor the bar nor the file; `HighlightItem` stores `points` and has no point-editing session; the tool's cursor is the crosshair, not the angled marker tip. Its bar is Highlight Color, Stroke Width, Blend Mode, Stroke Style, the Cap Style toggles, the six preset swatches, and the Shadow toggle.
- Point editing is a mode of the Select tool (`tools/point_edit.py`) with sessions for the line, the arrow, the arc, the polygon, and the freehand item; a double-click enters it, Escape leaves it, and Edit > Deselect's Escape asks the active tool first through `BaseTool.handle_escape`.
- The suite at the last code commit (437416d) ran 1358 tests with 13 skipped and one environmental deselection: 1344 passed and one failed, the pre-existing timing-sensitive Zoom tool test, which passes alone. Ruff and mypy are clean.
- Measured on this machine: a 1000 by 1000 px region renders in about 200 ms for Gaussian Blur, 50 ms for Pixelate, and 3 ms for Solid Fill, and an inverted Gaussian over the whole 1920 by 1080 canvas in about 0.5 s. The 100 ms of 2.10 is unmet.

## Phases

Five phases and a close-out, each phase several commits, each closed out before the next starts. A phase's steps are one commit each. Every commit is ruff-clean and mypy-strict-clean with the suite passing. Run the full suite as `QT_QPA_PLATFORM=offscreen uv run pytest -q -o faulthandler_timeout=120 --deselect tests/test_property_panel.py::test_font_combo_reflects_text_item_font` to a log file in the background from a scratch `git worktree` at the commit under test, with `python -m pytest` from the worktree's root (the venv's interpreter): it now takes fifty to sixty-five minutes and slows when other test runs share the machine, so run one at a time and keep foreground runs small. A test that reads a timer-driven animation drives the animation's clock by hand. No test opens a real popover or dialog unpatched or reads the real application data directory (the `isolated_settings` fixture redirects it).

### Phase 1, the mask (Blur PRD 2.4, 2.5, 2.7, 5.1, 7.1)

1. **Decisions and the notes document.** Present decisions 1 to 4; create `docs/Freeform-Blur-Highlighter-Implementation.md` (revision 1.0) with the phase table, the decisions, and the silences decided; add the rows the decisions imply. One commit.
2. **The mask on the item.** Per decision 1: the Freeform member of `BlurRegionShape`, the mask's storage on `BlurItem`, its place in `region_path` and `_render` (the mask replaces the shape in the clip, feathering and inverting as the shape does), the rect that follows the painted bounds, the scale rule on resize, and the keys of 5.1 and 7.1 with their size rule. Tests: a painted mask clipping the effect, the feather over a mask, inversion over a mask, the round trip in and out of a `.smk` file, an older file unaffected.
3. **Phase close-out.** Blur PRD rows; the notes' section; the phase-table row done; the next required step.

### Phase 2, the brush (Blur PRD 2.3, 2.6, 2.11)

1. **Painting.** The Freeform toggle in the bar and the Brush Size control (5 to 200), the brush cursor of 6.6 (a circle at the brush's size), press-and-drag painting into the mask, strokes accumulating, Enter or a tool switch finalizing, Escape cancelling, and a region with an empty mask discarded; the hints of 2.11. Tests: a painted region's mask and rect, several strokes accumulating, the cursor, the finalize and cancel routes, the hints.
2. **Phase close-out.** As Phase 1's.

### Phase 3, brush editing (Blur PRD 2.8, 6.1)

1. **The editing mode.** A double-click on a freeform region with the Select tool enters brush editing beside the point-editing mode of the Basic Shape remainder work: painting adds, Alt+painting erases, the brush cursor shows the size, Enter or Escape leaves, and each stroke pushes `ModifyBlurMaskCommand` (6.1) so undo returns the mask; the Property Panel's Brush size row. Tests: entering and leaving, adding and erasing, the command with undo and redo, a double-click on a rectangular region doing nothing.
2. **Phase close-out.** As Phase 1's.

### Phase 4, Whole Layer, the source modes, and the render (Blur PRD 2.4, 2.5, 2.7, 2.10)

1. **Whole Layer and the source modes.** Per decision 3: the Whole Layer shape covering the canvas with no region to draw, `source_mode` and `source_layer_id` filtering what `render_below` paints, and the Property Panel's rows; the cache key takes them. Tests: a whole-layer region, each source mode's pixels, a file naming a deleted layer, the round trip.
2. **The render's speed.** Per decision 4. Tests: the measured time recorded in the notes, a pixel check that the faster path still obscures, and the quality note at the largest radius.
3. **Phase close-out.** As Phase 1's.

### Phase 5, the Highlighter (Blur PRD 3.2, 3.3, 3.4, 3.5, 3.6, 3.9)

1. **Drawing and straightening.** Per decision 2: the real-time smoothing and the release simplification of 3.2, the auto-straightening of 3.3 with `straighten_threshold`, Shift's manual straight mode and Shift+Alt's 15-degree constraint, the snap to horizontal and vertical within 5 degrees, the 4 px minimum, the three keys of 3.4 with 5.2 and 7.2, the Auto-Straighten and Snap to Axis toggles of 3.5, the marker-tip cursor of 3.1, and the hints of 3.9. Tests: a near-straight stroke straightened and a curved one kept, the threshold, Shift and Shift+Alt, the snap, the keys' round trip, the bar's toggles, the cursor, the hints.
2. **Point editing.** A `HighlightPointSession` in `tools/point_edit.py`: two handles for a straightened stroke and the simplified points for a freeform one (3.6), each drag a `ModifyGeometryCommand`. Tests as 3.6 lists.
3. **Phase close-out.** As Phase 1's.

### Close-out of the work

Blur PRD, General UI PRD, and Technical Architecture PRD rows for what was built and where it departs; the notes complete; the General UI notes' Section 23 pointer; the Basic Shape remainder notes' Section 10 pointer updated; the display checks owed carried forward; the next required step stated.

## Decisions to surface

Apply the two-part test from the global guidance. Four decisions are expected to pass it; present all four with the consequential decision template before Phase 1 step 2 and wait.

- **1. What a painted blur region stores.** When someone paints a blur over an irregular shape, the file keeps either the painted picture or the strokes that made it. The example: hiding one face in a group photo on a 1200 by 800 screenshot, a dozen strokes wide. Option A, the bitmap mask of 2.5, 7.1, and 6.1: one alpha image at canvas scale, written as a base64 PNG inside `items.json`, or as a file in the archive past 100 KB, with each edit keeping the mask before and after. Option B, the strokes: a list of brush strokes (path, width, add or erase) from which the mask is drawn whenever it is needed, so files stay small, a resize stays sharp, and one undo entry is one stroke. Why it matters: this is the file format of every painted blur and it sets how heavy undo is. The cost of A: a 1920 by 1080 mask is about 2 MB in memory and 30 to 100 KB per undo entry, and resizing the region resamples the mask, so its edges soften. Recommendation: A, because 2.5, 7.1, and 6.1 describe exactly that, because the serializer already embeds a raster region's PNG as base64 the same way, and because only a bitmap keeps an eraser's result exactly. Follow-on detail: the mask lives at canvas scale aligned to the region's rect, the rect follows the painted bounds, and the archive gains its first `raster/` entry when a mask passes 100 KB.
- **2. Where the Highlighter's smoothing comes from.** A highlighter stroke can use the Freehand tool's curve fitting or its own simple smoothing. The example: dragging a 24 px highlight along a line of text. Option A, 3.2 as written: a moving average over the last five points while drawing, then Ramer-Douglas-Peucker at 2 px on release, the item keeping `path_points` as 5.2 says. Option B, the Freehand item's pipeline: simplification then cubic Bezier fitting, the stroke stored as curve segments, one pipeline serving both tools. Why it matters: it sets the highlight's file keys and whether the two tools share one path. The cost of A: two smoothing pipelines in the code, and a slow curve at a very wide stroke shows faint facets. Recommendation: A, since 5.2 stores points, a 24 px band hides the facets, and the straightening of 3.3 works on points. Follow-on detail: the point editing of 3.6 then shows two handles for a straightened stroke and the simplified points otherwise.
- **3. How far the source modes go.** A blur can obscure everything beneath it, or only some of it. The example: a blur over a screenshot that must hide the text below it but not the arrow you drew under it. Option A, all three modes of 2.5: `all_below` (today's behaviour), `active_layer`, and `specific_layer` with a layer dropdown in the Property Panel. Option B, `all_below` and `active_layer` only, since the third needs a control that follows layer renames and deletions. Why it matters: 2.5 lists three, and the capture already walks the items, so the filter itself is small. The cost of A: the dropdown must follow renames and deletions, and a file naming a layer that is gone falls back to `all_below`. Recommendation: A.
- **4. How the Gaussian meets the 100 ms of 2.10.** The blur is about twice too slow at 1000 by 1000 px, so dragging a region stutters. Option A, blur a downscaled capture and scale the result back: about four times faster at half scale, indistinguishable at radius 10 and softer at radius 50. Option B, the background thread of 2.10 with the progress indicator past 2000 px: the first thread in the code, and a stale frame while it runs. Why it matters: 2.10 is an acceptance row and the tool is felt every time a region moves. The cost of A: a departure from 2.10's thread, and a small quality difference at the largest radii. Recommendation: A; B stays available if a region ever grows past what A can carry.

Everything else follows the PRDs; where they are silent or disagree, decide, note it under the notes' decisions section and the PRD rows, and continue. Silences known now:

- The mask is kept in canvas pixels and aligned to the region's rect; a resize resamples it, and a rotation leaves it in the item's own coordinates, where the capture already works.
- A freeform region's rect is the painted bounds, so the transform handles frame the paint rather than the drag.
- Brush editing and point editing are two modes of the Select tool: a double-click on a freeform region enters brush editing, a double-click on a rectangular or elliptical one does nothing, and neither mode starts while the other lasts.
- The Snagit writer keeps skipping a blur region whatever its shape, and a highlight keeps its present mapping.
- Auto-straightening and the snap to axis apply while drawing only and never retroactively, as 3.6 says; the Property Panel shows them for the tool's defaults, not for a placed stroke.
- The Whole Layer shape has no region to drag: the tool places it with one click, and its rect is the canvas.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- Every new module gets a row in Technical Architecture PRD Section 10 in the commit that creates it; none is expected beyond a mask helper, if decision 1 calls for one.
- Departures from any PRD are recorded in that PRD's change log with a version bump, not only in code comments.
- No control is disabled (General UI PRD 1.3); a control whose requirement is unmet says which, through `check_requirements`.
- Every new control gets an accessible name as it is created, and `tests/test_accessibility.py`'s audit passes over every new surface.
- Every walk over the scene's items that a new property joins is checked against the General UI notes' Section 17.2 table; `ResizeImageCommand._restore_geometry` is the one walk that names item types one by one.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- Document timestamps are read from the machine clock at the time of writing, never estimated.
- Commit messages end with the attribution block the session provides.

## When the work is complete

Update the phase table in `docs/Freeform-Blur-Highlighter-Implementation.md`, bump its revision, add a change-log row, and state the next required step. Two candidates are known: the Eyedropper's Section 4 rows that the General UI work did not build (the preview loupe, the sample sizes, the colour history, and the colour formats), which need checking against the code before a kickoff is written for them; and the Windows backend kickoff (`docs/Windows-Backend-Kickoff-Prompt.md`), which waits for a Windows machine. The display checks owed by the Basic Shape remainder work (curved and elbow arrows in point editing, individual corner radii, a freehand stroke's handles, each arc type, a star polygon, and each blur mode over a screenshot) are still owed, and this work adds a painted blur, an erased one, a straightened highlight, and the marker-tip and brush cursors to that list.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-11-26 20:04 | Claude (Claude Code) | Initial kickoff prompt, written at Doug's request after the Basic Shape remainder close-out: the Blur tool's freeform brush, Whole Layer, source modes, and render speed, and the Highlighter's smoothing, straightening, snap to axis, point editing, and cursor; starting state at commit 035fa5e; five phases and a close-out; four decisions; six silences. |
