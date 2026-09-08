# Kickoff Prompt: General UI Phase 4, Toolbars and Status Bar

Last Updated: 09-08-26 16:50 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory: this work edits `snapmock/main_window.py`, `snapmock/ui/toolbar.py`, `snapmock/ui/tool_options_bar.py`, `snapmock/ui/status_bar.py`, and every tool's options, which every other session touches too.

This prompt is the Phase 4 instance of `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1). That prompt still governs the phases, the standards, and the decision list; this one adds what a session needs to know about the repository as Phase 3 left it, so it does not re-derive the state from the code. Where the two disagree, the general prompt wins and this one is corrected.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Build Phase 4 of the General UI PRD (`PRDs/SnapMock-General-UI-PRD.html`, version 1.9 at the start of this phase; the phase bumps it to 2.0): the Main Toolbar of Section 4, the Left Tool Palette of Section 2, the Tool Options Bar's shared controls of Section 5, and the status bar zones of Section 9. Where the PRD is satisfied already, leave the code alone. Where the implementation departs from the PRD, record the departure in the PRD's change log and in `docs/General-UI-Implementation.md`, as `CLAUDE.md` requires.

Phase 4 opens by presenting kickoff decision 2, the memory usage zone, with the consequential decision template, and waits. Nothing is built before that decision is taken.

## Read first, in this order

1. `docs/General-UI-Implementation.md`, revision 1.4: Section 1 says Phases 0 to 3 are done; Sections 2.2, 2.4, 2.5, and 2.9 are the verified inventory for this phase; Section 6 lists the deviations already recorded, three of which this phase closes; Section 10 says what Phase 3 built.
2. `PRDs/SnapMock-General-UI-PRD.html`: Sections 2.1 and 2.2 (zones and proportions), 4 (Main Toolbar), 5 (Tool Options Bar), 9 (Status Bar), 1.3 (never-disabled controls), 13 (theming, for the toolbar and separator colours the style sheets already carry), and 17 (acceptance). Then `PRDs/SnapMock-Technical-Architecture-PRD.html` Section 10, binding since 1.4 and now at 1.7: a new module under `ui/` or `core/` gets a row in the same commit; a new package or top-level module also bumps the version.
3. `PRDs/SnapMock-Screen-Capture-PRD.html` Sections 3.3 (the Capture control in the toolbar) and 14.5 (nothing outside `snapmock/capture/` calls a platform module or ctypes), and `docs/Screen-Capture-Implementation.md` Section 1.5 for the Capture button as built.
4. The tool PRDs for the options each tool owns: `PRDs/SnapMock-Basic-Shape-Annotation-Tools-PRD.html`, `PRDs/SnapMock-Text-Callout-Annotation-Tools-PRD.html`, `PRDs/SnapMock-Blur-Highlighter-Eyedropper-Tools-PRD.html`, `PRDs/SnapMock-Numbered-Steps-Stamps-Emoji-PRD.html`, and `PRDs/SnapMock-Navigation-Raster-Operations-PRD.html` (crop, raster selection, lasso, zoom, pan). Section 5.3 of the General UI PRD lists the bar contents per tool; where a tool PRD places an option elsewhere, the tool PRD wins and the departure is recorded.
5. `snapmock/main_window.py` (toolbar construction near the top of `__init__`, `_setup_view_menu`, `_setup_capture_toolbar`, `_apply_menu_icons`, `_on_theme_changed`, `_apply_tool_defaults`, `_update_menu_states`, `_configure_view`), `snapmock/ui/toolbar.py` (`SnapToolBar`, the unused `ZoomDropdown`), `snapmock/ui/tool_options_bar.py`, `snapmock/ui/status_bar.py`, `snapmock/ui/icons.py`, `snapmock/ui/unmet_requirements.py`, `snapmock/core/theme_manager.py`, `snapmock/tools/base_tool.py` (`build_options_widgets`, `creation_defaults`), the six tools that override `build_options_widgets` (select, text, callout, crop, raster_select, lasso_select), `snapmock/tools/eyedropper_tool.py`, `snapmock/config/settings.py` (the Phase 3 keys under `appearance/`, `tools/`, `view/`), `snapmock/config/shortcuts.py`.
6. `tests/test_theme.py`, `tests/test_menus.py`, `tests/test_window_layout.py`, `tests/test_preferences_dialog.py`, `tests/test_capture/test_main_window.py` (the toolbar group and synced toggles), `tests/conftest.py`.

Do not write code until all six are read.

## Starting state, verified at commit 750a299 on 09-08-26

- The top toolbar is `SnapToolBar`, object name `ToolPalette`, the tool palette synced with the `ToolManager`. Its buttons are icon-only Tabler glyphs with "Name (Shortcut)" tooltips, sized from `theme_manager().icon_qsize()`, and it re-applies icons on `theme_changed` and `icon_size_changed`. The Capture menu-button sits at its left end through `set_capture_button`. View > Show Tool Palette toggles this toolbar; the deviation entry in the notes says Show Main Toolbar arrives with Phase 4.
- `ZoomDropdown` in `snapmock/ui/toolbar.py` is an editable combo box over `ZOOM_STEPS`; nothing instantiates it. The PRD's preset list for the Main Toolbar dropdown (10, 25, 50, 75, 100, 150, 200, 400, 800, 1600, 3200) differs from `ZOOM_STEPS`.
- `ToolOptionsBar` (object name `ToolOptionsBar`) adds a label and calls the active tool's `build_options_widgets`. Six tools override it; twelve show only the label. No shared control set exists. The preset dropdown is Phase 7 and is not built here.
- `ui/icons.py` already maps every Main Toolbar label (New, Open, Save, Export Quick (PNG), Undo, Redo, Cut, Copy, Paste, Duplicate, Delete, Bring to Front, Send to Back, the six Align rows, Zoom In, Zoom Out, Fit to Window) to a glyph, so the Main Toolbar can reuse the existing `QAction` objects and their icons rather than create new ones.
- The never-disabled helper is `check_requirements` and `show_not_available` in `snapmock/ui/unmet_requirements.py`, with the `unmet_messages` fixture in `tests/conftest.py`. Toolbar buttons that share a menu action inherit its behaviour; the Section 4.3 message on an unmet requirement must hold for every button.
- The status bar (`SnapStatusBar`) has three zones: tool hint, cursor position formatted "Cursor: x, y", and zoom formatted "Zoom: 100%". Missing: the PRD formats, the fixed widths, selection size, canvas size, the clickable zoom, and memory usage.
- Preferences > Tools already pushes stroke colour, stroke width, fill colour, font family, font size, freehand smoothing (`creation_defaults["smoothing"]`), and the numbered step starting number (`creation_defaults["start_number"]`) into each tool through `MainWindow._apply_tool_defaults`, and `PropertyPanel.refresh_tool_defaults` re-reads them. The Tool Options Bar's controls edit the same `creation_defaults` dictionaries; the two surfaces must stay in step.
- The momentary eyedropper (Alt) picks a colour that has no consumer; Section 5.3's "Apply to Stroke" and "Apply to Fill" buttons are its consumer, noted as a deviation to close in this phase.
- Slots connected to the process-wide `ThemeManager` must be bound methods of a `QObject`, never lambdas; Phase 3 hit the deleted-widget error in the suite.
- Theme colours for toolbars (`toolbar-bg`, `toolbar-separator`, `button-hover`, `button-pressed`) are in the two style sheets and already apply to any `QToolBar`; no new colour work is expected.

## Steps, one commit each

1. **Decision 2.** Present the memory usage zone decision and wait. If the platform-call option is chosen, the same commit that adds the module amends Screen Capture PRD Section 14.5's rule in that PRD's change log to name the one additional module.
2. **Main Toolbar.** A new `QToolBar` below the menu bar with the six groups of Section 4.2 separated by dividers, reusing the menu actions; the Capture control moves here as Group 0 per Screen Capture PRD 3.3, and the Screen Capture implementation notes Section 1.5 are updated; 24 px icons in 32 px buttons, tooltips "Name (Shortcut)"; the zoom dropdown wired to the active view and rebound on tab switch; View > Show Main Toolbar; the toolbar in `saveState` persistence and in Reset Layout; the 40 px height.
3. **Left Tool Palette.** `SnapToolBar` becomes a vertical toolbar on the left edge, 48 px wide, one column; View > Show Tool Palette keeps toggling it; the deviation entry closes.
4. **Tool Options Bar, shared controls.** A shared control set (stroke colour, fill colour, stroke width, stroke style, font family, font size, bold/italic/underline, fill and stroke opacity, shadow toggle) built once and composed per tool from a declaration on the tool; per-tool contents from Section 5.3 reconciled against each tool PRD, with departures recorded; the Select tool's "Selection: N items" and alignment buttons; the eyedropper's swatch, hex, RGB, and Apply to Stroke / Apply to Fill; the freehand Smoothing slider reading `creation_defaults["smoothing"]`; the numbered step Starting Number reading `creation_defaults["start_number"]`; edits reflected in the Property Panel's tool-defaults mode and the reverse; the 36 px height.
5. **Status bar.** The six zones of Section 9 with the PRD formats and fixed widths; selection size from the selection manager; canvas size from the scene, updated on resize; the zoom zone clickable, opening the same dropdown as the Main Toolbar; memory usage per decision 2, refreshed every 5 seconds, orange above 500 MB and red above 1 GB using the theme's warning and error colours; the 24 px height.
6. **Close-out.** General UI PRD 2.0 change-log rows; Technical Architecture PRD rows for any new module; Screen Capture implementation notes for the moved Capture button; `docs/General-UI-Implementation.md` revision 1.5 with the phase table, deviations, tests, and a "What Phase 4 built" section; the next required step.

Each step is ruff-clean and mypy-strict-clean with the suite passing (`test_main_window_default_size` and `test_font_combo_reflects_text_item_font` are the known environmental failures on this machine; the first passed again after Phase 1 and may be run).

## Decision to surface

Apply the two-part test from the global guidance. One decision is expected to pass it; present it with the consequential decision template before step 2, and wait:

2. **Memory usage zone** (kickoff decision 2). The readout needs process memory on three platforms. Options: a new runtime dependency (a cross-platform process library), or platform calls kept inside one module with the Screen Capture PRD 14.5 rule amended to name it. A third route, Python's resource module, covers Linux and macOS only and needs a Windows call anyway.

Everything else follows the PRD; where the PRD is silent, decide, note it under Deviations, and continue. Two silences are known: the Main Toolbar's zoom preset list versus the shipped `ZOOM_STEPS` (decide and record), and which options bar controls a tool PRD keeps in the Property Panel (decide per tool and record).

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- Every new module gets a row in Technical Architecture PRD Section 10 in the commit that creates it, and any new package or top-level module also bumps that PRD's version.
- Departures from the General UI PRD are recorded in its change log with a version bump, not only in code comments.
- Nothing outside `snapmock/capture/` calls a platform module or ctypes (Screen Capture PRD Section 14.5) unless decision 2 amends that rule in the same commit.
- No control is disabled (General UI PRD 1.3); every toolbar button checks its requirements through `check_requirements` and shows the unmet message.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- No new runtime dependency without surfacing it as a decision.
- Commit messages end with the attribution block the session provides.

## When the phase is complete

Update the Phase status table in `docs/General-UI-Implementation.md`, bump its revision, add a change-log row, and state the next required step: Phase 5, Canvas, in a new session, opening with decision 3 (guide persistence in the project file, which changes the `.smk` format and the Technical Architecture PRD's file-format section).

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-08-26 16:50 | Claude (Claude Code) | Initial Phase 4 prompt: starting state at commit 750a299, six steps, decision 2, the two known PRD silences. |
