# Kickoff Prompt: Screen Capture Implementation

Last Updated: 09-07-26 12:05 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Implement the **SnapMock Screen Capture PRD** version 1.0 (`PRDs/SnapMock-Screen-Capture-PRD.docx`) on the Linux backends first, with the Windows and macOS backends stubbed behind the same interfaces. Write `docs/Screen-Capture-Implementation.md` when done, in the format of `docs/Library-Implementation.md`.

## Read first, in this order

1. `PRDs/SnapMock-Screen-Capture-PRD.docx`, all sections. Extract text with `unzip -p file.docx word/document.xml | sed 's/<\/w:p>/\n/g; s/<[^>]*>//g'`.
2. `docs/Screen-Capture-PRD-Summary.md`: the decisions and the open questions.
3. `docs/Library-Implementation.md`: the entry point `MainWindow.add_to_library`, the toast, `LibraryManager.create_from_image`, and the settings and preferences patterns to follow.
4. `snapmock/main_window.py`, `snapmock/config/settings.py`, `snapmock/config/shortcuts.py`, `snapmock/ui/preferences_dialog.py`, `snapmock/ui/toast.py`, `snapmock/app.py`.
5. `tests/conftest.py` and `tests/test_library_panel.py` for the isolated-settings fixture and the MainWindow test pattern.

Do not write code until all five are read.

## Build order

Each step is one commit, ruff-clean and mypy-strict-clean, with tests passing on the offscreen platform.

1. `snapmock/capture/models.py`: CaptureMode, CaptureRequest, ScreenGrab, MonitorInfo, CaptureMetadata, BackendCapabilities, HotkeyBinding, CaptureResult (PRD Section 10). Settings keys and defaults in `AppSettings` (PRD Section 8.1, 12.2).
2. `snapmock/capture/backend.py`: the `CaptureBackend` and `HotkeyBackend` protocols, `CaptureError`, a `NullCaptureBackend`, a `NullHotkeyBackend`, and a `FakeCaptureBackend` for tests that returns synthetic monitors and images.
3. `snapmock/capture/manager.py`: `CaptureManager` with `start`, `cancel`, `capture_completed`, `capture_failed`, the delay timer, the hide-and-restore sequence, modal-dialog refusal, cursor compositing, clipboard copy, and the single-instance channel (PRD Sections 3.5, 3.6, 4, 6.1). Tests against the fake backend.
4. `snapmock/capture/overlay.py`: the region selection overlay (PRD Section 5) drawing from a ScreenGrab. Tests drive it with synthetic mouse and key events.
5. `MainWindow` wiring: Capture menu, toolbar Group 0, tray icon and menu, `add_to_library(..., capture_metadata=...)`, `capture_metadata` in `manifest.json`, toast and notification text (PRD Sections 3.2 to 3.4, 7, 12.1).
6. Preferences: the Capture category and the capability line (PRD Section 8.1).
7. `snapmock/capture/x11.py`: the X11 backend and X11 hotkey backend through ctypes (PRD Sections 6.3, 6.7). Guarded so the module imports on every platform and activates only on an X11 session.
8. `snapmock/capture/wayland_portal.py`: the portal backend over QtDBus (PRD Section 6.4), plus the Wayland onboarding dialog (PRD Section 9.2).
9. `snapmock/capture/windows.py` and `snapmock/capture/macos.py`: stubs that implement the protocols, report accurate capabilities, and raise `CaptureError("not yet implemented on this platform")` from `grab_screens`. The macOS onboarding dialog (PRD Section 9.1) is built against the stub.
10. `docs/Screen-Capture-Implementation.md` with architecture, deviations from the PRD, tests, and follow-ups.

## Decisions to surface

Apply the two-part test from the global guidance. One is expected to pass it; present it with the consequential decision template before step 7 and wait:

1. X11 access through ctypes against libX11 directly, versus through Qt's native interface for XCB, versus python-xlib as a new dependency. The PRD leaves this to the implementer.

Everything else follows the PRD. Where the PRD is silent, decide, note it under Deviations in the implementation notes, and continue.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the implementation notes.
- All scene mutations via Commands; capture creates files, never mutates scenes.
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit. `test_main_window_default_size` is a known environmental failure.
- No new runtime dependency without surfacing it as a decision.
- Commit messages end with the attribution block the session provides.

## When the implementation is complete

State the next required step and write the next-action prompt for the Windows and macOS backends.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-07-26 12:05 | Claude (Claude Code) | Initial implementation kickoff prompt. |
