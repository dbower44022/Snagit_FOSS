# Kickoff Prompt: Basic Shape Remainder and Blur Modes

Last Updated: 09-11-26 14:21 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory: this work adds two tools, changes the Select tool, the Arrow, Rectangle, Freehand, and Blur items and tools, the Tool Options Bar, the Property Panel, and the acceptance test, which every other session touches too.

This is the work the Vector Item Properties close-out named on 09-11-26 (`docs/Vector-Item-Properties-Implementation.md`, Section 8): everything of the Basic Shape Annotation Tools PRD that decision 3 of that work (option B) left for a kickoff of its own, plus the Blur tool's modes of the Blur, Highlighter, and Eyedropper PRD's Section 2. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) still governs the standards; this one governs the work. Where the two disagree, the general prompt wins and this one is corrected. The work is five phases and a close-out; a session pasting this prompt starts at the first phase not marked done in Section 1 of the notes document this work creates.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Finish the Basic Shape Annotation Tools PRD and the Blur tool:

- `PRDs/SnapMock-Basic-Shape-Annotation-Tools-PRD.html` (version 1.8): point editing for lines and arrows (3.5; the arrow rows of 4.7's hints), curved and elbow arrows (4.5, 4.6, and the Line Style toggles of 4.7), the Rectangle's individual corner radii (5.3, 5.4), the Arc tool (Section 7), the Polygon tool (Section 8), the Freehand tool's two-stage smoothing with Bezier storage, its Stroke Cap toggles and Close Path, its point editing and re-smoothing (9.3, 9.4, 9.6, 9.7, 9.8, 9.9), the data models of 10.2, 10.3, 10.5, 10.6, and 10.7, the commands of 11.3 to 11.5, and the Section 12 rows those sections own.
- `PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html` (version 1.4): the Blur / Pixelate tool of Section 2 (the three modes, the four region shapes, the properties of 2.5, the bar of 2.6, the rendering of 2.7, the editing of 2.8, the hit testing of 2.9) to the extent decision 4 below sets, with the 5.1, 7.1, and 8.1 rows.
- `PRDs/SnapMock-General-UI-PRD.html` (version 2.16): the 3.7 rows for Arc (Shift+A) and Polygon (G), the 5.3 rows for Arc, Polygon, Rectangle (the Uniform / Individual toggle), Freehand, and Blur, and 17.3's tool count.
- `PRDs/SnapMock-Technical-Architecture-PRD.html` (version 1.28): the registry of 3.3 (arc and polygon), the hierarchy of 4.2 (`ArcItem`, `PolygonItem`), Section 6.1's entries, and Section 10 for every module this work adds.

The session opens by presenting the four decisions below with the consequential decision template and waits. Nothing is built before they are taken.

## Read first, in this order

1. `docs/Vector-Item-Properties-Implementation.md` (revision 1.3 or later): Section 2 (the four decisions and the silences; decision 3 names what this work owns), Sections 3 to 5 (what each phase built: the shared properties, `apply_creation_defaults`, `head_paths`, the Arrow and Rectangle sections of the Property Panel, the bar's `ControlSpec` kinds and glyph dropdowns), Section 6's deviations, and Section 7 (the suite runs and the timing-sensitive tests).
2. `docs/General-UI-Implementation.md` (revision 1.33 or later): Section 5.1's decisions, Section 6's open bullets (the per-tool bar contents), Section 14 (presets and the codec's `_ENUM_TYPES`), Section 17.2 (the walk table; a new item type joins every walk that lists item types), and Sections 19 to 21 as the pattern.
3. `docs/Numbered-Steps-Stamps-Emoji-Implementation.md` (revision 1.5 or later): Section 2.2's silences on registering a tool (the palette count, the Tools menu row, the shortcut, the glyph), and Section 7 on running the suite.
4. `PRDs/SnapMock-Basic-Shape-Annotation-Tools-PRD.html`, whole, with the 1.6 to 1.8 rows that say what is built and what this work owns.
5. `PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html`, Section 2 whole, 5.1, 7.1, 8.1, and the 1.4 row.
6. `PRDs/SnapMock-General-UI-PRD.html`: 3.7 (the tool table with Arc and Polygon listed and not registered), 5.3, 6.6 (the cursor table), 8 (the Property Panel), 12.2, 17.3, and the 2.13 to 2.16 rows.
7. `PRDs/SnapMock-Technical-Architecture-PRD.html`: 3.3 (the registry), 3.4.2 (`TransformHandles`), 3.5 (the raster pipeline the Blur tool captures through), 4.2, 6.1, 10, and the 1.25 to 1.28 rows.
8. `snapmock/items/arrow_item.py` (`head_paths`, `_head_geometry`, `line_style`), `rectangle_item.py` (`effective_corner_radius`, `outline`), `freehand_item.py` (raw points only), `blur_item.py` (a stub that draws nothing useful), `vector_item.py` (`apply_creation_defaults`, `shadow_path`, `stroke_outline`), `snapmock/tools/arrow_tool.py`, `rectangle_tool.py`, `freehand_tool.py` (`_smoothed`, `MAX_SMOOTHING_EPSILON`), `blur_tool.py`, `select_tool.py` (`_handles`, the double-click route to `open_marker_editor`, the tail-tip handle of the callout if any), `snapmock/ui/transform_handles.py`, `snapmock/core/path_utils.py` (`simplify_rdp`), `snapmock/core/render_engine.py` (`render_layer_region`, `render_layers_composite`: what a blur region can capture), `snapmock/ui/tool_options_bar.py` (`ControlSpec`, `arrow_head_icon`, the `toggle` kind), `snapmock/ui/property_panel.py` (`_build_arrow_section`, `_build_rectangle_section`, the per-type section pattern), `snapmock/tools/tool_manager.py` and `snapmock/main_window.py` (where tools are registered and the Tools menu built), `snapmock/config/shortcuts.py`, `snapmock/ui/icons.py` (`TOOL_ICONS` and the vendored Tabler subset), `snapmock/io/project_serializer.py` (`ITEM_REGISTRY`), `snapmock/io/snagit_writer.py`.
9. `tests/test_arrow_heads.py`, `tests/test_corner_radius.py`, `tests/test_vector_properties.py`, `tests/test_vector_bar_presets.py`, `tests/test_tools/test_select_tool.py`, `tests/test_transform_resize.py`, `tests/test_main_toolbar.py` (the palette count), `tests/test_acceptance.py` (17.3), `tests/test_accessibility.py`: read the test names to know what each area already asserts.

Do not write anything until all nine are read.

## Starting state, verified at commit ab71e15 on 09-11-26

- The Vector Item Properties work is complete: every vector item carries stroke style, cap, join, the two opacities, the shadow, and a blend mode; the Arrow has head and tail styles and sizes on straight lines (`line_style` stored, never curved); the Rectangle has a uniform Corner Radius control; the Freehand tool simplifies raw points on release and stores points only; the palette has nineteen tools (no Arc, no Polygon); `BlurItem` and `BlurTool` are stubs (a rectangle that paints nothing but a placeholder, a tool with no options). The suite at ab71e15 ran 1272 tests with 13 skipped and one environmental deselection, 1258 passing; ruff and mypy are clean; the Zoom tool's Alt-at-release test and the X11 live-key test are timing-sensitive under load and pass alone.
- No point-editing mode exists for any item: the Select tool's `TransformHandles` resize, rotate, and move; the callout's tail is moved through its own handle in the Select tool. A double-click on an item routes to `open_marker_editor` for the marker items and to text editing for text items.
- `RenderEngine` renders a layer region and composites layers for merging; nothing captures "the content beneath an item" for a blur.

## Phases

Five phases and a close-out, each phase several commits, each closed out before the next starts. A phase's steps are one commit each. Every commit is ruff-clean and mypy-strict-clean with the suite passing. Run the full suite as `QT_QPA_PLATFORM=offscreen uv run pytest -q -o faulthandler_timeout=120 --deselect tests/test_property_panel.py::test_font_combo_reflects_text_item_font` to a log file in the background from a scratch `git worktree` at the commit under test, with `python -m pytest` from the worktree's root (the venv's interpreter): it takes thirty-five to forty minutes and slows when other test runs share the machine, so run one at a time. A test that reads a timer-driven animation drives the animation's clock by hand. No test opens a real popover or dialog unpatched or reads the real application data directory (the `isolated_settings` fixture redirects it).

### Phase 1, point editing and the arrow's lines (Basic Shape PRD 3.5, 4.5, 4.6, 4.7, 11.3)

1. **Decisions and the notes document.** Present decisions 1 to 4; create `docs/Basic-Shape-Remainder-Implementation.md` (revision 1.0) with the phase table, the decisions, and the silences decided; add the rows the decisions imply. One commit.
2. **The point-editing mode.** Per decision 1: a mode of the Select tool entered by a double-click on a line or an arrow, showing the endpoints as 8 by 8 px handles in the accent colour, dragging one with Shift constraining to 15 degrees, Escape or a click outside leaving, `ModifyGeometryCommand` (11.3) merging drags within 300 ms; the status hints of 3.8 and 4.8. Tests: enter, drag, constrain, leave, undo.
3. **Curved and elbow arrows.** `line_style` Curved draws a quadratic Bezier through `control_point` (the midpoint by default) and Elbow the two or three right-angle segments through `bend_point`; the arrowheads orient along the tangent or the terminal segment; the control point and bend point as the green handle of 4.5 and 4.6 in point editing; the Line Style toggles in the Arrow bar (4.7); the 10.2 keys `control_point` and `bend_point`. Tests: the rendered curve passes through the control point's influence, the elbow's right angles, the head's orientation, the round trip.
4. **Phase close-out.** Basic Shape PRD rows; the notes' section; the phase-table row done; the next required step.

### Phase 2, the Rectangle's corners and the Freehand pipeline (Basic Shape PRD 5.3, 5.4, 9.3, 9.6, 9.7, 9.8, 9.9)

1. **Individual corner radii.** `corner_radius_mode` and the four radii on `RectangleItem`, the path built with `arcTo` per corner (5.5), the Uniform / Individual toggle and the four spin boxes in the Rectangle bar and the Property Panel's Rectangle section, the 10.3 keys. Tests: each corner rounded alone, the mode round trip, the bar and the panel.
2. **The Freehand pipeline.** Per decision 2: the two-stage smoothing of 9.3 (Ramer-Douglas-Peucker then cubic Bezier fitting) with `path_points` and `bezier_segments` stored (10.7), re-smoothing from the raw points when the Smoothing slider changes with a selected freehand item (9.7), the Stroke Cap toggles and Close Path of 9.6 with `is_closed` filling the path (9.8) and the hit test of 9.9. Tests: the fitted path's segment count falls with smoothing, re-smoothing is non-destructive, a closed path fills and hits inside, the round trip, the bar.
3. **Freehand point editing.** The on-curve and off-curve handles of 9.7 in the point-editing mode of Phase 1, with Alt breaking continuity, a double-click on a segment inserting a point, a right-click deleting one. Tests as 9.7 lists.
4. **Phase close-out.** As Phase 1's.

### Phase 3, the Arc tool (Basic Shape PRD Section 7)

1. **`ArcItem` and the tool.** The three-step creation of 7.2 (drag the chord, move for the curvature, click to confirm), `ArcItem` with the 10.5 keys, the three arc types of 7.6 with the fill rules, the arrowheads shared with the Arrow through `head_paths`, the bar of 7.4, the hints of 7.7, the tool registered as the twentieth tool (Shift+A, a Tabler glyph, the Tools menu row, the palette count, 17.3). Tests: the three steps, the types, the arrowheads, the round trip, the registration.
2. **Arc point editing.** The three handles of 7.5 in the point-editing mode. Tests as 7.5 lists.
3. **Phase close-out.** As Phase 1's.

### Phase 4, the Polygon tool (Basic Shape PRD Section 8)

1. **`PolygonItem` and the tool.** Freeform and Regular modes of 8.2 with their state machines (click to place, double-click or the first vertex to close, Enter, right-click to remove, Escape; the drag for a regular polygon with Shift), the star option, the 10.6 keys, the bar of 8.4, the hints of 8.7, the tool registered as the twenty-first tool (G, a glyph, the Tools menu row, 17.3). Tests: both modes, the minimum of three vertices, the star, the open polyline, the round trip, the registration.
2. **Polygon point editing.** The vertex handles of 8.5 with `InsertVertexCommand` and `RemoveVertexCommand` (11.4, 11.5), the centre and radius handles of a regular polygon. Tests as 8.5 lists.
3. **Phase close-out.** As Phase 1's.

### Phase 5, the Blur tool's modes (Blur PRD Section 2)

1. **The capture and the three modes.** Per decision 4: `BlurItem` captures the content beneath it through the render engine, applies Gaussian blur (the `blur_image` passes of `items/shadow.py` at the region's radius), pixelate, or solid fill, clips to the rectangle or ellipse shape with feathering and the item's opacity, caches the result and invalidates it when the item moves or resizes, its properties change, or the layers below change; the 2.5 properties, the 2.6 bar (the mode toggles, the intensity slider whose label follows the mode, Fill Color, Region Shape, Corner Radius, Feather, Invert Mask, Opacity), the 5.1 keys, the Property Panel's Blur section. Tests: a pixel check per mode over a raster below, the ellipse clip, the feather, the invert, the cache invalidating, the round trip, the bar.
2. **The freeform region and Whole Layer.** Per decision 4: the brush-painted alpha mask of 2.3 and 2.8, or a recorded deferral.
3. **Phase close-out.** As Phase 1's.

### Close-out of the work

Basic Shape PRD, Blur PRD, General UI PRD, and Technical Architecture PRD rows for what was built and where it departs; the notes complete; the General UI notes' Section 6 bullet on the per-tool bar contents closed with a Section 22 pointer; the Vector Item Properties notes' Section 8 pointer updated; the next required step stated.

## Decisions to surface

Apply the two-part test from the global guidance. Four decisions are expected to pass it; present all four with the consequential decision template before Phase 1 step 2 and wait.

- **1. Where point editing lives.** Every shape's point-editing mode (3.5, 4.5, 4.6, 7.5, 8.5, 9.7) is entered by a double-click on a selected item and shows control-point handles. Option A, a mode of the Select tool beside its transform handles, with the handles drawn in the view's foreground pass as the transform handles are, one `PointEditSession` object per item type that knows its handles and the command each drag pushes: the callout's tail handle joins it later; its cost is the Select tool growing a second state machine. Option B, a `PointEditTool` of its own, activated by the double-click and left by Escape, with its own bar: cleaner separation; its cost is a tool the palette does not show and the tool-switch machinery (creation defaults, presets) treating it as a tool. Recommendation: A; the double-click already belongs to the Select tool, and the handles are a drawing concern of the view.
- **2. What the Freehand item stores.** Section 10.7 stores both `path_points` and `bezier_segments`. Option A, both, with re-smoothing from the raw points (9.7) and the Bezier path drawn: the PRD as written; its cost is twice the data per stroke and a fitting algorithm to write and test. Option B, the raw points and the smoothing value only, the Bezier fit computed on load and after every change: smaller files; its cost is the fit's cost on every load and no way to hand-edit a segment that survives a re-fit. Option C, keep today's simplified polyline and add Close Path and the cap toggles only: smallest; its cost is 9.3's Bezier stage and 9.7's Bezier handles unmet. Recommendation: A; the PRD's storage model is the one point editing needs.
- **3. The tool count and the shortcuts.** Arc (Shift+A) and Polygon (G) are listed by General UI PRD 3.7 and were never registered; the palette count is nineteen. Option A, register both as tools twenty and twenty-one with the PRD's shortcuts, the palette count changing in every test that asserts it; option B, one Shapes tool with a mode dropdown for Arc and Polygon: fewer palette buttons; its cost is a departure from 3.7's table and the shortcuts. Recommendation: A.
- **4. How far the Blur tool goes.** Section 2 has three modes, four shapes, the invert, feathering, source modes, and a background-thread render for large regions. Option A, the three modes over the rectangle and ellipse shapes with feathering, invert, opacity, and the cache, rendered on the main thread, and the freeform brush mask and Whole Layer deferred with a row; its cost is 2.3's brush, 2.4's freeform and whole-layer rows, and the source modes of 2.5 recorded as not built. Option B, everything in Section 2 including the brush mask, its editing, and the thread: its cost is the mask's own editing mode and the first thread in the code. Recommendation: A; the blur that hides an address is the essential privacy tool, and the brush is a kickoff of its own once the capture pipeline exists.

Everything else follows the PRDs; where they are silent or disagree, decide, note it under the notes' decisions section and the PRD rows, and continue. Silences known now:

- The arrowhead on a curve orients along the tangent at the endpoint (4.5); `head_paths` takes a direction per end.
- The `ModifyGeometryCommand` of 11.3 is one class in `snapmock/commands/` (a Section 10 row) with the 300 ms merge; `InsertVertexCommand` and `RemoveVertexCommand` sit beside it.
- The Blur tool's capture of "the content beneath" is every visible layer below the item's layer plus the items below it on its own layer, rendered through `RenderEngine` at the canvas scale; the cache key is the region, the properties, and a revision counter the scene bumps on any change to a lower layer.
- The Section 2.4 Whole Layer shape and the 2.5 source modes wait with the freeform brush (decision 4, option A).
- The Snagit writer maps a Blur region to Snagit's blur object if one exists in the sample files, else skips it with the warning; a Snagit notes row either way.
- The Arc's and Polygon's glyphs come from the vendored Tabler subset (`circle-half`, `polygon`, or the nearest); a glyph added to the subset is recorded in the icons README.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- Every new module gets a row in Technical Architecture PRD Section 10 in the commit that creates it: `items/arc_item.py`, `items/polygon_item.py`, `tools/arc_tool.py`, `tools/polygon_tool.py`, the geometry command module, and any point-editing module are expected.
- Departures from any PRD are recorded in that PRD's change log with a version bump, not only in code comments.
- No control is disabled (General UI PRD 1.3); a control whose requirement is unmet says which, through `check_requirements`.
- Every new control gets an accessible name as it is created, and `tests/test_accessibility.py`'s audit passes over every new surface.
- Every walk over the scene's items that a new item type joins is checked against the General UI notes' Section 17.2 table.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- Document timestamps are read from the machine clock at the time of writing, never estimated.
- Commit messages end with the attribution block the session provides.

## When the work is complete

Update the phase table in `docs/Basic-Shape-Remainder-Implementation.md`, bump its revision, add a change-log row, and state the next required step. Two candidates are known: the freeform blur brush and the Highlighter's straightening (Blur PRD 2.3, 2.8, 3.3), which have no kickoff prompt yet, and the Windows backend kickoff (`docs/Windows-Backend-Kickoff-Prompt.md`), which waits for a Windows machine.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-11-26 14:21 | Claude (Claude Code) | Initial kickoff prompt, written by the Vector Item Properties close-out: the Basic Shape PRD's remainder (point editing, curved and elbow arrows, individual corner radii, the Freehand pipeline, the Arc and Polygon tools) and the Blur tool's modes; starting state at commit ab71e15; five phases and a close-out; four decisions; six silences. |
