# Kickoff Prompt: General UI Phase 7, Tool Themes and Presets

Last Updated: 09-09-26 17:15 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory: this work edits `snapmock/main_window.py`, `snapmock/ui/tool_options_bar.py`, the tools' creation defaults, and the settings module, which every other session touches too.

This prompt is the Phase 7 instance of `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1). That prompt still governs the phases, the standards, and the decision list; this one adds what a session needs to know about the repository as Phase 6 left it, so it does not re-derive the state from the code. Where the two disagree, the general prompt wins and this one is corrected.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Build Phase 7 of the General UI PRD (`PRDs/SnapMock-General-UI-PRD.html`, version 2.2 at the start of this phase; the phase bumps it to 2.3): the preset dropdown of Section 5.2, the Tool Themes dialog of Section 11.8, the Manage Presets dialog of Section 11.9, the Tools menu's Tool Themes row and Active Theme label of Section 3.7, JSON storage in the application data directory with `.smktheme` import and export, and the last-used tool option values of Section 15.4. Where the PRD is satisfied already, leave the code alone. Where the implementation departs from the PRD, record the departure in the PRD's change log and in `docs/General-UI-Implementation.md`, as `CLAUDE.md` requires.

Phase 7 opens by presenting the two decisions below with the consequential decision template, one at a time, and waits after each. Nothing is built before both are taken.

## Read first, in this order

1. `docs/General-UI-Implementation.md`, revision 1.9: Section 1 says Phases 0 to 6 are done; Sections 2.3 (the Tools menu entry), 2.5, and 2.11 (the Tool Themes and Manage Presets entry) are the verified inventory for this phase; Section 6 lists the deviations already recorded, one of which this phase closes (Last-used tool option values); Section 13 says what Phase 6 built.
2. `PRDs/SnapMock-General-UI-PRD.html`: Sections 5.2 (the Preset Dropdown and the paragraph after it on per-tool overrides), 5.3 (per-tool contents), 3.7 (the Tools menu's two rows below the tool list), 11.8 (Tool Themes Dialog), 11.9 (Manage Presets Dialog), 11.3 (Preferences > Tools, whose defaults the themes overlap), 15.4 (session persistence, "Last-used tool and its option values"), 1.3 (never-disabled controls), 14 (accessibility, for names on the new controls), and 17 (acceptance). Then `PRDs/SnapMock-Technical-Architecture-PRD.html` Section 4 (data models: there is no theme or preset model), Section 6.1 (file format, if decision 7.1 adds a manifest key), Section 9.1 (dependency policy), and Section 10, binding since 1.4 and now at 1.11: a new module under `ui/`, `core/`, or `config/` gets a row in the same commit; a new package or top-level module also bumps the version.
3. The tool PRDs whose options a preset captures: `PRDs/SnapMock-Basic-Shape-Annotation-Tools-PRD.html` (the shape tools' creation defaults), `PRDs/SnapMock-Text-Callout-Annotation-Tools-PRD.html` (the text and callout defaults, bubble shape, tail style), `PRDs/SnapMock-Numbered-Steps-Stamps-Emoji-PRD.html` (Starting Number), `PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html` (the eyedropper's options, which are not creation defaults). Where a tool PRD defines an option differently, the tool PRD wins and the departure is recorded.
4. `snapmock/tools/base_tool.py` (`creation_defaults`, `options_controls`, `build_options_widgets`, `on_option_changed`), `snapmock/tools/tool_manager.py` (`tool_ids`, `tool`, `activate`, `tool_changed`, `tool_defaults_changed`), every tool under `snapmock/tools/` that sets `_creation_defaults` (rectangle, ellipse, line, arrow, highlight, freehand, text, callout, numbered_step) and the three that keep option widgets of their own (`crop_tool.py`, `raster_select_tool.py`, `lasso_select_tool.py`), `snapmock/ui/tool_options_bar.py` (`ControlSpec`, `SHARED_CONTROLS`, `_on_tool_changed`, `_build_control`, `_write`, `_read_defaults`, `refresh`), `snapmock/ui/property_panel.py` (the tool-defaults mode: `_set_default`, `_populate_from_tool_defaults`, `_populate_appearance_from_tool_defaults`, `refresh_tool_defaults`), `snapmock/ui/preferences_dialog.py` (`_build_tools_page`), `snapmock/main_window.py` (`_setup_tools_menu`, `_apply_tool_defaults`, `_apply_tool_preference_changes`, `_restore_last_tool`, `_save_window_state`, `_register_tools`, `TRANSIENT_TOOLS`), `snapmock/config/settings.py` (`last_tool`, the export-settings JSON precedent around `export/{fmt}/settings`, `_color_text`, `_optional_color`), `snapmock/config/constants.py` (`DEFAULT_LIBRARY_DIRECTORY`, the tool default constants), `snapmock/ui/icons.py` (`ACTION_ICONS` already names a glyph for "Tool Themes..."), `snapmock/ui/unmet_requirements.py`, `snapmock/ui/export_dialog.py` and `snapmock/ui/preferences_dialog.py` as the dialog precedents, `snapmock/io/project_serializer.py` (the manifest, if decision 7.1 adds a key).
5. `tests/test_tool_options_bar.py`, `tests/test_menus.py` (the Tools menu tests), `tests/test_preferences_dialog.py` (`test_tools_and_performance_defaults`, `test_tool_defaults_reach_the_tools`, `test_tool_defaults_are_read_at_startup`), `tests/test_property_panel.py` and `tests/test_property_panel_phase6.py` (the tool-defaults mode), `tests/conftest.py` (the isolated settings fixture: a new application data directory needs the same isolation).

Do not write code until all five are read.

## Starting state, verified at commit 810d99b on 09-09-26

- Nothing of this phase exists: no preset or theme model, no storage, no dropdown, no dialogs, no `.smktheme` reader or writer. The Tools menu holds the eighteen tool rows in six groups and nothing below them; `ACTION_ICONS` already maps "Tool Themes..." to the Tabler `palette` glyph, and the glyph is vendored.
- A tool's settings are its `creation_defaults` dictionary. Nine tools have one: the six vector tools carry `stroke_color`, `fill_color`, `stroke_width`, and `opacity_pct` (freehand adds `smoothing`); the text tool carries the font, style, colour, background, border, padding, alignment, and `auto_size` keys; the callout tool carries the text keys plus `bubble_shape`, `tail_style`, and `tail_width`; the numbered step tool carries `start_number`. Select, lasso select, raster select, crop, stamp, blur, eyedropper, pan, and zoom have none. Values are `QColor`, `float`, `int`, `bool`, `str`, `Qt.AlignmentFlag`, `VerticalAlign`, `BubbleShape`, and `TailStyle`; nothing serializes them, so a JSON store needs a codec.
- The crop tool's aspect ratio and Rule of Thirds, and the raster and lasso selection tools' feather and anti-alias, live on the tool object or in the widget the tool builds, not in `creation_defaults`. A preset cannot capture them unless they move.
- The Tool Options Bar composes each tool's bar from `options_controls` and `SHARED_CONTROLS`; `_write` stores a value in `creation_defaults`, calls `on_option_changed`, and emits `ToolManager.tool_defaults_changed`, which the Property Panel's tool-defaults mode and the bar itself listen to. The leftmost widget is the tool's name label; the preset dropdown goes before it or replaces it.
- Preferences > Tools (stroke colour and width, fill colour, font family and size, freehand smoothing, numbered step start) is pushed into every tool's `creation_defaults` at startup and on every change by `MainWindow._apply_tool_defaults`. The PRD's built-in "Default" theme and this page describe the same values twice; decision 7.2 settles which owns them.
- Session persistence stores the last tool id only (`AppSettings.last_tool`, saved in `_save_window_state`, restored by `_restore_last_tool`, transient tools excluded). Option values are not persisted; the Phase 1 deviation assigns them to this phase.
- No code computes an application data directory. The Library uses `~/SnapMock/Library`; `QStandardPaths` is not used anywhere; `AppSettings` stores the export settings as JSON strings inside `QSettings`, the one JSON precedent.
- The Technical Architecture PRD has no theme or preset data model, no storage location for them, and no Section 10 rows; this phase adds all three.
- Never-disabled controls use `check_requirements`; a dialog with a list and action buttons has two precedents, the Preferences dialog's sidebar and the Export dialog; the Library panel's rename is the inline-edit precedent.
- `tests/conftest.py` points `AppSettings` at a throwaway INI file for every test; anything the phase writes to disk needs the same treatment or tests will write into the developer's home directory.

## Steps, one commit each

1. **Decisions.** Present decision 7.1 (overrides saved with the project) and then decision 7.2 (Preferences > Tools and the Default theme) and wait after each.
2. **Model and storage.** The preset and theme model in a new `core/` module: the codec for every creation-default value type, the per-tool preset store and the theme store as JSON files under the application data directory (decide the location and record it), the built-in Default theme that cannot be deleted or renamed, `.smktheme` read and write with a format version, and the Technical Architecture PRD rows (a Section 4 data model, the storage location, Section 10) in the same commit.
3. **Preset dropdown.** The leftmost control of every tool's bar: the tool's presets alphabetically, Save as Preset..., Update Preset (shown only when a named preset is active and modified), Manage Presets..., Reset to Theme; "Custom" when the settings differ from the applied preset or theme; a preset applied to a tool is a per-tool override of the theme; overrides and option values persist across sessions, closing the Phase 1 deviation; the bar, the Property Panel's tool-defaults mode, and Preferences stay in step through `tool_defaults_changed`.
4. **Manage Presets dialog.** Title "Manage [Tool Name] Presets", the alphabetical list with a compact summary per row, Rename inline, Duplicate with the " Copy" suffix, Delete with confirmation, Close; renames and deletions applied immediately (and undoable, or a recorded deviation: see the silences).
5. **Tool Themes dialog and the Tools menu.** The theme list with the active theme checked, the preview panel by tool, New, Duplicate, Rename, Delete, Import, Export, Apply (resets every tool and clears overrides), Cancel; Tools > Tool Themes... and the read-only Active Theme label with "(modified)" once any override is applied.
6. **Close-out.** General UI PRD 2.3 change-log rows; Technical Architecture PRD rows for every new module and, under decision 7.1 option A, the Section 6.1 row; `docs/General-UI-Implementation.md` revision 1.10 with the phase table, decisions, deviations, tests, and a "What Phase 7 built" section; the next required step.

Each step is ruff-clean and mypy-strict-clean with the suite passing (`test_font_combo_reflects_text_item_font` is the known environmental failure on this machine and is deselected; `test_main_window_default_size` passes). Run the full suite as `QT_QPA_PLATFORM=offscreen uv run pytest -v -o faulthandler_timeout=120` to a log file: a modal message box left open by a test hangs the run, and the dump names the test.

## Decisions to surface

Apply the two-part test from the global guidance. Two decisions are expected to pass it; present each with the consequential decision template before step 2, one at a time, and wait:

- **7.1 Overrides saved with the project.** Section 5.2 says per-tool preset overrides "persist across sessions and are saved with the project". Saving them changes `manifest.json` and the Technical Architecture PRD's Section 6.1, as the guides did in Phase 5, and a project then carries tool settings that apply on open. Options: add an optional manifest key holding the per-tool overrides (a `format_version` that stays 1, a loader that ignores the key), and decide whether opening a project applies them; or keep overrides in the application data directory only, with a General UI PRD change-log row recording that projects do not carry tool settings.
- **7.2 Preferences > Tools and the Default theme.** Preferences > Tools and the built-in Default theme both define the tools' starting values, and `_apply_tool_defaults` overwrites every tool at startup from Preferences. Options: Preferences > Tools becomes the editor of the Default theme's values (its seven settings are read into the Default theme, the startup push becomes the theme load, and the page keeps its place), or Preferences > Tools is replaced by a link to the Tool Themes dialog and its settings keys are retired with a Section 11.3 row.

Everything else follows the PRD; where the PRD is silent, decide, note it under Deviations, and continue. Six silences are known: where the application data directory is (the PRD's example is `~/.config/snapmock/`; `QStandardPaths.AppConfigLocation` under the existing organisation and application names is the candidate); which tools have presets (those with creation defaults; whether the crop and selection tools' widget-held options move into `creation_defaults` so they can be captured, or stay outside presets with a row); whether Manage Presets renames and deletions are undoable, given that presets are not document state and the command stack belongs to a document (a dialog-local undo, or a recorded deviation); how "Custom" is detected (a comparison of the tool's defaults with the applied preset or theme, and what the dropdown shows for a tool whose theme values were never captured); the `.smktheme` schema and its version field; and what the theme preview panel lists per tool.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- Every new module gets a row in Technical Architecture PRD Section 10 in the commit that creates it, and any new package or top-level module also bumps that PRD's version. A change to `layers.json` or the manifest gets a Section 6.1 row and a version bump in the same commit.
- Departures from the General UI PRD are recorded in its change log with a version bump, not only in code comments.
- All mutations of document state go through commands; preset and theme files are not document state, and the session says so where it decides their undo model.
- No control is disabled (General UI PRD 1.3); every dialog button and dropdown row checks its requirements through `check_requirements` and shows the unmet message.
- Every new control gets an accessible name (General UI PRD 14) as it is created; Phase 8 audits, it does not retrofit.
- Slots connected to the process-wide `ThemeManager` must be bound methods of a `QObject`, never lambdas; avoid Python reference cycles between a widget and its children.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- No new runtime dependency without surfacing it as a decision.
- Commit messages end with the attribution block the session provides.

## When the phase is complete

Update the Phase status table in `docs/General-UI-Implementation.md`, bump its revision, add a change-log row, and state the next required step: Phase 8, First run, accessibility, and responsive behaviour, in a new session. Phase 8 opens with kickoff decision 5, the welcome panel's New Blank Canvas card; the acceptance pass against PRD Section 17 follows Phase 8.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-09-26 17:15 | Claude (Claude Code) | Initial Phase 7 prompt: starting state at commit 810d99b, six steps, decisions 7.1 and 7.2, the six known PRD silences. |
