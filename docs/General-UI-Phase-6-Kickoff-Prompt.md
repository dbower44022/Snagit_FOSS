# Kickoff Prompt: General UI Phase 6, Panels and Colour Picker

Last Updated: 09-09-26 00:05 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory: this work edits `snapmock/main_window.py`, `snapmock/ui/layer_panel.py`, `snapmock/ui/property_panel.py`, `snapmock/ui/color_picker.py`, and the layer model, which every other session touches too.

This prompt is the Phase 6 instance of `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1). That prompt still governs the phases, the standards, and the decision list; this one adds what a session needs to know about the repository as Phase 5 left it, so it does not re-derive the state from the code. Where the two disagree, the general prompt wins and this one is corrected.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Build Phase 6 of the General UI PRD (`PRDs/SnapMock-General-UI-PRD.html`, version 2.1 at the start of this phase; the phase bumps it to 2.2): the Layer Panel of Section 7, the Property Panel's remaining items of Section 8, and the colour picker popover of Section 11.1. Where the PRD is satisfied already, leave the code alone. Where the implementation departs from the PRD, record the departure in the PRD's change log and in `docs/General-UI-Implementation.md`, as `CLAUDE.md` requires.

Phase 6 opens by presenting the two decisions below with the consequential decision template, one at a time, and waits after each. Nothing is built before both are taken.

## Read first, in this order

1. `docs/General-UI-Implementation.md`, revision 1.7: Section 1 says Phases 0 to 5 are done; Sections 2.7, 2.8, 2.10, and 2.11 (the Color Picker entry) are the verified inventory for this phase; Section 6 lists the deviations already recorded, two of which this phase touches (Select All Text batch changes, Preferences rows without a consumer); Section 12 says what Phase 5 built.
2. `PRDs/SnapMock-General-UI-PRD.html`: Sections 7 (Layer Panel), 8 (Property Panel), 10.3 (layer context menu), 11.1 (Color Picker), 1.3 (never-disabled controls), 13 (theming, for the accent, hover, and locked-row colours), 14 (accessibility, for names on the new controls), and 17.5 (acceptance). Then `PRDs/SnapMock-Technical-Architecture-PRD.html` Sections 3.2 (layer data model and the Layer Panel contract), 3.9.1 (display rendering and blend modes), 6.1 (file format; `layers.json` carries every Layer property), and 10, binding since 1.4 and now at 1.10: a new module under `ui/`, `core/`, or `commands/` gets a row in the same commit; a new package or top-level module also bumps the version.
3. The tool PRDs whose item properties the Property Panel shows: `PRDs/SnapMock-Basic-Shape-Annotation-Tools-PRD.html` (stroke style, fill and stroke opacity, shadow, blend mode, corner radius), `PRDs/SnapMock-Text-Callout-Annotation-Tools-PRD.html` (font weight and style, line spacing, background fill), `PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html` (the eyedropper the picker's button activates, and the single Opacity slider for non-vector items). Where a tool PRD places a property elsewhere or defines it differently, the tool PRD wins and the departure is recorded.
4. `snapmock/core/layer.py`, `snapmock/core/layer_manager.py` (signals and mutators), `snapmock/commands/layer_commands.py` (`AddLayerCommand`, `DuplicateLayerCommand`, `RemoveLayerCommand`, `ReorderLayerCommand`, `ChangeLayerPropertyCommand`), `snapmock/core/render_engine.py`, `snapmock/io/project_serializer.py` (the `layers.json` fields), `snapmock/ui/layer_panel.py`, `snapmock/ui/context_menus.py` (`build_layer_panel_context_menu`), `snapmock/ui/property_panel.py` (the six `CollapsibleSection` instances, the tool-defaults mode, `refresh_tool_defaults`, `_notify_defaults_changed`), `snapmock/ui/collapsible_section.py`, `snapmock/ui/color_picker.py` and its six consumers (`find_replace_color_dialog.py`, `item_properties_dialog.py`, `preferences_dialog.py`, `property_panel.py`, `tool_options_bar.py`), `snapmock/items/base_item.py` and `snapmock/items/vector_item.py` (the properties that exist), `snapmock/tools/eyedropper_tool.py` (`set_pick_callback`, `pick_serial`), `snapmock/ui/icons.py`, `snapmock/ui/unmet_requirements.py`, `snapmock/config/settings.py` (`thumbnail_delay_ms`, `confirm_delete_layers`), `snapmock/main_window.py` (`_setup_layer_menu`, `_layer_delete`, `_layer_merge_down`, `_on_layer_lock_changed`, `_on_active_document_changed`, the `LayerPanel.set_manager` and `PropertyPanel.set_scene` calls).
5. `tests/test_property_panel.py`, `tests/test_layer_manager.py`, `tests/test_layer_menu_actions.py`, `tests/test_context_menus.py` (`TestLayerPanelContextMenu`), `tests/test_documents.py` (the panel rebinding on tab switch), `tests/test_preferences_dialog.py` (the ColorPicker uses), `tests/conftest.py`.

Do not write code until all five are read.

## Starting state, verified at commit 120456f on 09-08-26

- `Layer` is a dataclass: `name`, `layer_id`, `visible`, `locked`, `opacity`, `z_base`, `item_ids`. It has no blend mode and no layer type; the "BG" and raster badges of Section 7.5 have nothing to key on. `layers.json` writes exactly those fields; `load_project` reads them with defaults.
- `LayerManager` emits `layer_added`, `layer_removed`, `layers_reordered`, `active_layer_changed`, `layer_visibility_changed`, `layer_lock_changed`, `layer_opacity_changed`, `layer_renamed`. Every mutation the panel makes must go through a command in `commands/layer_commands.py`; `ChangeLayerPropertyCommand` covers visibility, lock, opacity, and name.
- `LayerPanel` is a `QDockWidget` (object name `LayerPanel`) holding a `QListWidget` of names, "+" and "-" buttons with Tabler icons, a context menu built by `build_layer_panel_context_menu`, and active-row tracking. It is rebound per tab through `set_manager`. Nothing of Section 7.2 to 7.5 exists: no row widget, no toggles, no thumbnail, no opacity text, no inline rename, no drag reorder, no Ctrl+click, no bottom action bar beyond the two buttons, no badges, no locked-row dimming, no minimum width.
- Merge Down, Merge Visible, and Flatten All are deferred to a Navigation and Raster Operations follow-up by the Phase 1 decision; their rows check requirements and then say the feature is not available yet. The bottom action bar's Merge Down button reuses that action and inherits the message. Do not build merging here.
- Delete Layer confirms when the layer has items (Preferences > General "Confirm before deleting layers"); Duplicate Layer copies items; Rename Layer is an input dialog, which inline rename replaces (the F2 shortcut stays).
- `PropertyPanel` has Transform, Appearance, Text, Text Box, Item Info, and Canvas sections with persisted collapse state and a tool-defaults mode kept in step with the Tool Options Bar and Preferences through `ToolManager.tool_defaults_changed`. Section 2.8 of the notes lists what is missing. Four of the missing controls (Stroke Style, Fill Opacity, Stroke Opacity, Shadow) and Blend Mode have no item property behind them; the Phase 4 deviation says they arrive with the Basic Shape item work. Line Spacing has no text property either.
- `SnapScene` has a background colour and a canvas size and no DPI; the Technical Architecture PRD's project model names `canvas_dpi` (default 72) but nothing stores it. The Canvas section shows width and height as read-only labels; Resize Canvas is the editing path today.
- `ColorPicker` is a swatch button that opens `QColorDialog` with alpha, plus a "∅" transparent toggle that PRD 1.6 removed in favour of a Transparent swatch inside the popover. It emits `color_changed(QColor)` and has `color`, `allow_transparent`, and `swatch_size` parameters; all six consumers use that surface, so a popover that keeps the same class name and signal replaces the dialog without touching them.
- The eyedropper tool exposes `set_pick_callback` and `pick_serial`; the momentary Alt eyedropper returns to the previous tool and applies the pick to its stroke default. The picker's eyedropper button needs a pick that lands in the picker, not in a tool default.
- Recent and saved colours have no settings keys. `AppSettings` uses `QSettings` with typed accessors; add keys there, never raw `QSettings` elsewhere.
- Layer thumbnails need the thumbnail update delay (`AppSettings.thumbnail_delay_ms`, stored by Phase 3 with no consumer) and a render of one layer's items; `RenderEngine` renders the whole scene or a region, not one layer.
- Hovering a layer row "briefly highlights items belonging to that layer on the canvas (optional, can be disabled in Preferences)": no Preferences row exists for it.
- Slots connected to the process-wide `ThemeManager` must be bound methods of a `QObject`, never lambdas. Avoid Python reference cycles between a widget and its children (`RulerWidget` holds its view weakly for this reason): the garbage collector clears a widget's attributes while Qt is still destroying it.
- Guides live on `SnapScene` and change only through `commands/guide_commands.py`; the Property Panel does not show them.

## Steps, one commit each

1. **Decisions.** Present decision 6.1 (layer blend mode) and then decision 6.2 (item properties without a home) and wait after each.
2. **Layer model.** Whatever decision 6.1 adds to `Layer`: the field, the command, `layers.json` and `load_project`, the Snagit writer's handling if any, the render path, and the Technical Architecture PRD rows in the same commit.
3. **Layer Panel rows.** A row widget per layer: visibility and lock toggles (20 px Tabler eye and lock glyphs, dimmed when hidden), the 40 px thumbnail on a checkerboard rendered from that layer's items and refreshed after the thumbnail delay, the name with ellipsis and inline rename on double-click and on F2, the opacity text with a slider popover, the 48 px row height, the accent highlight for the active row, hover highlight, the 70 percent treatment and lock overlay for locked rows, the 200 px minimum width. Every change through a command.
4. **Layer Panel interactions and action bar.** Drag reorder with the insertion line through `ReorderLayerCommand`; Ctrl+click multi-selection with the batch operations it serves (delete, lock, hide, and merge where merge exists) as one undoable command each; the bottom action bar (New, Delete, Duplicate, Merge Down, blend mode dropdown per decision 6.1) reusing the menu actions and their never-disabled messages; badges per decision 6.1; the hover-highlight-on-canvas behaviour with its Preferences row, or a recorded deferral.
5. **Property Panel.** The chain-link aspect lock; hex inputs beside the stroke and fill swatches; Font Weight and Font Style dropdowns; Background Fill in the Text section; the Canvas section's editable width and height (through the Resize Canvas command), Pasteboard Color, Grid Size, Snap to Grid, and Canvas DPI (decide and record how DPI is stored); mixed-value indicators for every shared control under multi-selection, and one undoable command per change across the selection, which also closes the Select All Text deviation; the controls decision 6.2 admits; Canvas Properties in the canvas context menu opening the Canvas section (closing the Section 2.10 deviation).
6. **Colour picker popover.** `ColorPicker` opens a popover beside the swatch: the 200 px hue and saturation square, hue slider, opacity slider, hex, RGB and HSL inputs, the 12 recent and 12 saved swatches persisted in `AppSettings`, the Transparent swatch, the eyedropper button routed to the eyedropper tool with the pick returned to the picker, live preview through `color_changed`, closing on an outside click. The "∅" toggle goes. All six consumers keep working unchanged.
7. **Close-out.** General UI PRD 2.2 change-log rows; Technical Architecture PRD rows for any new module; `docs/General-UI-Implementation.md` revision 1.8 with the phase table, decisions, deviations, tests, and a "What Phase 6 built" section; the next required step.

Each step is ruff-clean and mypy-strict-clean with the suite passing (`test_main_window_default_size` and `test_font_combo_reflects_text_item_font` are the known environmental failures on this machine; the first passes again since Phase 1 and may be run).

## Decisions to surface

Apply the two-part test from the global guidance. Two decisions are expected to pass it; present each with the consequential decision template before step 2, one at a time, and wait:

- **6.1 Layer blend mode.** Section 7.4's dropdown and Section 7.5's badges need a blend mode and a layer type on `Layer`, which changes `layers.json`, the render engine (offscreen compositing per Technical Architecture 3.9.1), the Snagit writer, and the Technical Architecture PRD's data model. Options: add `blend_mode` (and a derived or stored layer type for the badges) now, with the file-format row; or defer the dropdown and badges to the Navigation and Raster Operations follow-up that already owns merging, with a General UI PRD change-log row, and build the rest of the panel.
- **6.2 Item properties without a home.** Stroke Style, Fill Opacity, Stroke Opacity, the Shadow section, Blend Mode, and Line Spacing have no item property. Options: build the properties in this phase (items, serialization, render, the tool PRDs' change logs), which pulls Basic Shape and Text PRD scope into General UI; or keep the Phase 4 deferral, build every other Property Panel item, and record the six controls as arriving with their tool PRDs' item work.

Everything else follows the PRD; where the PRD is silent, decide, note it under Deviations, and continue. Four silences are known: where Canvas DPI is stored (the scene, the manifest, or not yet); what the Ctrl+click multi-layer selection may do beyond delete, lock, and hide; whether the hover highlight ships with a Preferences row or is deferred; and how the recent-colours list is ordered and de-duplicated.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- Every new module gets a row in Technical Architecture PRD Section 10 in the commit that creates it, and any new package or top-level module also bumps that PRD's version. A change to `layers.json` or the manifest gets a Section 6.1 row and a version bump in the same commit.
- Departures from the General UI PRD are recorded in its change log with a version bump, not only in code comments.
- All mutations go through commands: no panel writes to a `Layer`, an item, or the scene directly.
- No control is disabled (General UI PRD 1.3); every panel button checks its requirements through `check_requirements` and shows the unmet message.
- Every new control gets an accessible name (General UI PRD 14) as it is created; Phase 8 audits, it does not retrofit.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- No new runtime dependency without surfacing it as a decision.
- Commit messages end with the attribution block the session provides.

## When the phase is complete

Update the Phase status table in `docs/General-UI-Implementation.md`, bump its revision, add a change-log row, and state the next required step: Phase 7, Tool themes and presets, in a new session. No kickoff decision is scheduled for Phase 7; the welcome-panel card (kickoff decision 5) waits for Phase 8.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-09-26 00:05 | Claude (Claude Code) | Initial Phase 6 prompt: starting state at commit 120456f, seven steps, decisions 6.1 and 6.2, the four known PRD silences. |
