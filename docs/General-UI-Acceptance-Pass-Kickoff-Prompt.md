# Kickoff Prompt: General UI Acceptance Pass against PRD Section 17

Last Updated: 09-10-26 02:10 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine, with the display available: about a third of the Section 17 bullets can only be judged by looking at the running application, and the session will hand you a checklist to walk through. Start it only when no other session is committing in this working directory.

This prompt closes the General UI work that `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) defined in eight phases. That prompt still governs the standards; this one governs the pass. Where the two disagree, the general prompt wins and this one is corrected.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Run the acceptance pass against Section 17 of the General UI PRD (`PRDs/SnapMock-General-UI-PRD.html`, version 2.4). Section 17 has thirty-six bullets in eight subsections (17.1 Window & Layout, 17.2 Menu Bar, 17.3 Toolbars, 17.4 Canvas, 17.5 Panels, 17.6 Theming, 17.7 Dialogs, 17.8 Accessibility). For every bullet the pass records one verdict, pass, fail, or not applicable, with the evidence that supports it and, for a fail, the cause and the owner. The record is a new section of `docs/General-UI-Implementation.md`, "Acceptance pass against PRD Section 17", one row per bullet.

The pass verifies; it does not build. A bullet that fails is recorded first. A fix may follow only when it is a few lines, changes no requirement, and lands in its own commit after the verdict is written, so the record says what the pass found and not what it left behind. Anything larger is owned by a follow-up: a PRD correction row, the Group and Ungroup kickoff (kickoff decision 4), the Navigation and Raster Operations follow-up (merging, layer blend mode, badges), or a new follow-up list this pass creates.

Three kinds of evidence are admissible, and each row names which:

1. **An automated test that already exists.** Name the file and the test. Section 7 of the implementation notes lists what each phase added.
2. **An automated test written during the pass**, where none exists and the bullet can be judged offscreen. Tests go in `tests/test_acceptance.py`, one per bullet, named after the bullet, so the record stays traceable.
3. **A check on the real display**, where the bullet is visual (rendering, glitches, legibility, focus outlines), needs a desktop service (the System theme's colour scheme hint, a screen reader), or needs a real drag. The session writes the exact steps and the expected observation, presents them as one checklist, and waits. Doug's answers are the evidence, quoted in the row.

## Read first, in this order

1. `docs/General-UI-Implementation.md`, revision 1.14: Section 1 says every phase is done; Section 5 lists the decisions the verdicts must respect (a deferral by decision is a fail whose owner is already named, not a pass); Section 6 lists every recorded departure from the PRD, each with its change-log version; Section 7 maps every test file to what it covers; Sections 8 to 15 say what each phase built.
2. `PRDs/SnapMock-General-UI-PRD.html`, Section 17 in full, then each section a bullet cites: 2 (window, docking, title), 3 (every menu table), 4 (toolbar groups and icons), 5 (the options bar), 6 (canvas, and 6.6 for the cursor table that 17.4 calls "Section 6.5"), 7 (Layer Panel), 8 (Property Panel), 9 (status bar zones), 11 (the four dialogs 17.7 names), 13 (theme tables), 14 (accessibility), 15 (session persistence, for the 17.1 bullets on saved layout), and the change log from version 1.7 up, which records every departure a verdict must weigh.
3. `tests/conftest.py` (the isolated settings, the first-run flag, the floored panel thresholds, the fake capture backends: every test window opens at the 1024 by 600 minimum offscreen), `tests/test_window_layout.py`, `tests/test_menus.py`, `tests/test_main_toolbar.py`, `tests/test_tool_options_bar.py`, `tests/test_canvas_area.py`, `tests/test_cursors.py`, `tests/test_layer_panel.py`, `tests/test_property_panel_phase6.py`, `tests/test_status_bar.py`, `tests/test_theme.py`, `tests/test_accessibility.py`, `tests/test_color_picker.py`, `tests/test_export_dialog.py`, `tests/test_preferences_dialog.py`, `tests/test_window_management.py`, `tests/test_responsive.py`, `tests/test_welcome_panel.py`: read each file's test names, not every body, to build the evidence map.
4. `snapmock/main_window.py` only where a bullet needs it: `_update_title`, `_view_reset_layout`, `_require`, `_setup_view_menu` (the toggles), the drop handling the 17.4 drag-and-drop bullet points at (`SnapView` in `snapmock/core/view.py`, `dragEnterEvent` and `dropEvent`, and `snapmock/io/importer.py`), and `snapmock/ui/unmet_requirements.py`.
5. `snapmock/app.py` and the run command in `CLAUDE.md`, for the display checks.

Do not write anything until all five are read.

## Starting state, verified at commit 3d1f252 on 09-10-26

- Every phase of the General UI implementation is done. The suite passes 892 tests with 13 skipped and one environmental deselection (`test_font_combo_reflects_text_item_font`); ruff and mypy are clean.
- General UI PRD 2.4 carries the Phase 8 rows; Technical Architecture PRD 1.12 carries Phase 8's Section 10 rows without a version bump.
- Known before the pass starts, so the session does not rediscover them:
  - 17.2 "all specified items": Group and Ungroup (Section 3.6) are rows that explain a deferral (decision 4, own kickoff); Merge Down, Merge Visible, and Flatten All (Section 3.4) are rows that explain a deferral (the raster follow-up); Check for Updates (Section 3.8) says it is scheduled for a later phase and no phase owns it. Each is a fail with a named owner, except Check for Updates, which needs one.
  - 17.2 "Keyboard shortcuts work as specified": six tool letters differ from Section 3.7 by decision (PRD 1.7 row). The verdict weighs the decision.
  - 17.4 "Section 6.5": the cursor table is Section 6.6 (PRD inconsistency list, implementation notes Section 4).
  - 17.4 "creates a background layer": confirm what a dropped image file becomes today before judging; the import path may create a raster region on the active layer rather than a background layer.
  - 17.6 "WCAG 2.1 AA": `tests/test_accessibility.py` holds seventeen pairs per theme at 4.5:1 after six colours were lifted in Phase 8 (PRD 2.4 row). The bullet is about all text; the row should say what the test covers and what it does not (text drawn by tools on the canvas is the user's colour choice, not the theme's).
  - 17.6 "Theme switching is instant": covered by `tests/test_theme.py`; the System option needs a desktop that reports a colour scheme, which the offscreen platform does not.
  - 17.8 "Screen reader announces control names and states": no automated evidence is possible; PyQt6 does not expose `QAccessible`. This is a display check with Orca (GNOME) or the desktop's reader, and the status hint's live-label mechanism (PRD 2.4 row) is what to listen for.
  - 17.8 "All controls are reachable via Tab": `tests/test_accessibility.py` covers the zone order and Tab focus on toolbar buttons; the menu bar is reached with Alt or F10 by decision (PRD 2.4 row).
  - 17.1 "80% of screen": `_default_window_size` gives 80 percent of the available geometry, never below the minimum; offscreen that is the minimum, so the bullet is a display check as well as a test.
- The kickoff's known open issues in the PRD's Section 18 (the Blur letter, the title-page date, the approval record) are not Section 17 bullets and are not part of this pass.

## Steps, one commit each

1. **Evidence map.** Add the new section to the implementation notes with all thirty-six rows: bullet text, the evidence kind (existing test, new test, display check), and, for existing tests, the file and test name. Rows for display checks carry the steps and the expected observation. Present the display checklist to Doug as one message and wait; do not run the steps yourself against the offscreen platform and call them display evidence.
2. **Automated verdicts.** Write `tests/test_acceptance.py` for the rows that need a new test; run the full suite; fill in every automated row's verdict. A fail is written as a fail with its cause and owner before anything else happens.
3. **Display verdicts.** Fill in the display rows from Doug's answers, quoting them. A bullet Doug could not check is "not applicable" with the reason, never a pass by default.
4. **Small fixes, if any.** Only what the task statement allows, each in its own commit, each named in the row it changes with the commit hash, the verdict left as the pass found it and a note saying it is fixed since.
5. **Close-out.** The summary at the top of the new section: the counts of pass, fail, and not applicable; the fails with an owner and the fails without one; the PRD correction rows the pass proposes (General UI PRD 2.5 if any row changes a requirement or corrects a table); the implementation notes revision bumped with a change-log row; the next required step.

Each commit is ruff-clean and mypy-strict-clean with the suite passing. Run the full suite as `QT_QPA_PLATFORM=offscreen uv run pytest -q -o faulthandler_timeout=120` to a log file in the background: it takes about fifteen minutes, and a modal dialog left open by a test hangs the run, and the dump names the test.

## Decisions to surface

Apply the two-part test from the global guidance. One decision is expected to pass it, at the end of step 3:

- **Fails without an owner.** Every fail the pass finds that no decision, kickoff, or follow-up already owns. Options for each: a small fix now under the task statement's limit; a row in a new "General UI follow-up" list in the implementation notes for a later kickoff; or a PRD correction row that changes the requirement to what is built, where the built behaviour is the better one. Present the list once, with a recommendation per fail and the cost of each, and wait.

Everything else follows the PRD; where a bullet is ambiguous, say how it was read in the row and continue.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- A verdict is one of three words. "Pass" means the bullet holds as written or under a recorded decision that the row cites; a deferral is a fail whose owner the row names.
- No control is disabled (General UI PRD 1.3); a check that finds one is a fail.
- A new test module gets no Technical Architecture Section 10 row (Section 10 lists the package, not the test files), but a new module under `snapmock/` would; none is expected.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- Commit messages end with the attribution block the session provides.

## When the pass is complete

Update `docs/General-UI-Implementation.md`: the phase table gains a row "Acceptance pass" with its status and commit range; the revision is bumped with a change-log row; the next required step is stated. With the pass done, the next required step is the Group and Ungroup kickoff (kickoff decision 4), then the Navigation and Raster Operations follow-up, unless the pass's fails-without-an-owner decision puts a General UI follow-up first.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-10-26 02:10 | Claude (Claude Code) | Initial acceptance-pass prompt: starting state at commit 3d1f252, the three kinds of evidence, the thirty-six bullets in eight subsections, the known fails and inconsistencies, five steps, one decision. |
