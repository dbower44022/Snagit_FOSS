# Screen Capture PRD: Summary Note

Last Updated: 09-07-26 12:12 · Revision 1.1

Companion to `PRDs/SnapMock-Screen-Capture-PRD.html` version 1.0, the canonical copy; `PRDs/SnapMock-Screen-Capture-PRD.docx` is the Word original it was converted from. One page: the decisions made, the open questions. The open questions are also Section 15 of the HTML document.

## Decisions surfaced and approved

| Decision | Choice | Cost accepted |
|---|---|---|
| Global hotkeys | Platform-specific registration behind one `HotkeyBackend` interface: X11 (key grab) and Windows (RegisterHotKey) in version 1, both through ctypes with no new dependency. macOS deferred. Command-line invocation through a single-instance channel on every platform. | Two native code paths to maintain; a documented desktop-shortcut setup step on Wayland and macOS. |
| Wayland strategy | Desktop portal (Screenshot interface over QtDBus) only. Portal absence is reported with a message; no X11 fallback. | No active-window mode and no cursor inclusion on Wayland in version 1; a compositor-owned consent dialog. |
| Overlay process model | The region selection overlay runs inside the editor process. | Hide-and-restore choreography and overlay fault isolation rest on code, not a process boundary. |

## Routine decisions made without asking

- **Default hotkeys:** PrintScreen (Region), Alt+PrintScreen (Active Window), Ctrl+PrintScreen (Full Screen). All editable.
- **Default capture mode:** Region.
- **Capture menu placement:** a top-level Capture menu after Library and before Help. The General UI PRD menu order is otherwise untouched.
- **Toolbar placement:** a new Group 0 Capture at the left end of the Main Toolbar, one menu-button style control.
- **Window behavior:** hide (never minimize) before the grab when the Hide Window preference is on (default on); restore once, from a single code path, on success, cancel, and failure.
- **Region confirms on release.** No adjustment step with handles in version 1. A drag under 4 by 4 logical pixels is discarded.
- **Frozen-image overlay.** The screen is grabbed first; the overlay shows and crops that image. This is what makes one overlay work on all four backends.
- **Physical pixels always.** Captures are stored at the display's physical resolution; the device pixel ratio is recorded in `capture_metadata`.
- **Tray icon on by default; Keep Running in Tray off by default.** Closing the window still quits unless the user opts in.
- **Clipboard copy is additive** (off by default) and is the supported route for bringing a capture into an existing non-library document via paste. Capturing directly into the active document was rejected for version 1.
- **Scrolling capture deferred; freehand region out of scope** (the lasso tool inside the editor covers it).
- **Window snap in the overlay** (click a window to select its bounds) deferred to version 2; it needs window enumeration on every platform.
- **Entry point change:** `MainWindow.add_to_library` gains an optional `capture_metadata` keyword argument; the existing signature keeps working.
- **New manifest field:** optional `capture_metadata` object beside `library_metadata`.
- **No new undoable commands.** A capture creates a file; it never mutates a scene.
- **Supersedes** the Technical Architecture PRD 7.2 note that tray integration is not required for version 1.

## Open questions

1. **GNOME consent dialog frequency.** Whether the GNOME portal asks once per session or on every screenshot call is inferred, not checked. If it asks every time, the Wayland experience is one click worse than the PRD implies; the onboarding text already warns of both cases.
2. **macOS active window through ctypes.** The Core Graphics window list is reachable from ctypes, but pyobjc is the safer route. The PRD names pyobjc as an optional implementation candidate; the implementer should decide after a spike.
3. **Wayland overlay placement.** Compositors may ignore the per-monitor full-screen request. The PRD records this as a known limitation; if it bites on GNOME in practice, a single overlay window spanning the virtual desktop is the fallback to evaluate.
4. **Windows 11 PrintScreen.** Windows 11 can bind PrintScreen to the Snipping Tool by default. The PRD documents the conflict; whether SnapMock should offer to take over the key on first run is a version 1.1 question.
5. **Sound asset.** The shutter sound file needs a license-compatible source before it ships.

## Next required step

Implement the PRD in a new session using `docs/Screen-Capture-Implementation-Kickoff-Prompt.md`.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 09-07-26 12:12 | Claude (Claude Code) | Point at the HTML PRD as the canonical copy; note that the open questions are now its Section 15. |
| 1.0 | 09-07-26 12:05 | Claude (Claude Code) | Initial summary note for Screen Capture PRD v1.0. |
