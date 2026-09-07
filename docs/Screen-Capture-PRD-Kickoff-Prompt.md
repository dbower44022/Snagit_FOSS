# Kickoff Prompt: Screen Capture PRD

Last Updated: 09-07-26 01:45 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository.

---

Operating mode: ARCHITECTURE

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Write the **SnapMock Screen Capture PRD**, a product requirements document in the same family as the existing PRDs in `PRDs/`. Deliver it as `PRDs/SnapMock-Screen-Capture-PRD.docx`, version 1.0, using python-docx (already a dev dependency), matching the structure and register of the existing documents. Also write a short companion note `docs/Screen-Capture-PRD-Summary.md` (one page) listing the decisions made and the open questions.

## Read first, in this order

1. `PRDs/SnapMock-Library-PRD.docx`, Sections 2.3, 6, and 8: the capture-to-library workflow this PRD must feed.
2. `docs/Library-Implementation.md`: what is already built. `MainWindow.add_to_library(image, source)` is the existing entry point a capture must call; the toast, auto-open preference, and auto-naming already exist.
3. `PRDs/SnapMock-General-UI-PRD.docx`: menu bar, main toolbar, tool options bar, preferences dialog, keyboard shortcuts, first-run experience, and the never-disabled-controls principle.
4. `PRDs/SnapMock-Navigation-Raster-Operations-PRD.docx`, Section 1.3 and any capture references.
5. `PRDs/SnapMock-Technical-Architecture-PRD.docx`: class structure, the `.smk` format, and the platform targets.
6. Extract text from a `.docx` with `unzip -p file.docx word/document.xml | sed 's/<\/w:p>/\n/g; s/<[^>]*>//g'`.

Do not draft any section until all five documents are read. A PRD written against the wrong assumptions costs two rewrites.

## What the PRD must cover

Follow the section pattern of the tool PRDs: Document Overview (purpose, scope, dependencies), then feature sections, then Data Models, Command Definitions, Serialization, Preferences Integration, Keyboard Shortcuts, Acceptance Criteria, Changelog.

Feature sections, at minimum:

- **Capture modes**: full screen, active window, region (drag-select with magnifier and pixel dimensions), and a stated position on scrolling capture and freehand region (in scope, deferred, or out of scope, with the reason).
- **Capture entry points**: global hotkeys, system tray icon and menu, a Capture button in the main toolbar, and a File or Capture menu. Specify what happens to the SnapMock window during capture (hide, minimize, or stay) and how the window is restored.
- **Capture options**: delay timer, include or exclude the mouse cursor, capture sound, multi-monitor behavior, high-DPI scaling, and clipboard copy alongside library storage.
- **Platform backends**: Linux X11, Linux Wayland (portal-based), macOS (screen recording permission), Windows. For each: how the capture is taken, what permission prompts appear, and what degrades gracefully. Name the abstraction the application code sees so backends are interchangeable.
- **Post-capture flow**: the image goes to the library through the existing entry point with source `capture`; auto-open and toast behavior are governed by Library preferences; define what changes, if anything, when a capture is taken while a non-library document is active.
- **Region selection overlay**: interaction, keyboard modifiers, escape and cancel, appearance, and behavior across monitors.
- **Preferences**: a Capture category (default mode, hotkeys, delay, cursor, sound, hide window, copy to clipboard).
- **First-run**: permission onboarding on macOS and Wayland.

## Decisions to surface

Apply the two-part test from the global guidance. These are expected to pass it; present each with the consequential decision template before drafting the sections that depend on it, and wait for the answer:

1. Global hotkeys: an in-process cross-platform library versus a platform-specific implementation versus tray-only invocation without global hotkeys in version 1.
2. Wayland strategy: portal only, portal with X11 fallback, or X11 only for version 1.
3. Whether the capture overlay runs inside the main process or as a separate helper process.

Everything else is a routine choice: decide it, state it in the summary note, and continue.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to the PRD text and to every reply.
- The document carries a version, a date, and a changelog section like the other PRDs. The companion note carries `Last Updated: MM-DD-YY HH:MM` and a change log table.
- Name third-party libraries only in the platform backend section and mark them as implementation candidates, not requirements.
- Acceptance criteria are testable statements, one per line, grouped by feature section.

## When the PRD is complete

State the next required step and write the next-action prompt for implementing the PRD in a new session.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-07-26 01:45 | Claude (Claude Code) | Initial kickoff prompt. |
