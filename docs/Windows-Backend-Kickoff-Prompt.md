# Kickoff Prompt: Windows Capture Backend

Last Updated: 09-07-26 19:16 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on a Windows machine. This prompt replaces step A of `docs/Windows-macOS-Backends-Kickoff-Prompt.md`; step B (macOS) of that document still stands and runs on a Mac. The Windows backend is verified by hand on Windows; the offscreen test suite covers only what a fake can exercise.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Replace the Windows stub in `snapmock/capture/windows.py` with a working backend that implements the Screen Capture PRD version 1.0 (`PRDs/SnapMock-Screen-Capture-PRD.html`, Sections 6.6, 6.7, 6.8). Keep the interfaces, the null-backend fallback, the macOS stub, and the fake-backed test suite unchanged except where this prompt says otherwise.

## Step 0: make the development environment work on Windows

Do this before reading code. The repository was developed on Linux and lives inside a Dropbox folder, and both facts matter on Windows.

1. Install uv if it is missing (`winget install astral-sh.uv`), then from the repository root run `uv python install 3.12` and `uv sync --all-groups`. This creates a fresh `.venv`; do not reuse any `.venv` that Dropbox may have synced from the Linux machine.
2. Stop Dropbox from syncing the virtual environment and the tool caches. Dropbox on Linux emptied `.venv\bin` on 09-07-26, and the same will happen here. In PowerShell:

   ```powershell
   foreach ($d in ".venv", ".pytest_cache", ".ruff_cache", ".mypy_cache") {
       if (Test-Path $d) { Set-Content -Path $d -Stream com.dropbox.ignored -Value 1 }
   }
   ```

   Run the loop again after the first test run creates any cache directory that did not yet exist.
3. Set `git config core.autocrlf input` for this repository so committed files keep the LF line endings the Linux history uses.
4. Run the suite offscreen: `$env:QT_QPA_PLATFORM = "offscreen"; uv run pytest -q`. Expect `tests/test_capture/test_wayland_portal.py` to fail at collection because PyQt6 wheels for Windows do not ship `PyQt6.QtDBus`. Fixing that is step A.0 below. Every other failure is either `test_main_window_default_size` and `test_font_combo_reflects_text_item_font` (known environmental failures on the Linux machine; record whether they fail here too) or something to report before continuing.

## Read first, in this order

1. `docs/Screen-Capture-Implementation.md`: the architecture, especially 1.3 (how the X11 backend keeps every platform call inside its module and reaches the platform through ctypes), Section 2 Deviations, and Section 4 Follow-ups.
2. `PRDs/SnapMock-Screen-Capture-PRD.html`, Sections 6.6 to 6.8, 10.6, 14.5.
3. `snapmock/capture/backend.py` (`QtScreenGrabBackend`, `HotkeyBackend`, the failure-reason strings in the fake hotkey backend), `snapmock/capture/x11.py` (the pattern to follow, including `physical_to_logical` and the hotkey backend's failure reasons), `snapmock/capture/windows.py`, `snapmock/capture/__init__.py` (`select_backends`), `snapmock/capture/models.py` (`MonitorInfo`, `ScreenGrab`, `HotkeyBinding`).
4. `tests/test_capture/test_x11.py` and `tests/test_capture/test_platform_stubs.py` for the portable-plus-live test pattern, and `tests/conftest.py` for how the suite keeps `MainWindow` on the fake backends.

Do not write code until all four are read.

## Build order

Each step is one commit, ruff-clean and mypy-strict-clean, with the offscreen suite passing. Live tests are guarded by `sys.platform == "win32"` and skipped elsewhere.

A.0 Suite collection on Windows. In `tests/test_capture/test_wayland_portal.py` replace the module-level `PyQt6.QtDBus` import with `pytest.importorskip("PyQt6.QtDBus")` so the module skips where QtDBus is absent. Confirm `snapmock/capture/wayland_portal.py` is only ever imported by name from `select_backends()` on Linux, so the application itself needs no change. This is the only edit to an existing test module other than the stub test in A.5.

A.1 DPI awareness. The kickoff plan called for `SetProcessDpiAwarenessContext` from `create_backends()`. That cannot work as written: `create_backends()` runs after `QApplication` exists, Qt 6 already sets per-monitor DPI awareness version 2 on Windows during `QGuiApplication` startup, and a second call fails with access denied. So: at the start of `create_backends()`, read the current context with `GetThreadDpiAwarenessContext` and compare it to `DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2` with `AreDpiAwarenessContextsEqual`. If equal, log it at debug level and move on; record under Deviations that Qt provides the awareness and the backend verifies rather than sets it. If not equal, stop and surface a decision (see below), because the fix lives in `snapmock/app.py` before `QApplication` is created.

A.2 Screen grab. Delete the stub's `grab_screens` override so the backend inherits `QtScreenGrabBackend.grab_screens`, which grabs each `QScreen` and scales to `MonitorInfo.physical_size`. Verify by hand on a mixed-DPI pair of monitors that each image matches its physical size and that the composited region crosses the monitor boundary without a seam.

A.3 Active window. `GetForegroundWindow`; `DwmGetWindowAttribute` with `DWMWA_EXTENDED_FRAME_BOUNDS` (value 9) for the visible frame, falling back to `GetWindowRect` if DWM reports an error; title through `GetWindowTextLengthW` and `GetWindowTextW`. The DWM rectangle is in virtual-desktop physical pixels; map it to Qt logical coordinates the way `physical_to_logical` in `x11.py` does, using the monitor that contains the window's centre. Return None when the foreground window is SnapMock's own, the desktop, or the taskbar, so the manager's own fallback applies as it does on X11.

A.4 Cursor. `GetCursorInfo`; return None unless `CURSOR_SHOWING` is set. `GetIconInfo` for the hotspot and bitmaps. Convert through `GetDIBits` with a 32-bit top-down `BITMAPINFO` into a `QImage` in `Format_ARGB32`. Handle the monochrome case where `hbmColor` is null and `hbmMask` is double height (the upper half is the AND mask, the lower half the XOR mask), which is how the I-beam cursor arrives. Release every GDI handle from `GetIconInfo` with `DeleteObject`. The hotspot is in physical pixels; return it in the cursor image's own pixels, which is what `ScreenGrab.cursor_hotspot` expects.

A.5 Hotkeys. `WindowsHotkeyBackend` creates a message-only window (`HWND_MESSAGE` parent) through `CreateWindowExW` and registers each binding with `RegisterHotKey` using `MOD_NOREPEAT`. Map a `QKeySequence` to Windows modifiers and a virtual-key code; reject sequences without a modifier and keys with no virtual-key mapping with the same failure reasons the X11 backend uses. `RegisterHotKey` failing with error 1409 (`ERROR_HOTKEY_ALREADY_REGISTERED`) sets `failure_reason` to "In use by another application", matching the fake and the X11 backend so the Preferences editor shows one wording everywhere. Deliver `WM_HOTKEY` through a `QAbstractNativeEventFilter` installed on the application; the filter reads the hotkey identifier from `wParam` and emits `triggered` with the binding's action. `unregister` and `unregister_all` call `UnregisterHotKey`; the window is destroyed when the backend is deleted. Set `supported` true. Rewrite `test_windows_stub_reports_capabilities_and_refuses_grab` in `tests/test_capture/test_platform_stubs.py` to the new contract: capabilities unchanged, `supported` true, and `create_backends()` still returns the two backends without touching a screen. Leave the macOS tests alone.

A.6 Import safety. `snapmock/capture/windows.py` must still import cleanly on Linux and macOS, because `tests/test_capture/test_platform_stubs.py` imports it on every platform. Reach `ctypes.windll` only inside functions or behind `sys.platform == "win32"`, never at module level. Run the offscreen suite once more after the final commit to prove it.

A.7 Live tests. Add `tests/test_capture/test_windows.py` guarded like `test_x11.py`: struct sizes, virtual-key mapping, DPI awareness context, active window geometry and title for the test's own window, the cursor image when a cursor is showing, and a hotkey round trip through `RegisterHotKey` on a key combination unlikely to be taken (for example Ctrl+Alt+Shift+F12) with `keybd_event` or `SendInput` to press it, with `unregister_all` in teardown.

## Hand verification on Windows

Run `uv run python -m snapmock` and record the result of each item in the implementation notes:

- Full screen, active window, and region from the menu, the toolbar, the tray, and each hotkey.
- Active window on a maximized window, a window with the invisible resize border (compare against `GetWindowRect`), and a window on the secondary monitor.
- Cursor on and off, arrow and I-beam, with the cursor on the secondary monitor at a different scale factor.
- Hotkey conflict: enable Windows 11's "Use the Print screen button to open screen capture", bind Print Screen in Preferences, and confirm the editor reports "In use by another application".
- Hotkeys still fire while another application has focus, and stop firing after Quit.
- A second `python -m snapmock --capture region` reaches the running instance through the single-instance channel.

## C. Update the implementation notes

In `docs/Screen-Capture-Implementation.md`: remove the "Windows hotkey stub reports unsupported" deviation and the Windows row of the stub description; describe the Windows backend in a new Section 1.7 in the style of 1.3; add the DPI-awareness deviation from A.1; add `test_windows.py` and the rewritten stub test to Section 3; move the Windows item out of Section 4 Follow-ups; record the hand-verification results; bump the revision and add a change-log row.

## Decisions to surface

Apply the two-part test from the global guidance. Expected to pass it, if it arises: A.1 finding that Qt has not set per-monitor awareness version 2, because the fix touches `snapmock/app.py` and must still honour PRD 14.5 (only `snapmock/capture/` calls the platform). Present it with the consequential decision template and wait. Everything else follows the PRD; where the PRD is silent, decide, note it under Deviations, and continue.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the implementation notes.
- Nothing outside `snapmock/capture/` imports a platform module or calls ctypes (PRD 14.5).
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- No new runtime dependency without surfacing it as a decision. `pywin32` is not needed; ctypes reaches user32, dwmapi, and gdi32 directly.
- Commit messages end with the attribution block the session provides.

## When the implementation is complete

State the next required step: the macOS backend, step B of `docs/Windows-macOS-Backends-Kickoff-Prompt.md`, run on a Mac. Update that document's header to say step A is done and point to this document, and add a change-log row.

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-07-26 19:16 | Claude (Claude Code) | Initial Windows-only kickoff prompt, split from the combined Windows/macOS prompt. Adds the Windows environment step (uv, Dropbox ignore, line endings, QtDBus skip), corrects the DPI-awareness step to verify rather than set, and adds the hand-verification list. |
