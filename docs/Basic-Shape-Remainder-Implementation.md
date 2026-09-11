# Basic Shape Remainder and Blur Modes Implementation Notes

Last Updated: 09-11-26 17:41 · Revision 1.2

Implements the remainder of the Basic Shape Annotation Tools PRD (`PRDs/SnapMock-Basic-Shape-Annotation-Tools-PRD.html`, version 1.8 at the start) and the Blur / Pixelate tool of the Blur, Highlighter, and Eyedropper Tools PRD (version 1.4), with the General UI PRD (version 2.16) and Technical Architecture PRD (version 1.28) rows they own, in the five phases and the close-out defined by `docs/Basic-Shape-Remainder-Kickoff-Prompt.md` (revision 1.0). A session pasting that prompt starts at the first phase not marked done in Section 1. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) governs the standards; the General UI implementation notes (`docs/General-UI-Implementation.md`) hold the walk table of Section 17.2.

Starting state, verified at commit 8a9ce6b on 09-11-26 (the kickoff names ab71e15; 8a9ce6b adds only the Vector Item Properties close-out documents and the kickoff prompt): every vector item carries the shared stroke, fill, opacity, shadow, and blend properties; the Arrow draws its heads on a straight shaft and stores `line_style` without drawing it; the Rectangle has the uniform Corner Radius; the Freehand tool simplifies the raw points on release and stores the simplified polyline under `points`; the palette has nineteen tools; `BlurItem` paints a grey placeholder and `BlurTool` has no options. The suite at ab71e15 ran 1272 tests with 13 skipped and one environmental deselection: 1258 passed; ruff and mypy are clean.

## 1. Phase status

| Phase | Scope | Status | Commits |
|---|---|---|---|
| 1 | Point editing and the arrow's lines (Basic Shape PRD 3.5, 4.5, 4.6, 4.7, 11.3): the decisions, the point-editing mode, curved and elbow arrows, close-out | Done | 177f69b, 1f23a37, ba4320e, then this close-out commit |
| 2 | The Rectangle's corners and the Freehand pipeline (5.3, 5.4, 9.3, 9.6 to 9.9): individual corner radii, the Freehand pipeline, Freehand point editing, close-out | Done | 405f637, ad1f6b6, 661371e, then this close-out commit |
| 3 | The Arc tool (Section 7): `ArcItem` and the tool, Arc point editing, close-out | Not started | |
| 4 | The Polygon tool (Section 8): `PolygonItem` and the tool, Polygon point editing, close-out | Not started | |
| 5 | The Blur tool's modes (Blur PRD Section 2): the capture and the three modes, the freeform region and Whole Layer deferral, close-out | Not started | |
| Close-out | PRD rows, the General UI notes' pointer, the Vector Item Properties notes' pointer | Not started | |

## 2. Decisions

### 2.1 Taken at the start of Phase 1 (09-11-26)

Presented with the consequential decision template and chosen by Doug on 09-11-26: the recommendation in every case ("use your recommendations for all decisions").

| Decision | Choice | Effect |
|---|---|---|
| 1 Where point editing lives | A, a mode of the Select tool | A double-click on a line, an arrow, an arc, a polygon, or a freehand item with the Select tool selects it and enters point-editing mode. The transform handles hide; the item's control points show as scene items above every annotation item, the way `TransformHandles` already are. Each item type has one point-edit session class in the new module `snapmock/tools/point_edit.py` (a Technical Architecture PRD Section 10 row): the session knows its handles in scene coordinates, applies a drag with its modifiers, and builds the command the drag pushes. Escape, a click away from the item and its handles, a tool switch, or a selection change leaves the mode. The status bar shows the item's point-editing hint while the mode lasts. The cost: the Select tool gains a second state machine. The alternative, option B, a hidden `PointEditTool`, would have needed exclusion from the presets, the themes, the palette count, and the tool-switch machinery. |
| 2 What the Freehand item stores | A, both the raw points and the fitted segments | `FreehandItem` stores `path_points` (the raw sampled points), `bezier_segments` (cubic segments of start, cp1, cp2, end), `smoothing` (0.0 to 1.0), `is_closed`, and `pressure_data` (always null) under the 10.7 keys, and paints the segments. The two-stage pipeline of 9.3 runs on release: Ramer-Douglas-Peucker simplification at a tolerance of smoothing times 5 px, then least-squares cubic Bezier fitting at an error of smoothing times 3 px. Moving the Smoothing slider with freehand items selected re-smooths each from its `path_points` as one undoable change; a hand edit of the segments is replaced by a re-smooth, since the re-smooth starts from the raw points. The cost: about twice the data per stroke, and the fitting algorithm to write and test. The alternatives: option B, the raw points only with the fit recomputed on every load, where a hand-edited segment could not survive; option C, the simplified polyline kept, leaving 9.3's second stage and 9.7's handles unmet. |
| 3 The tool count and the shortcuts | A, two tools, Arc on Shift+A | The Arc tool (`arc`, Arc, Shift+A) and the Polygon tool (`polygon`, Polygon, G) are registered as the twentieth and twenty-first tools, after the Line tool in the palette and in the Tools menu's shape group. Shift+A is the Basic Shape PRD's key (7.1); General UI PRD 3.7 lists O, and its Arc row is corrected by a General UI PRD row, since each tool's own PRD owns its details (the marker work's silence 1; the Emoji tool's Shift+E came the same way). The palette count changes from nineteen to twenty-one in the three tests that assert it. The cost: Arc needs two keys, and 3.7 carries a correction. The alternatives: Arc on O with the Basic Shape PRD corrected; one Shapes tool with a mode dropdown, departing from 3.7's table. |
| 4 How far the Blur tool goes | A, three modes over two shapes, on the main thread | `BlurItem` gains the Gaussian, Pixelate, and Solid Fill modes over the Rectangle and Ellipse region shapes, with `corner_radius`, `feather`, `invert_mask`, the item's opacity, `border_color`, and `border_width`, a cached render, and the 2.6 bar. The brush-painted freeform region of 2.3 and 2.8, the Freeform and Whole Layer shapes of 2.4, `brush_size`, `alpha_mask`, the source modes of 2.5, and the background-thread render and progress indicator of the Performance section are recorded as not built; a file carrying `freeform` or `whole_layer` reads as a rectangle. The cost: those rows open, and a region larger than 500 by 500 px may miss the 100 ms render target. The alternative, option B, all of Section 2 with the mask's own editing mode and the first thread in the code. |

### 2.2 The kickoff's six silences

Each decided as the kickoff recommended, on 09-11-26, with the detail the reading added.

| Silence | Decision |
|---|---|
| The arrowhead on a curve | Oriented along the tangent at the endpoint (4.5): toward the end point from the control point for a curve, along the terminal segment for an elbow. `head_paths` takes a direction per end. |
| The geometry commands | `ModifyGeometryCommand` (11.3) in the new module `snapmock/commands/geometry_commands.py` (a Section 10 row), merging drags of the same property on the same item within 300 ms; `InsertVertexCommand` and `RemoveVertexCommand` (11.4, 11.5) beside it. A line's endpoint drag pushes `ModifyGeometryCommand`, not the `ModifyPropertyCommand` that 3.5 names, since 11.3 is the section on point edits. |
| What the blur captures | Every visible item stacked below the blur item, which is every item of the lower layers plus the lower items of its own layer, painted into an image over the region at the canvas scale with the canvas colour first. The items are painted directly with their scene transforms and effective opacity by a new `RenderEngine` method, not through `QGraphicsScene.render` with visibility toggles as the thumbnails are: a scene render from inside the blur item's paint would draw the blur item itself, and a visibility toggle schedules another paint. The cache key is the region, the properties, the item's scene transform, and a revision counter the scene bumps on every command push, undo, and redo and on every layer change. |
| Whole Layer and the source modes | Wait with the freeform brush (decision 4). |
| The Snagit writer | Skips a blur region with its warning, as today. Verified 09-11-26: the 239 sample files carry the tool modes Text, Callout, Image, Highlight, Shape, Arrow, Line, and Stamp, and no blur object. A Snagit notes row at the close-out. |
| The Arc and Polygon glyphs | From the vendored Tabler subset; a glyph added to the subset is recorded in the icons README. |

### 2.3 Corrections to the kickoff, found in the reading

- General UI PRD 3.7 lists Arc under O, not Shift+A; only the Basic Shape PRD (7.1) gives Shift+A. Settled by decision 3.
- The transform handles are scene items (`TransformHandles`, a `QGraphicsItemGroup` at z 999997), not drawn in the view's foreground pass; only the grid, the guides, the crosshairs, and the layer hover outline are. The point-editing handles follow the transform handles.
- No callout tail handle exists in the Select tool: `MoveTailCommand` has no caller, and a callout's tail moves only with a resize. Decision 1's "joins it later" has nothing to join; nothing is built for it here.
- A third test asserts the palette count: `tests/test_tools/test_emoji_tool.py::test_emoji_is_the_nineteenth_tool_after_stamp_with_shift_e`, beside the two the kickoff names.

### 2.4 Findings decided with the decisions

- The Line and Arrow tools show "Shift: constrain angle" and do not read Shift while drawing. Point editing needs the same 15-degree snap, so Phase 1 step 2 builds one helper and both tools use it while drawing (Basic Shape PRD 3.2, a row).
- A closed freehand stroke fills (9.8), and 9.6 adds its controls to the shared set of 2.6, which includes Fill Color and Fill Opacity; the Vector Item Properties work left them off the Freehand bar because the item drew no fill. The Freehand bar gains both with Close Path (Phase 2 step 2).
- Files saved before Phase 2 store the already-simplified polyline under `points`. They load with those points as `path_points` and are fitted on load at their stored smoothing, 0.5 when absent.
- The Freehand tool's Smoothing creation default stays the slider's whole percent, 0 to 100, as presets and themes already store it; the item stores the 0.0 to 1.0 fraction of 10.7. The Ramer-Douglas-Peucker tolerance at 100 percent becomes 9.3's 5 px, where the shipped `MAX_SMOOTHING_EPSILON` was 6 px (a Basic Shape PRD row).
- The PRD's class name `BlurRegionItem` stays `BlurItem` in the code and in `items.json`, as every file saved so far names it.

## 3. What Phase 1 built

In commit order. Step 1, 177f69b: the decisions of Section 2; Basic Shape PRD 1.9, Blur PRD 1.5, General UI PRD 2.17, Technical Architecture PRD 1.29. Step 2, 1f23a37: `snapmock/tools/point_edit.py` (`HandleKind` with the diameters of 3.5, 4.5, and 9.7; `PointHandle`; `PointEditSession` with scene and local coordinates through the item's flips, `handle_at`, `begin_drag`, `cancel_drag`, `end_drag`; `LinePointSession` and `ArrowPointSession`; `session_for`; `PointHandlesItem`, a scene item at z 999998 drawing the handles and dashed guides) and `snapmock/commands/geometry_commands.py` (`ModifyGeometryCommand`, `copy_geometry`, `shape_name`), each with its Technical Architecture PRD Section 10 row; the Select tool's point-editing mode (double-click entry, the handle drag state, the exits, the handles following undo and redo through the command stack's signal); Edit > Deselect's Escape leaving the mode first; `constrain_angle` in `core/path_utils.py`, used by point drags and now by the Line and Arrow tools while Shift is held. Step 3, ba4320e: curved and elbow arrows in `ArrowItem` (`control_point`, `bend_point`, `effective_control_point`, `bend_x`, `bend_handle_point`, `elbow_points`, `end_directions`, `line_path` in the line style, `head_paths` returning the shaft as a path trimmed at a filled head's base along the curve or the segments, the 10.2 keys); the Line Style toggles of 4.7 in the Arrow bar with `line_style_icon` and the `line_style` creation default; `LineStyle` in the preset codec; the Line style row of the Property Panel's Arrow section; the control point and bend point handles in `ArrowPointSession` with the 4.8 hints per style. Step 4, this commit: Basic Shape PRD 1.10, General UI PRD 2.18, Technical Architecture PRD 1.30, Snagit notes 1.4, these notes.

Silences found while building, decided as the code says and recorded as PRD rows:

- The handles are sized in scene pixels, as the transform handles are, so they grow with the zoom; a press within 3 px of a handle's edge grabs it; the topmost handle wins where two overlap.
- A press on the item keeps point-editing mode, so a missed handle does not end it; a press elsewhere leaves the mode and acts as a normal press.
- A point drag snaps to the grid and the guides as a move does, unless Shift is held, when the 15-degree constraint wins.
- A flipped item's handles are mirrored where the item paints them.
- The mode also ends when the item leaves the scene (Delete, or an undo of its creation) and on a tool switch.
- A curved arrow with no `control_point` curves through the midpoint, so switching a straight arrow to Curved changes nothing until the green point moves; switching the style keeps the stored points.
- An elbow is horizontal, vertical, horizontal; its bend point stores the middle y and moves across only; when the bend meets an end's x, the first or last segment vanishes and two remain.
- A curved arrow's shaft ends where the curve meets a filled head's reach measured in a straight line from the tip.
- The new arrow keys use 10.2's `{"x", "y"}` form while `line` keeps its list form.
- The Snagit writer writes a curved or elbow arrow as its straight line (Snagit notes 1.4).

## 4. What Phase 2 built

In commit order, built while the Phase 1 suite ran and committed after the Phase 1 close-out. Step 1, 405f637: the individual corner radii (`CornerRadiusMode` and `CORNER_KEYS` in `config/constants.py`; `RectangleItem`'s four radii stored as set and drawn clamped with one `arcTo` per corner; the Individual toggle and four spin boxes of the Rectangle bar through `ToolOptionsBar.set_control_visible`; the Property Panel's Individual corners check box and four rows; the codec). Step 2, ad1f6b6: the Freehand pipeline (`fit_cubic_beziers` and the iterative `simplify_rdp` in `core/path_utils.py`; `FreehandItem`'s `path_points`, `bezier_segments`, `smoothing`, `smoothing_fit`, and `is_closed` under the 10.7 keys; the Freehand bar with the fill controls, the Stroke Cap toggles, and Close Path; the Property Panel's Freehand section; `ResizeImageCommand`'s restore). Step 3, 661371e: Freehand point editing (`FreehandPointSession` and `split_cubic`; the Select tool's double-click insertion and right-click deletion routes; Alt kept from the momentary eyedropper). Step 4, this commit: Basic Shape PRD 1.11, General UI PRD 2.19, Technical Architecture PRD 1.31, these notes.

Silences found while building, decided as the code says and recorded as PRD rows:

- Switching a rectangle to Individual while its four radii are all zero starts them from the uniform radius, so it keeps its look; radii already set are never overwritten.
- In Individual mode the bar hides the Corner Radius slider with its label, and the Property Panel hides the Corner radius row.
- Both stages of the Freehand pipeline have a 0.5 px floor, and the fit and the simplification are iterative, so no stroke exhausts the recursion limit.
- Re-smoothing a placed stroke is done from the Property Panel's Freehand section, since the bar edits creation defaults only; one command restores the smoothing and the segments together, a hand edit included.
- A stroke is an accidental click when its points span under 2 px both across and down, so a straight underline is kept.
- Dragging an on-curve point carries its two handles; dragging a handle turns the opposite handle in line at its own length; Alt breaks either link; a right-click on a handle never opens the item menu, even where the two-point minimum refuses the deletion.
- Shift's straight segments (9.5) and the brush-tip cursor (9.2) are not built.

Measured for 5000 raw points on this machine: about 65 to 70 ms at 50 and 100 percent smoothing, and up to 630 ms at 0 percent on a stroke with a pixel of jitter, against the 50 ms of 9.10.

## 5. Deviations from the PRDs

Each has its PRD row.

- General UI PRD 3.7: Arc on Shift+A, not O (decision 3).
- Basic Shape PRD 3.5: a line's endpoint drag pushes `ModifyGeometryCommand` (11.3), not `ModifyPropertyCommand`.
- Basic Shape PRD 9.3: the Smoothing creation default stays a whole percent; the item stores the fraction.
- Blur PRD Section 2: the freeform region, Whole Layer, the source modes, and the background-thread render are not built (decision 4); the item class keeps the name `BlurItem`.
- Basic Shape PRD 9.3 and 9.10: both stages of the Freehand pipeline floor at 0.5 px; a jittery 5000-point stroke fits in up to 630 ms at 0 percent smoothing.
- Basic Shape PRD 9.7: re-smoothing a placed stroke is done from the Property Panel's Freehand section, not the Tool Options Bar.
- Basic Shape PRD 9.1: a stroke is an accidental click when its points span under 2 px both across and down, not when its bounding box is under 4 square pixels.

## 6. Tests

Phase 1: `tests/test_point_edit.py` (13: entering by double-click with the handles, the transform handles hidden, and the hint; an item without points not entering; a drag as one undoable geometry edit with the handles following undo; the Shift constraint; the 300 ms merge by point; Escape, a click away, and a new selection leaving; deleting the item leaving; the window's Escape keeping the selection; the arrow's endpoints; a flipped line's handles; `constrain_angle`; both drawing tools under Shift) and `tests/test_arrow_lines.py` (9: the curve through its control point by pixels and hit shape; the heads along the tangent with the shaft ending at the filled base; the elbow's right angles and its two-segment case; the keys' round trip, old files, the list form, and scaling; the control point and bend point drags with undo and hints; the bar's toggles reaching the next arrow; the panel row with undo). The two shaft assertions of `tests/test_arrow_heads.py` read the path. The full suite at the Phase 1 code commit (ba4320e), run from a scratch worktree while the Phase 2 work's targeted runs shared the machine, ran 1293 tests with 13 skipped and the one environmental deselection: 1279 passed and one failed, the pre-existing timing-sensitive Zoom tool test (`tests/test_tools/test_zoom_tool.py::test_left_click_zooms_in_and_alt_at_the_release_zooms_out`), which passes alone at that commit; the run took 48 minutes. Ruff and mypy are clean at every commit; the accessibility audit passes over the Arrow bar's toggles and the new panel row.

Phase 2: `tests/test_corner_radii.py` (8), `tests/test_freehand_pipeline.py` (10), `tests/test_freehand_point_edit.py` (7); the Freehand smoothing test of `tests/test_tool_options_bar.py`, the scale test of `tests/test_transform_resize.py`, and the Freehand bar order of `tests/test_vector_bar_presets.py` moved with the work. The full suite at the Phase 2 code commit (661371e), run from a scratch worktree while the Phase 3 to 5 work's targeted runs shared the machine, ran 1318 tests with 13 skipped and the one environmental deselection: 1304 passed and one failed, the pre-existing timing-sensitive Zoom tool test, which passes alone at that commit; the run took 50 minutes. Ruff and mypy are clean at every commit; the accessibility audit passes over the Rectangle and Freehand bars' new controls and the two new panel sections.

**Next required step:** Phase 3, the Arc tool: built with Phases 4 and 5 while the Phase 2 suite ran, committed at 867a763 and 58d40a0; its close-out follows one full-suite run at the last code commit.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.2 | 09-11-26 17:41 | Claude (Claude Code) | Phase 2 done: the phase table, the Phase 2 section (what it built, the silences found while building, the Freehand timings), three deviations added, the Phase 2 tests and the suite run, the next required step. Basic Shape PRD 1.11, General UI PRD 2.19, Technical Architecture PRD 1.31. |
| 1.1 | 09-11-26 16:45 | Claude (Claude Code) | Phase 1 done: the phase table, Section 3 (what Phase 1 built, the silences found while building), Sections 4 and 5 renumbered, Section 5 with the Phase 1 tests and the suite run, the next required step. Basic Shape PRD 1.10, General UI PRD 2.18, Technical Architecture PRD 1.30, Snagit notes 1.4. |
| 1.0 | 09-11-26 15:38 | Claude (Claude Code) | Initial notes: the starting state, the phase table, the four decisions (1 A, 2 A, 3 A with Arc on Shift+A, 4 A) and the kickoff's six silences as chosen 09-11-26, four corrections to the kickoff, five findings decided with the decisions, the deviations they imply, the next required step. Basic Shape PRD 1.9, Blur PRD 1.5, General UI PRD 2.17, Technical Architecture PRD 1.29. |
