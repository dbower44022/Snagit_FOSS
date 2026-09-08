# Kickoff Prompt: Library Follow-Up (Delete Undo, Export Scope, New Canvas)

Last Updated: 09-07-26 22:57 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory; the session edits `snapmock/main_window.py` and the shared command stack, which other work touches too.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Close the three Library deviations recorded in `docs/Library-Implementation.md` Section 2, according to the decisions Doug made on 09-07-26. Two of the three change code; one changes only documents.

## Decisions already made (do not reopen)

1. **Delete gets undo through a session-private trash.** Delete moves files into the reserved `.trash` folder at the library root, as a Library command. Undo moves them back. A file goes to the system trash when its command is discarded from the command stack, when SnapMock quits, and by a sweep at startup. Rejected: keeping delete without undo; a private trash that never reaches the system trash.
2. **The Export dialog stays with the General UI PRD.** The Library keeps its file-dialog fallback. Nothing in export code changes, and the Export Quick wording stays as it is. The General UI implementation kickoff, when written, must include the Library's multi-select variant: output directory, Apply to All, progress with cancel.
3. **New Canvas joins the Library menu.** File > New stays outside the Library. The Library menu gains New Canvas next to New Folder, doing exactly what the panel's empty-space context-menu item does: a blank canvas at the default size in the folder the panel is showing. The panel item stays.

## Read first, in this order

1. `docs/Library-Implementation.md`, all of it, then `PRDs/SnapMock-Technical-Architecture-PRD.html` Section 10, which is binding since version 1.4: a PRD that introduces a package or a top-level module amends Section 10 in the same version. This work is not expected to add either; if it does, amend Section 10 in the same commit.
2. `PRDs/SnapMock-Library-PRD.html`: File Management Operations, Library Menu, Command Definitions (`DeleteLibraryFileCommand` in particular), Export.
3. `snapmock/library/manager.py` (`TRASH_DIR_NAME`, `delete_files`, `move_library`, `flush`, `create_blank`), `snapmock/library/commands.py`, `snapmock/core/command_stack.py` (`push` and its limit handling, `clear`), `snapmock/ui/library_panel.py` (the delete path and the Ctrl+Z handling), `snapmock/main_window.py` (`_setup_library_menu`, `_library_new_canvas`, `_open_in_new_window`, `closeEvent`).
4. `tests/test_library_manager.py`, `tests/test_library_panel.py`, `tests/conftest.py`.

Do not write code until all four are read.

## Facts verified on 09-07-26 that shape the design

- `.trash` is already reserved: the folder listing hides dot-folders, the size total skips it, and `move_library` leaves it behind. Nothing writes to it yet.
- The Library has its own `CommandStack` with the 200-command limit; the panel handles Ctrl+Z and Ctrl+Shift+Z against it. Edit > Undo in the menu bar acts on the active tab's stack. That stays.
- The panel's delete path shows the confirmation dialog, emits `files_about_to_be_deleted` so the main window closes tabs, then calls `delete_files`, which sends to the system trash outside any command.
- `CommandStack` has no notification when a command is dropped: by the limit in `push`, by redo truncation in `push`, or by `clear`.
- Every `MainWindow` builds its own `LibraryManager`, so Open in New Window produces a second manager and a second Library stack over the same library root. Two windows can hold deletes at the same time.

## Build order

Each step is one commit, ruff-clean and mypy-strict-clean, with the suite passing (`test_main_window_default_size` and `test_font_combo_reflects_text_item_font` are known environmental failures on this machine).

1. **Discard hook on the command stack.** Add a `discard()` method to `BaseCommand` with an empty default, and have `CommandStack` call it for every command it drops: the oldest when the limit is exceeded, the truncated redo history on `push`, and everything on `clear`. Scene commands inherit the empty default. Tests in `tests/test_command_stack.py` or the nearest existing module for all three paths.

2. **The delete command.** `DeleteLibraryFileCommand` in `snapmock/library/commands.py`, matching the PRD's shape: `redo` moves each path into the manager's session trash folder under a unique name and records the pairs; `undo` moves them back; `discard` sends what is still in the session trash to the system trash. `LibraryManager` gains the session trash folder, `.trash/<session id>` created on first use so two windows never sweep each other's files, plus `trash_files`, `restore_files`, and `purge_session_trash`. `delete_files` becomes the command's implementation detail or is removed. The panel's delete path pushes the command instead of calling `delete_files`; the confirmation dialog and `files_about_to_be_deleted` stay. Folders move whole. The panel refreshes through `files_changed` as it does now. Undo does not reopen a closed tab; note that in the implementation notes.

3. **Sweeps.** On the main window's close path, next to `flush`, purge that window's session trash to the system trash. At `LibraryManager` construction, sweep every folder under `.trash` whose session id is not this manager's to the system trash, which handles crashes and windows that closed without a clean exit. `move_library` sweeps `.trash` before moving so nothing is stranded. Tests for each.

4. **New Canvas in the Library menu.** In `_setup_library_menu`, add New Canvas after New Folder, calling `_library_new_canvas` with the folder the panel is showing. Test in `tests/test_library_panel.py` alongside the existing menu tests.

5. **Library PRD amendment.** In `PRDs/SnapMock-Library-PRD.html`: File Management Operations and `DeleteLibraryFileCommand` describe the session trash and when files reach the system trash; the Library Menu table gains the New Canvas row; the Export section states that the Export dialog and the Library's multi-select variant are delivered by the General UI implementation. Bump the document version, add revision-control and change-log rows in the document's own format, and do not name products.

6. **Implementation notes.** In `docs/Library-Implementation.md`: remove the three deviations, describe the session trash in Section 1.3, add the tests to Section 3, move the Export dialog to Section 4 Follow-ups with the Library variant named, bump the revision and add a change-log row.

## Decisions to surface

Apply the two-part test from the global guidance. None is expected. If step 1 turns out to need a change to the command interface every scene command implements, stop and present it with the consequential decision template.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- No new runtime dependency. `send2trash` is already present.
- Commit messages end with the attribution block the session provides.

## When the implementation is complete

State the next required step: the General UI implementation kickoff prompt, which must carry the Export dialog (General UI PRD Section 11.2) with the Library's multi-select variant, and which should decide whether the welcome screen's New Blank Canvas card creates a Library canvas.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-07-26 22:57 | Claude (Claude Code) | Initial kickoff prompt from the three Library deviation decisions made on 09-07-26. |
