# Kickoff Prompt: General UI Implementation

Last Updated: 09-08-26 13:45 · Revision 1.1

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory: this work edits `snapmock/main_window.py`, the toolbars, the panels, and the settings module, which every other session touches too.

The General UI PRD covers all of the window chrome, and closing it is several sessions of work. This prompt therefore defines phases. A session executes phases in order, one commit per step, and records where it stopped in `docs/General-UI-Implementation.md`. A later session pasting this same prompt starts at the first phase not marked done there.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Implement the General UI PRD (`PRDs/SnapMock-General-UI-PRD.html`, at the version its revision table shows; each phase bumps it) in the phases below, closing the gap between what the PRD specifies and what the application does today. Where the PRD is satisfied already, leave the code alone. Where an implementation departs from the PRD, record the departure in the PRD's change log, as `CLAUDE.md` requires, and in the implementation notes.

## Read first, in this order

1. `docs/General-UI-Implementation.md` if it exists: its "Phase status" section says where to start. If it does not exist, this is the first session and Phase 0 creates it.
2. `PRDs/SnapMock-General-UI-PRD.html`, all of it. It is the specification for every phase. Then `PRDs/SnapMock-Technical-Architecture-PRD.html` Section 10, which is binding since version 1.4: a PRD that introduces a package or a top-level module amends Section 10 in the same version. Section 10 lists every module under every package, so a new module under `ui/`, `core/`, or `config/` also gets a row there in the same commit that creates it.
3. `docs/Library-Implementation.md`, `docs/Screen-Capture-Implementation.md`, and `docs/Library-Follow-Up-Kickoff-Prompt.md` for the three subsystems that already put items into the menus, toolbars, Preferences, and status bar. The Library follow-up delivers a session-private trash and a New Canvas menu item; the Export dialog was assigned to this work by a decision on 09-07-26.
4. `snapmock/main_window.py` (menus, toolbars, docks, close path, help actions), `snapmock/ui/toolbar.py`, `snapmock/ui/tool_options_bar.py`, `snapmock/ui/status_bar.py`, `snapmock/ui/preferences_dialog.py`, `snapmock/ui/color_picker.py`, `snapmock/ui/layer_panel.py`, `snapmock/ui/property_panel.py`, `snapmock/config/settings.py`, `snapmock/config/shortcuts.py`, `snapmock/config/constants.py`, `snapmock/core/view.py`, `snapmock/io/exporter.py`.
5. `tests/test_menus.py`, `tests/test_preferences_dialog.py`, `tests/test_property_panel.py`, `tests/test_canvas_area.py`, `tests/conftest.py`.

Do not write code until all five are read.

## Gap inventory, verified against the code on 09-07-26

This is the starting list, not the final one. Phase 0 re-verifies it and completes it.

Present and close to the PRD: the menu bar's menus and most items; the Layer, Image, and Arrange menus; the View menu's zoom, grid, ruler, snap, and panel toggles; rulers, grid, checkerboard, canvas shadow, and the empty-canvas prompt; the Resize Canvas and Resize Image dialogs; the Property Panel's collapsible sections including the canvas section; window geometry and dock state persistence; recent files; a zoom dropdown class.

Missing or departing from the PRD:

- **Icons.** `snapmock/resources/icons/` is empty. Toolbar buttons are text. The PRD requires an icon set with light and dark variants.
- **Main Toolbar.** The toolbar at the top is the tool palette synced with the tool manager. The PRD's Main Toolbar (file, edit, clipboard, z-order, alignment, and zoom groups) does not exist, and the PRD's Left Tool Palette is a vertical toolbar on the left edge.
- **Tool Options Bar.** Each tool builds its own widgets; there is no preset dropdown and no shared control set.
- **Never-disabled controls.** Only one call disables a control, but no menu or toolbar action shows the PRD's "which requirements are unmet" message. That behaviour must be audited action by action.
- **View menu.** Missing: Show Crosshairs, Show Guides, Snap to Guides, Lock Guides, Clear All Guides, Show Tool Palette, Show Status Bar, Reset Layout, Dark Mode.
- **Edit menu.** Missing: Select All Text, Find/Replace Color.
- **Arrange menu.** Missing: Group, Ungroup. Both need a group item type that the item hierarchy does not have.
- **Tools menu.** Missing: Tool Themes and the Active Theme label.
- **Help menu.** Welcome, Keyboard Shortcuts, and Check for Updates are "coming soon" message boxes. The Documentation and Report a Bug links point at placeholder addresses, not at `dbower44022/Snagit_FOSS`.
- **File menu.** Print is a "coming soon" message box. Export opens a save-file dialog, not the Export dialog. Export Quick has no last-used settings to use.
- **Dialogs.** No Export dialog, no Tool Themes dialog, no Manage Presets dialog, no Keyboard Shortcuts dialog. The colour picker is the Qt colour dialog, not the PRD's popover. About lacks Copy Version Info. Unsaved Changes lacks the canvas preview. Preferences is a single page of four groups (General, View, Library, Capture), not the PRD's sidebar of categories, and most settings in the Appearance, Canvas & Grid, Tools, and Performance categories do not exist.
- **Status bar.** Has hint, cursor, and zoom. Missing: selection size, canvas size, memory usage, and the clickable zoom.
- **Layer Panel.** A plain list of names. Missing: visibility and lock toggles in the row, thumbnails, opacity indicator, drag reorder, the bottom action bar, badges, and Ctrl+click multi-selection.
- **Canvas.** Missing: crosshairs, guides (creation from rulers, move, delete, snap, lock, persistence in the project file), and the cursor table has not been audited.
- **Theming.** No theme manager, no style sheets, no Dark Mode, no System option. `resources/themes/` is empty.
- **Accessibility.** Zero accessible names set anywhere.
- **Window management.** No minimum size, no Reset Layout, no panel collapse thresholds, no multi-monitor check for floating panels.
- **Session persistence.** Missing: theme, last-used export settings, last-used tool and its options, zoom per recent project.
- **First run.** No welcome panel.

## Phases

Each step in a phase is one commit, ruff-clean and mypy-strict-clean, with the suite passing (`test_main_window_default_size` and `test_font_combo_reflects_text_item_font` are known environmental failures on this machine). Each phase ends by updating `docs/General-UI-Implementation.md`.

**Phase 0: Inventory and notes.** Re-verify the gap inventory above against the code, section by section of the PRD, and write `docs/General-UI-Implementation.md` with: a Phase status table (one row per phase: not started, in progress, done, with the commit range), the verified inventory, an empty Deviations list, and a change log. Present the completed inventory and stop for Doug's confirmation before Phase 1.

**Phase 1: Menus, shortcuts, help, and window.** Every menu item in PRD Section 3 present with its shortcut; the never-disabled audit, with one shared helper that shows the unmet-requirement message; the Keyboard Shortcuts dialog built from `config/shortcuts.py`; About with version, build date, licence, links, and Copy Version Info; the Documentation and Report a Bug links pointing at the real repository; Reset Layout; the minimum window size; the window title pattern; session persistence for the last-used tool. Group and Ungroup, Print, Check for Updates, and the View menu's guide and crosshair items are excluded from this phase (see Decisions and Phase 5).

**Phase 2: Export.** The Export dialog of PRD Section 11.2 with per-format options, output path, last-used directory per format, and last-used settings; the Library's multi-select variant with output directory, Apply to All, and the existing progress dialog; Export Quick using the last-used settings and opening the dialog on first use; export settings in session persistence. The live preview and file-size estimate are the last step of the phase, so the dialog is usable before they land.

**Phase 3: Theme and Preferences.** The theme manager in `core/`, the light and dark style sheets in `resources/themes/`, the System option, Dark Mode in the View menu, live switching; canvas rendering (selection handles, grid, rulers, guides, overlay accent) reading from the theme manager; the Preferences dialog rebuilt as sidebar categories with every setting in Section 11.3, each wired to the code that reads it; the icon set (see Decisions) applied to toolbars and menus.

**Phase 4: Toolbars and status bar.** The Main Toolbar with its six groups; the Left Tool Palette as a vertical toolbar; the Tool Options Bar's shared controls; the status bar zones of Section 9 including memory usage (see Decisions).

**Phase 5: Canvas.** Crosshairs, guides with their View menu items and Preferences colours, guide persistence in the project file (see Decisions), and the cursor table audit.

**Phase 6: Panels and colour picker.** The Layer Panel of Section 7; the Property Panel's remaining items (Item Info section's layer dropdown and item lock, mixed indicators everywhere, text section items); the colour picker popover of Section 11.1.

**Phase 7: Tool themes and presets.** The preset dropdown, the Tool Themes dialog, the Manage Presets dialog, JSON storage in the application data directory, the `.smktheme` import and export, the Active Theme label.

**Phase 8: First run, accessibility, responsive behaviour.** The welcome panel (see Decisions); accessible names and descriptions on every control, tab order, focus outline; panel collapse thresholds; multi-monitor recovery for floating panels; the Unsaved Changes preview.

## Decisions to surface

Apply the two-part test from the global guidance. These are expected to pass it; present each with the consequential decision template at the start of the phase that needs it, and wait:

1. **Icon set** (Phase 3): vendor an open-licence SVG icon set into `resources/icons/` under its licence file, or draw a project-owned set. A vendored set is a licensing and attribution decision.
2. **Memory usage zone** (Phase 4): the PRD's memory readout needs process memory on three platforms. A new runtime dependency is one option; platform calls kept inside one module are the other.
3. **Guide persistence** (Phase 5): guides saved in the project file change the `.smk` format and the Technical Architecture PRD's file-format section. Present the format change before writing it.
4. **Group and Ungroup** (raised in Phase 1, built later or deferred): a group item type touches the item hierarchy, the commands, serialization, and the Technical Architecture PRD. Options are to schedule it as its own kickoff or to defer it with a change-log entry in the General UI PRD.
5. **Welcome panel's New Blank Canvas card** (Phase 8): whether it creates a Library canvas, matching the Library decision of 09-07-26 that New Canvas lives in the Library menu, or an unsaved document like File > New.
6. **Print** (Phase 1 raises it; not scheduled): whether the print dialog is in scope for this PRD's implementation or deferred with a change-log entry.

Everything else follows the PRD; where the PRD is silent, decide, note it under Deviations, and continue.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- Every new module gets a row in Technical Architecture PRD Section 10 in the commit that creates it, and any new package or top-level module also bumps that PRD's version.
- Departures from the General UI PRD are recorded in its change log with a version bump, not only in code comments.
- Nothing outside `snapmock/capture/` calls a platform module or ctypes (Screen Capture PRD Section 14.5). If the memory zone takes the platform-call option, that rule is amended in the Screen Capture PRD's change log to name the one additional module, in the same commit.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- No new runtime dependency without surfacing it as a decision.
- Commit messages end with the attribution block the session provides.

## When a phase is complete

Update the Phase status table in `docs/General-UI-Implementation.md`, bump its revision, add a change-log row, and state the next required step: the next phase, in a new session if this one is long. When Phase 8 is done, the next required step is the acceptance pass against PRD Section 17, recorded in the implementation notes.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 09-08-26 13:45 | Claude (Claude Code) | The PRD version is no longer fixed at 1.6 in the task statement; each phase bumps the PRD, and the notes name the current version. |
| 1.0 | 09-07-26 23:06 | Claude (Claude Code) | Initial kickoff prompt: verified gap inventory, eight phases, six decisions to surface. |
