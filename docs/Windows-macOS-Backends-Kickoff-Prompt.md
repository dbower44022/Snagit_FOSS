# Kickoff Prompt: Windows and macOS Capture Backends

Last Updated: 09-07-26 20:41 · Revision 1.3

> Step A (Windows) is **done**, as of 09-07-26. It was carried out from `docs/Windows-Backend-Kickoff-Prompt.md`, which held the Windows environment setup and the corrected DPI-awareness step; the result is described in Section 1.7 of `docs/Screen-Capture-Implementation.md`, along with the hand verification that is still owed on a real Windows desktop. Use this document for step B (macOS) only.
>
> Step B is deferred as of 09-07-26: no macOS device is available. The macOS stub stays in place, and every capture on macOS fails with the Section 6.5 message until step B runs. Nothing in the Windows work depends on it.

Paste everything below the line into a new Claude Code session rooted in this repository, on the target platform (a Windows machine for step A, a macOS machine for step B). Each platform's backend is verified by hand on that platform; the offscreen test suite covers only what a fake can exercise.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Replace the Windows and macOS stubs in `snapmock/capture/` with working backends that implement the Screen Capture PRD version 1.0 (`PRDs/SnapMock-Screen-Capture-PRD.html`, Sections 6.5, 6.6, 6.7, 9.1). Keep the interfaces, the null-backend fallback, and the fake-backed test suite unchanged.

## Read first, in this order

1. `docs/Screen-Capture-Implementation.md`: the architecture, especially 1.3 (how the X11 backend uses a private connection and ctypes), and the Deviations list.
2. `PRDs/SnapMock-Screen-Capture-PRD.html`, Sections 6.5 to 6.8, 9.1, 10.6, 14.5.
3. `snapmock/capture/backend.py` (`QtScreenGrabBackend`, `HotkeyBackend`), `snapmock/capture/x11.py` (the pattern to follow), `snapmock/capture/windows.py`, `snapmock/capture/macos.py`, `snapmock/capture/onboarding.py`.
4. `tests/test_capture/test_x11.py` and `tests/test_capture/test_platform_stubs.py` for the portable-plus-live test pattern.

Do not write code until all four are read.

## Build order

Each step is one commit, ruff-clean and mypy-strict-clean, with the offscreen suite passing. Live tests are guarded and skipped off-platform.

A. Windows (`snapmock/capture/windows.py`):
   1. Per-monitor DPI awareness at startup (`SetProcessDpiAwarenessContext`), called from `create_backends()` before any screen is queried.
   2. Active window: `GetForegroundWindow`, `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)`, mapped to Qt logical coordinates; title through `GetWindowTextW`.
   3. Cursor: `GetCursorInfo`, `GetIconInfo`, the icon bitmap into a `QImage` with alpha and hotspot.
   4. Hotkeys: `RegisterHotKey` on a message-only window, `WM_HOTKEY` through a `QAbstractNativeEventFilter`; `MOD_NOREPEAT`; failure code 1409 reported as "In use by another application". Set `supported` true.
   5. Live tests guarded by `sys.platform == "win32"`.

B. macOS (`snapmock/capture/macos.py`):
   1. Permission: `CGPreflightScreenCaptureAccess` and `CGRequestScreenCaptureAccess` through ctypes against CoreGraphics; `request_permission()` returns Granted, Denied, or NotRequired (before 10.15).
   2. Active window: `CGWindowListCopyWindowInfo` for the frontmost application's front on-screen window, bounds mapped to Qt logical coordinates, title from `kCGWindowName`. Decide after a spike whether ctypes against CoreFoundation is workable or pyobjc is needed; a new dependency is a decision to surface.
   3. Cursor: `NSCursor.currentSystemCursor` image and hotspot, if reachable; report unavailable otherwise.
   4. Hotkeys stay deferred (null hotkey backend); the command-line route remains.
   5. Live tests guarded by `sys.platform == "darwin"`.

C. Update `docs/Screen-Capture-Implementation.md`: remove the two stub deviations, describe each backend in Section 1, add the tests, bump the revision and change log.

## Decisions to surface

Apply the two-part test from the global guidance. Expected to pass it: pyobjc as a new dependency for the macOS window list, if the ctypes spike fails. Present it with the consequential decision template and wait. Everything else follows the PRD; where the PRD is silent, decide, note it under Deviations, and continue.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the implementation notes.
- Nothing outside `snapmock/capture/` imports a platform module or calls ctypes (PRD 14.5).
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit. `test_main_window_default_size` and `test_font_combo_reflects_text_item_font` are known environmental failures on the development machine.
- No new runtime dependency without surfacing it as a decision.
- Commit messages end with the attribution block the session provides.

## When the implementation is complete

State the next required step and write the next-action prompt for the version 2 candidates (window snap in the overlay, the KDE Wayland backend).

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.3 | 09-07-26 20:41 | Claude (Claude Code) | Step A done; header points at the Windows kickoff prompt and the implementation notes. |
| 1.2 | 09-07-26 19:31 | Claude (Claude Code) | Step B deferred; no macOS device available. |
| 1.1 | 09-07-26 19:16 | Claude (Claude Code) | Step A superseded by the Windows-only kickoff prompt; this document now covers step B only. |
| 1.0 | 09-07-26 16:05 | Claude (Claude Code) | Initial kickoff prompt for the Windows and macOS backends. |
