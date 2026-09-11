# Vector Item Properties Implementation Notes

Last Updated: 09-11-26 11:13 · Revision 1.0

Implements the shared vector item properties that General UI Phase 6 decision 6.2 named and deferred (Stroke Style, Fill Opacity, Stroke Opacity, the Shadow section, Blend Mode, and Line Spacing), from the Basic Shape Annotation Tools PRD (`PRDs/SnapMock-Basic-Shape-Annotation-Tools-PRD.html`, version 1.5 at the start), the Text and Callout Annotation Tools PRD (version 1.6), the Blur, Highlighter, and Eyedropper Tools PRD (version 1.3), the General UI PRD (version 2.12), and the Technical Architecture PRD (version 1.24), in the three phases and the close-out defined by `docs/Vector-Item-Properties-Kickoff-Prompt.md` (revision 1.0). A session pasting that prompt starts at the first phase not marked done in Section 1. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) governs the standards; the General UI implementation notes (`docs/General-UI-Implementation.md`) hold the walk table of Section 17.2, which this work does not expect to extend.

Starting state, verified at commit 57bdbd6 on 09-11-26 (the kickoff names c1c35c5; 57bdbd6 adds only the kickoff prompt and the marker notes 1.4 pointer): `VectorItem` carries `stroke_color`, `stroke_width`, `fill_color`, and the base class's one `opacity`; `ShadowMixin` is mixed into the three marker items only; `NumberedStepItem` alone carries `fill_opacity` and `stroke_opacity`; `TextItem` and `CalloutItem` sit beside `VectorItem` with their own background and border properties; the Highlighter paints its own round-capped pen with no composition mode; the Arrow draws one filled triangle; the Rectangle's `corner_radius` has no control. The suite at the last code commit (12aad72) ran 1191 tests with 13 skipped and one environmental deselection; ruff and mypy are clean.

## 1. Phase status

| Phase | Scope | Status | Commits |
|---|---|---|---|
| 1 | The shared properties (Basic Shape PRD 2.2, 2.6; Technical Architecture PRD 4.3): the decisions, `VectorItem` and the items, the text items, the Tool Options Bar and presets, the Property Panel, close-out | In progress | this commit (step 1) |
| 2 | Blend mode and line spacing (Blur PRD 3.4 to 3.7; Text PRD 2.2; General UI PRD 8.3, 8.4): the Highlighter, the item blend mode, line spacing, close-out | Not started | |
| 3 | The per-tool controls (Basic Shape PRD 4.3, 4.4, 4.7, 5.3, 5.4): arrowheads, corner radius, close-out | Not started | |

## 2. Decisions

### 2.1 Taken at the start of Phase 1 (09-11-26)

Presented with the consequential decision template and chosen by Doug on 09-11-26: the recommendation in every case.

| Decision | Choice | Effect |
|---|---|---|
| 1 Where the shared properties live for the text items | B, mixed in beside `VectorItem` | `TextItem` and `CalloutItem` stay `RichTextMixin, SnapGraphicsItem` and mix in `ShadowMixin` and the two opacities directly, as the stamp and emoji items do. The shadow is drawn first, under the text box's frame and under the callout's combined bubble and tail path (the bubble plus its tail circles for the cloud shape), with the Basic Shape PRD's defaults (`#00000080`, offset 3 and 3, blur 5). The background is the fill for `fill_opacity` and the border is the stroke for `stroke_opacity`; their `border_style` keeps its name. The Property Panel's Appearance section stays hidden for text items; the Text Box section gains Fill Opacity and Stroke Opacity rows and keeps Background and Border; the Shadow section shows for them. The Text tool's and the Callout tool's Tool Options Bars gain Border Style (Text PRD 3.5, 4.6). Technical Architecture PRD 4.2 gains a row saying the two text items sit beside `VectorItem` rather than under it; Text PRD 3.6's "Transform, Appearance, Shadow, and Text sections" is departed from on Appearance. The cost: "vector item" means the class and the property set, and a text box's opacities live in a different section from a rectangle's. The alternatives: option A, the class move (background to fill, border to stroke, every text and callout test, the Snagit field names, old files' keys read as fallbacks) for what is a naming change; option C, defer, which would leave the Text PRD's 3.6 and 8.3 rows unmet. |
| 2 What the vector items' Opacity control becomes | A, replace | Vector items and their tools expose `fill_opacity` and `stroke_opacity` and no `opacity_pct`; the Appearance section shows the two sliders for a vector selection and the one slider for a non-vector selection; a stored preset, theme, or session state carrying `opacity_pct` for a shape tool is read once into both new keys, when neither is present, and dropped on the next write; the base `opacity` stays as a Qt property for groups, non-vector items, and the layer machinery. A selection that holds a group shows the single Opacity slider for the group's own opacity beside the two sliders acting on its vector members, so nothing loses a control. The Snagit writer keeps writing the base opacity (kickoff silence 10), which is 100 for a shape from now on. The cost: the migration rule and a saved preset whose meaning changes from one number to two. The alternative, option B, three opacity controls on every shape and the numbered step's deviation made permanent. |
| 3 How far into the Basic Shape tools this kickoff goes | B, Phases 1 to 3 as written | Arrowheads on straight lines (head and tail styles, the four sizes and the custom size; Basic Shape PRD 4.3, 4.4, 4.7) and the uniform Corner Radius control (5.4) are Phase 3. `line_style` stays Straight; curved and elbow arrows (4.5, 4.6), `corner_radius_mode` and the individual radii (5.3), point editing, the Arc and Polygon tools, and the Freehand tool's Bezier fitting and Close Path are the following kickoff's, named at the close-out. `head_style` defaults to Open per 4.3, which changes the look of every new arrow from today's filled triangle; a file saved before Phase 3 loads its arrows with the filled style, so nothing on disk changes appearance. The cost: a third phase of geometry work, and 4.5, 4.6, and 5.3 recorded as partly built. The alternatives: option A, the shared properties only, leaving the Arrow with one fixed head; option C, the whole PRD, two new tools and point editing on every shape in one notes document. |
| 4 Whether the item blend mode is built for every item or the Highlighter alone | A, every item | `blend_mode` on `SnapGraphicsItem` for every item, serialized as a string and read as Normal when absent; the Appearance section's Blend Mode dropdown lists the layer's seven names plus Soft Light, which the Highlighter needs (Blur PRD 3.4) and the layer list lacks; `composition_mode` in `core/layer.py` gains Soft Light. The combination rule, recorded in Technical Architecture PRD 3.9: the item's mode is applied as the painter composition mode when the layer's is Normal, the layer's otherwise, one composition mode per paint. The Highlighter's default is Multiply and the shadow is painted before the mode is set (Blur PRD 3.7). The SVG export drops the mode for every item, as it drops the layer's. The cost: the rule, a key on every item, and the export row. The alternative, option B, the Highlighter alone, with 3.1.4 and 8.3 departed from for every other item. |

### 2.2 The kickoff's twelve silences

Each decided as the kickoff recommended, on 09-11-26.

| Silence | Decision |
|---|---|
| `stroke_style` and `border_style` | One enum, `BorderStyle` in `config/constants.py`; `VectorItem.stroke_style` holds it under the key `stroke_style`; the text items keep the `border_style` name and key. |
| The shadow defaults | Each PRD's own: the Basic Shape PRD's (`#00000080`, offset 3 and 3, blur 5) for the shapes and the text items; the marker PRD's for the three marker items. `_init_shadow` takes the defaults as arguments and `constants.py` gains the vector set beside the marker set. |
| The stroke cap and join | `stroke_cap` Round and `stroke_join` Round by default for every vector item except the Highlighter (Flat cap); `pen()` applies them; the arrowhead's Open style keeps a round cap. No bar control for cap or join except the Highlighter's Cap Style toggles (Phase 2) and the Freehand's Stroke Cap toggles (9.6); no Property Panel row for either (not in General UI PRD 8.3). |
| The two opacities and `hit_shape` | A fill with `fill_opacity` 0 is still a fill for hit testing; `hit_shape` keys on `fill_color.alpha()` as today. |
| The preset migration of decision 2 | `decode_values` maps a shape tool's `opacity_pct` to `fill_opacity` and `stroke_opacity` (the same fraction) when neither new key is present, once, on read; `PREFERENCE_KEYS` unchanged. |
| The Highlighter's opacity | `highlight_color`'s alpha is primary (Blur PRD 3.7); the Highlighter tool's bar drops `opacity_pct` with the others and its `stroke_color` is the highlight colour; the tool's controls become Highlight Color, Stroke Width, Blend Mode, Cap Style, Stroke Style, and the preset colour row (Phase 2). |
| Auto-Straighten and Snap to Axis | Not shown: `HighlightTool` does not straighten strokes today (verified at c1c35c5), and a control with nothing behind it cannot be greyed out (General UI PRD 1.3). A Blur PRD row records that the behaviour belongs to a Highlighter kickoff. |
| Line Spacing's command | While editing, the paragraph at the cursor through the editor's `QTextCursor` as a `TextFormatCommand` merge boundary; otherwise every paragraph of the selected items through `set_line_height` as one `ModifyPropertyCommand`-shaped command per item (`line_spacing` as a whole-document property: the value shown is the first paragraph's, mixed when paragraphs differ). |
| The SVG export | Shadows land as raster images inside the SVG and composition modes are dropped, as the marker work recorded; one row per PRD, no new mechanism. |
| The Snagit writer | `stroke_style`, the opacities, and the shadow are not mapped; a Snagit notes row. |
| The item blend mode's combination rule | The item's mode when the layer's is Normal, the layer's otherwise; Technical Architecture PRD 3.9. |
| Groups | A group has no properties of its own; Appearance and Shadow for a selected group act on its vector members (`_selected_vectors`) and on its shadow-carrying members (`_selected_shadowed` expanding groups), with the 8.6 mixed indicators. |

### 2.3 Findings from the read list, decided with the decisions

- The Highlighter tool's creation default for colour is the shared red stroke default (`#FF0000`) at full opacity, so a new highlight today is an opaque red stroke; the Blur PRD's 3.4 default is `#FFFF00CC` (yellow at 80 percent) and the item's own constructor default is yellow at 50 percent. Phase 2 step 1 sets the tool's default to the PRD's value and records the fix as a Blur PRD row.
- Soft Light is a Highlighter blend mode (Blur PRD 3.4) and not one of the layer's seven names (General UI PRD 7.4); decision 4 adds it to the item's list and to `composition_mode`.
- A group is neither a vector item nor a non-vector item under decision 2's rule; the follow-on detail in the decision table keeps the group's own Opacity slider beside the two.

## 3. What Phase 1 built

Step 1, this commit: the decisions of Section 2; Basic Shape PRD 1.6; Text and Callout PRD 1.7; General UI PRD 2.13; Technical Architecture PRD 1.25.

## 4. Deviations from the PRDs

Each has its PRD row.

- `TextItem` and `CalloutItem` sit beside `VectorItem`, not under it (decision 1; Technical Architecture PRD 4.2), and the Property Panel's Appearance section does not show for them (Text PRD 3.6): their fill and stroke opacities are rows of the Text Box section.
- The Blend Mode dropdown lists eight names (the layer's seven plus Soft Light), not the Technical Architecture PRD 3.1.4 example list (decision 4).
- The shadow offset is two floats, `shadow_offset_x` and `shadow_offset_y` (Basic Shape PRD 2.2), not the `QPointF` of Technical Architecture PRD 4.3, as the marker work already built it.

## 5. Tests

None yet; step 1 changes documents only.

**Next required step:** Phase 1 step 2, `VectorItem` and the items: `stroke_style`, `stroke_cap`, `stroke_join`, `fill_opacity`, `stroke_opacity`, and the shadow on `VectorItem`, adopted by the six shape items with the numbered step dropping its own copies; the tests the kickoff lists.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-11-26 11:13 | Claude (Claude Code) | Initial notes: the starting state, the phase table, the four decisions (1 B, 2 A, 3 B, 4 A) and the twelve silences as chosen 09-11-26, three findings from the read list, the deviations they imply, the next required step. Basic Shape PRD 1.6, Text and Callout PRD 1.7, General UI PRD 2.13, Technical Architecture PRD 1.25. |
