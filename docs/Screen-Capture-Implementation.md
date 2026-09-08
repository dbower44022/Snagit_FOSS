# Screen Capture Implementation Notes

Last Updated: 09-07-26 23:47 · Revision 1.3

Implements the SnapMock Screen Capture PRD (version 1.0, September 2026): the three capture modes, every entry point (global hotkeys, system tray, Main Toolbar button, Capture menu, command-line invocation with a single-instance channel), the capture options, the region selection overlay, the capture backend abstraction with the Linux X11, Linux Wayland and Windows backends, a stub for macOS, the post-capture handoff to the Library, the Capture preferences category, and the Wayland and macOS onboarding dialogs.

## 1. Architecture

Nothing outside `snapmock/capture/` imports a platform module or calls ctypes. The editor sees one coordinator, `CaptureManager`, and connects two signals. That is the whole contract (PRD 6.1).

### 1.1 Package layout

| Component | File | Role |
|---|---|---|
| Data models | `snapmock/capture/models.py` | `CaptureMode`, `CaptureRequest`, `ScreenGrab`, `MonitorInfo`, `CaptureMetadata` (with `to_dict` / `from_dict`), `BackendCapabilities`, `HotkeyBinding`, `CaptureResult`, `PermissionState`, `FullScreenScope` (PRD 10). |
| Backend interfaces | `snapmock/capture/backend.py` | `CaptureBackend` and `HotkeyBackend` abstract bases, `CaptureError` and `CaptureCancelledError`, the null backends, `QtScreenGrabBackend` (the Qt per-screen root-window grab shared by X11, macOS and Windows), and the fakes the test suite runs against. |
| Backend selection | `snapmock/capture/__init__.py` | `select_backends()` picks the module by platform name and session type (PRD 6.2), importing `x11`, `wayland_portal`, `macos` or `windows` by name; an absent or failing module falls back to the null backends and is logged. |
| Manager | `snapmock/capture/manager.py` | `CaptureManager`: `start(request)`, `cancel()`, signals `capture_completed`, `capture_failed`, `capture_cancelled`, `capture_refused(reason, origin)`, `countdown_tick`, `hotkeys_changed`. Owns the delay countdown, the hide-and-restore sequence, modal-dialog refusal, cursor compositing, mode dispatch, clipboard copy, sound, hotkey bindings, the single-instance channel, and the lazily created overlay. |
| Compositing | `snapmock/capture/compositing.py` | Pure functions on a frozen grab: outward-rounded physical rectangles, cursor compositing, region rendering across monitors, All Monitors composition at the highest ratio with black gaps (PRD 2, 4.2, 4.4, 4.5). |
| Overlay | `snapmock/capture/overlay.py` | `RegionOverlay` with one `OverlayWindow` per monitor sharing a `SelectionModel` in virtual logical pixels: dimming, crosshair, selection border, dimensions label, hint bar, magnifier, modifiers, Space move, arrow keys, Escape, right-click, focus loss, and the fault boundary (PRD 5, 7.4). |
| Countdown | `snapmock/capture/countdown.py` | The frameless countdown badge; Escape or a click cancels (PRD 4.1). Also defines the widget property that marks capture UI so the window hider skips it. |
| Window state | `snapmock/capture/window_state.py` | `WindowHider`: records geometry and state of every visible SnapMock window, hides them, reports whether any surface is still exposed, restores once (PRD 3.6). |
| Single instance | `snapmock/capture/single_instance.py` | `SingleInstanceChannel` on a local socket named for the user, with stale-endpoint recovery; `try_forward` sends a command line within the 100 ms budget (PRD 3.5). |
| Command line | `snapmock/capture/cli.py` | `parse_capture_args` for `--capture [mode]` and `--delay N`. |
| Sound | `snapmock/capture/sound.py` | Plays `resources/sounds/shutter.wav` through Qt's sound effect class; failure is silent (PRD 4.3). |
| Tray icon | `snapmock/capture/tray.py` | The tray glyph, drawn in code because no icon asset exists yet. |
| Onboarding | `snapmock/capture/onboarding.py` | `WaylandOnboardingDialog` (consent and desktop-shortcut panels, Copy buttons, per-desktop notes, Don't show again) and `MacOSPermissionDialog` (Continue, Open System Settings, Cancel, then the quit-and-reopen state) (PRD 9). |
| X11 | `snapmock/capture/x11.py` | `X11CaptureBackend` and `X11HotkeyBackend` over a private Xlib connection through ctypes (PRD 6.3, 6.7). |
| Wayland | `snapmock/capture/wayland_portal.py` | `WaylandPortalBackend` over QtDBus and the portal's Screenshot interface (PRD 6.4). |
| Windows | `snapmock/capture/windows.py` | `WindowsCaptureBackend` and `WindowsHotkeyBackend` over user32, gdi32 and dwmapi through ctypes (PRD 6.6, 6.7). |
| macOS | `snapmock/capture/macos.py` | A stub that implements the interfaces, reports the capabilities the platform will have, and raises `CaptureError("not yet implemented on this platform")` from every grab. |

### 1.2 The capture flow

`start(request)` refuses when busy, when a modal dialog is open, or when the backend supports no mode, emitting `capture_refused` with the reason and the request origin so the main window can choose a toast or a notification. The onboarding gate runs next. With a delay, the countdown badge is placed at the top center of the monitor under the cursor and hidden 100 ms before the grab. The hide step records and hides every SnapMock window, polls for unexposed surfaces every 16 ms up to 250 ms, waits two frames, and grabs. Cursor compositing happens on the frozen grab before any mode logic. Full Screen keeps the monitor under the cursor or composites all monitors; Active Window crops to the backend's frame geometry or fails with "No active window found"; when the backend lacks active-window support the request degrades to Region with the hint from PRD 2.3. Region shows the overlay on the frozen grab and crops the confirmed logical rectangle in physical pixels, rounding outward.

Every outcome ends in one of three finish methods, each of which resets state, emits its signal, and then restores the windows. Completion emits before the restore so the Library tab exists when the window reappears (PRD 7.1). A `CaptureCancelledError` from a backend, which the portal raises when the user cancels the compositor's consent dialog, ends as a silent cancel rather than a failure.

### 1.3 X11 through ctypes

The X11 backend opens its own Xlib display rather than sharing Qt's connection. Grabbed key events then arrive on a socket the backend owns, read through a `QSocketNotifier` plus a 150 ms drain timer, so no native event filter or event parsing against Qt's connection is needed. Struct layouts (`XKeyEvent` 96 bytes, `XEvent` 192 bytes, `XFixesCursorImage` 48 bytes) were verified against the installed libraries. The active window comes from `_NET_ACTIVE_WINDOW`, expanded by `_NET_FRAME_EXTENTS` and shrunk by `_GTK_FRAME_EXTENTS` so client-side shadows are excluded; root-pixel geometry is mapped to Qt's logical virtual desktop through the monitor that holds most of the window. The cursor comes from XFixes with its hotspot, in physical pixels. Hotkeys grab the keycode for every combination of Caps Lock and Num Lock; a `BadAccess` reported by the X error handler after `XSync` marks the key as in use by another application, and the previous grab is released before a new one is attempted.

### 1.4 Wayland through the portal

`PortalScreenshotClient` subscribes to the Request interface's `Response` signal, calls `Screenshot` with `interactive` false and a handle token, waits in a local event loop for up to two minutes (the compositor's consent dialog), reads the returned file into a `QImage`, and deletes the file. Response code 1 becomes `CaptureCancelledError`; any other non-zero code, a missing service, or a timeout becomes `CaptureError` with the PRD 6.4 message. The whole-desktop image is split per monitor by physical geometry, scaled first if the compositor returned a different size. No X11 grab is attempted under Wayland.

### 1.5 MainWindow wiring

- Capture menu after Library and before Help with the three modes (shortcuts follow the hotkey preferences and refresh on `hotkeys_changed`), the Delay radio submenu, the three checkboxes bound to preferences, and Capture Preferences. The delay and checkbox state is mirrored across the Capture menu, the toolbar button menu, and the tray menu through one sync method.
- Main Toolbar Group 0: one menu-button control at the left end, installed through `SnapToolBar.set_capture_button`; the main click uses the default mode, the arrow menu lists the modes and the Delay submenu, and the tooltip reads "Capture (key)" for the default mode's hotkey.
- Tray icon and menu per PRD 3.2, created when the preference is on and a tray exists; left click shows the window except on macOS; the tooltip mirrors the countdown; Keep Running in Tray turns the window close into a hide, keeps the process alive without windows, and Quit SnapMock prompts through the normal close path.
- `add_to_library(image, *, source, capture_metadata, when)`: the metadata record is written to `manifest.json` beside `library_metadata`, `captured_at` is the grab time, and `Document.capture_metadata` carries it through continuous write-back. The Library panel's Properties dialog lists the fields.
- Toasts read "Captured to Library: name" or "Captured to Library and clipboard: name"; while the window is hidden in the tray a system notification is shown instead and clicking it shows the window. Failures and refusals follow the same routing, with a notification forced for tray and command-line origins.
- `app.py` parses `--capture`, forwards to a running instance and exits 0, otherwise listens on the channel, registers hotkeys, reports registration failures in one toast, and runs the capture as the first action after the window exists, keeping the window hidden until the capture ends when Hide Window is on.
- Secondary windows (Open in New Window) share the process-wide manager but do not connect its results or own a tray icon.

### 1.6 Preferences

The Capture category holds every setting from PRD 8.1. Hotkey editors register immediately: a change releases the old key, registers the new one, and on refusal shows "In use by another application" beside the editor and keeps the previous key. On a backend without in-process hotkeys, each editor is replaced by "Bind a desktop shortcut to:" with the command and a Copy button, plus the "How to set up a desktop shortcut..." link that opens the Wayland onboarding content. The read-only capability line comes from `CaptureManager.capability_summary()`.

### 1.7 Windows through ctypes

The screen grab is Qt's, which uses a GDI bit-block transfer underneath; ctypes supplies only what Qt does not expose. The Win32 types are spelled out with plain `ctypes` rather than taken from `ctypes.wintypes`, so the module imports for free on Linux and macOS, where the suite still imports it; nothing touches user32, gdi32 or dwmapi until `create_backends()` runs, and that raises `OSError` off Windows.

Per-monitor DPI awareness version 2 is already set by Qt while `QGuiApplication` starts, and a second call is refused, so `create_backends()` verifies the thread's context with `GetThreadDpiAwarenessContext` and `AreDpiAwarenessContextsEqual` instead of setting it. The active window comes from `GetForegroundWindow`, its frame from `DWMWA_EXTENDED_FRAME_BOUNDS` so that the invisible resize border Windows adds is excluded, falling back to `GetWindowRect` only when DWM reports an error; the rectangle is virtual-desktop physical pixels and is mapped through `physical_to_logical`. SnapMock's own windows and the shell classes (`Progman`, `WorkerW`, `Shell_TrayWnd` and their kin) report no active window, so the manager's own fallback applies as it does on X11. The cursor comes from `GetCursorInfo` and `GetIconInfo`, converted with `GetDIBits` into a top-down 32-bit `Format_ARGB32` image; a colour bitmap without alpha is masked by its AND mask, and a monochrome cursor, which is what the stock arrow and I-beam are, is rebuilt from the double-height mask whose upper half is the AND mask and lower half the XOR mask. Every bitmap `GetIconInfo` hands out is released.

Hiding SnapMock before the grab needs one Windows-specific step. Windows fades a window out after `hide()` and DWM keeps compositing it for the whole fade, while `QWindow.isExposed()` goes false about 80 ms in, with the window still almost fully painted. The manager grabs roughly 35 ms after nothing is exposed, so the capture caught SnapMock half faded and every capture carried a translucent copy of the editor. `WindowHider` therefore calls `disable_window_transitions()` on each window immediately before hiding it, which sets `DWMWA_TRANSITIONS_FORCEDISABLED`; the window is then gone in the next frame. Measured on one desktop, two identical windows hidden at the same instant: without the call the window was still fully painted at 35 ms and only gone at 130 ms, with it the window was gone at 0 ms.

Hotkeys are `RegisterHotKey` with `MOD_NOREPEAT` on a message-only window parented to `HWND_MESSAGE`, borrowing the `STATIC` class so none of our own has to be registered. `WM_HOTKEY` arrives through a `QAbstractNativeEventFilter`, and two details matter. The filter is a separate `_HotkeyEventFilter` object rather than the backend itself, because PyQt does not dispatch `nativeEventFilter` to a class that also inherits `QObject` and the backend must be a `QObject` to carry the `triggered` signal; a plain filter receives `WM_HOTKEY`, a `QObject`-mixed one receives nothing. And the filter is removed in `close()`, because Qt keeps a bare pointer to it and calling into a collected filter faults the process at exit. `RegisterHotKey` failing with error 1409 sets the failure reason to "In use by another application", the same wording the X11 backend and the fake use, so Preferences reads the same everywhere.

## 2. Deviations from the PRD

- **`ScreenGrab` carries `monitors`.** PRD 10.3 lists images and cursor fields only. The grab keeps the monitor list at grab time so a monitor change after the grab cannot affect the capture (PRD 4.4), and so the overlay draws from one object.
- **Backend interfaces are abstract base classes, not protocols.** `HotkeyBackend` needs a Qt signal, which requires a `QObject` base; `CaptureBackend` follows the same form.
- **Overlay accent color.** No ThemeManager exists yet (General UI PRD 13.4), so the overlay takes its accent from the application palette's highlight role.
- **Hotkeys apply live; other Capture preferences apply on OK.** The existing dialog collects changes and applies them on accept. Hotkeys register on edit because PRD 9.3 requires an immediate conflict report in the editor.
- **`capture_refused` carries the origin** so the main window can honor PRD 3.6's rule that tray and command-line refusals are shown as system notifications.
- **Countdown badge focus.** PRD 4.1 cancels on Escape while the badge has focus; the badge takes focus when shown, and a click also cancels.
- **Shutter sound.** The PRD left the sound asset as an open question. `resources/sounds/shutter.wav` is a short synthesized click generated for this project, so no license question remains.
- **Windows DPI awareness is verified, not set.** PRD 6.6 says awareness is enabled at startup. Qt has already set per-monitor awareness version 2 by the time `create_backends()` runs, and a second call fails with access denied, so the backend confirms the context and logs it rather than setting it.
- **A Windows hotkey may have no modifier.** The shipped Region default is a bare Print Screen and `RegisterHotKey` accepts a zero modifier mask, so a sequence without a modifier is registered rather than refused.
- **The Windows native event filter is a separate object.** PyQt does not dispatch `nativeEventFilter` to a class that also inherits `QObject`, and `HotkeyBackend` must be one, so the filter cannot be the backend itself.
- **Windows window hiding disables the close animation.** PRD 3.6 says the windows are hidden before the grab. On Windows hiding alone is not enough, because the faded-out window is still composited; the animation is turned off so that hiding takes effect immediately.
- **`physical_to_logical` lives in `backend.py`.** It began in `x11.py`; the Windows backend needs the same mapping and must not import a platform module that is not its own, so it moved beside `qt_monitors` and `QtScreenGrabBackend`.
- **macOS stub reports permission denied.** It cannot preflight or request, so every capture on macOS fails with the Section 6.5 message and the onboarding dialog reaches its quit-and-reopen state. The gate is skipped after Don't show this again.
- **Tray capability.** `BackendCapabilities.tray` is reported true on every real backend; whether a tray exists is decided by Qt at runtime, and the "no tray on this desktop" message appears when the preference is turned on without one.
- **Portal timeout.** The PRD sets no limit for the compositor's consent dialog; two minutes was chosen.

## 3. Tests

All under `tests/test_capture/`, run against the fake backends on the offscreen platform. `tests/conftest.py` gives every `MainWindow` a manager on the fake backends so the suite never touches a real screen or registers a real hotkey.

- `test_models.py`: enumerations, metadata round trip, monitor geometry, settings defaults and clamping.
- `test_backend.py`: null and fake backends, Qt monitor listing.
- `test_compositing.py`: outward rounding, crops within and across monitors, mixed-ratio composition, cursor placement.
- `test_manager.py`: every mode, degradation, refusals, backend and overlay failures, delay and countdown cancel, cursor, clipboard, sound, hide-and-restore ordering, hotkey registration and conflicts, the channel.
- `test_overlay.py`: drag, discard, Shift and Alt, Space move, cancel paths, multi-monitor spanning and clamping, hints, arrow keys, focus loss, painting, fault isolation.
- `test_cli_and_channel.py`: argument forms, forwarding, stale-endpoint recovery.
- `test_main_window.py`: menu order and items, toolbar group, synced toggles, manifest contents, write-back, toast text, failure and busy messages, dirty documents untouched, tray, keep running, hotkey failure toast, command-line first action.
- `test_preferences.py`: the Capture category, live hotkey editing, command-line guidance, capability line, applying changes, tray creation and removal.
- `test_x11.py`: struct sizes, keysym mapping, session refusal; live tests (skipped without a display) for the active window, cursor, grab conflicts, and a synthesized key press through XTest.
- `test_wayland_portal.py`: per-monitor splitting, file handling, injected screenshots, silent cancel, degradation; a fake portal service registered on the session bus exercises the real D-Bus round trip for success, cancel, and error.
- `test_windows.py`: struct sizes against the 64-bit layouts, the Qt-to-virtual-key mapping, and `create_backends` refusing off Windows; live tests (Windows only) for the DPI context, the frame rectangle and title of a window the test creates, the stock cursors put through the ICONINFO conversion, a duplicate key, error 1409 reported as in use, release on unregister, and a `WM_HOTKEY` round trip to `triggered`.
- `test_platform_stubs.py`: the Windows backend's capabilities and its refusal to activate off Windows, the macOS stub, the permission message, and the macOS dialog states.
- `test_wayland_portal.py` is skipped off Linux: QtDBus is absent from some Windows wheels, and where it is present it has no session bus and faults on teardown.

Verified by hand on the X11 machine: struct sizes, EWMH active window with frame extents and title, XFixes cursor image, grab refusal from a second client, release after ungrab, and the portal protocol (handle path, Response signal).

Verified by hand on the Windows machine (Windows 10 22H2, one monitor at ratio 1.0, PyQt6 6.10.2). The live suite is 15 passing under the real platform plugin. Every capture below landed in the Library as a `.smk` whose `manifest.json` carries `backend: windows`.

| Path | Result |
|---|---|
| `--capture full` from a cold start | `full_screen`, 1920x1200, real pixels |
| `--capture full` with an instance running | Forwarded over the single-instance channel; no second process, the running instance wrote the file |
| Ctrl+Print with another application focused | `full_screen`; the hotkey fires without SnapMock in the foreground |
| Alt+Print | `active_window`, rect (681,395) 979x548 and the window's title, including non-ASCII |
| Print, then a drag on the overlay | `region`, rect (300,300) 400x300, exactly the drag |
| Capture menu, Capture Full Screen | `full_screen`; menu shortcuts read Print, Alt+Print and Ctrl+Print from the preferences |
| Capture menu, Include Mouse Cursor then Capture Full Screen | `cursor_included: true` |
| Main Toolbar capture button, then a drag | `region`, rect (900,200) 250x150, exactly the drag |
| Quit, then Ctrl+Print | No capture; the keys are released with the process |
| Ctrl+Print with SnapMock itself in the foreground | The rectangle SnapMock occupied contains only what was behind it: no title bar, toolbar, panels or translucency. Before the animation was disabled the same crop showed the whole editor ghosted over the desktop |

The invisible resize border is excluded as PRD 14.5 requires: for the same window `GetWindowRect` reported (674,395) 993x555 and `DWMWA_EXTENDED_FRAME_BOUNDS` (681,395) 979x548, seven pixels off the left, right and bottom, and the active-window capture used the latter. Cursor compositing was checked against the frozen grab: exactly 249 pixels changed inside the 32x32 box at the hotspot, which is the opaque-pixel count of `IDC_ARROW` measured independently, so every opaque pixel is drawn and nothing else is.

**Still owed**, and not possible on this hardware. A second monitor is needed for the active window and the cursor at a different scale factor, and for whether a composited region crosses a monitor boundary without a seam; only ratio 1.0 was available here. Windows 11 is needed for the Print Screen conflict against its own capture, though the 1409 path itself is covered: a key held by another registration reports "In use by another application". The tray entry point was not exercised, since the tray preference is off by default.

## 4. Follow-ups

- macOS backend: the Screen Recording preflight and request calls, the Core Graphics window list for the active window, the system cursor image; pyobjc remains the optional candidate if ctypes proves fragile (PRD 6.5, open question 2).
- Window snap in the overlay (version 2), scrolling capture (deferred), a KDE-specific Wayland backend for active window and cursor (version 2 candidate).
- Replace the code-drawn tray glyph with a designed icon when the resources directory gains one, and take the overlay accent from the ThemeManager when it exists.
- The single-instance channel is created in `app.py`; a second launch on a machine where the channel cannot be created opens a second window, as before.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.3 | 09-07-26 23:47 | Claude (Claude Code) | Windows hide made immediate by disabling the DWM close animation, so captures no longer contain a translucent copy of the editor; measured and verified end to end. |
| 1.2 | 09-07-26 22:24 | Claude (Claude Code) | Windows hand verification run on an unlocked desktop: all three modes, five entry points, the resize border, cursor compositing, and hotkey release recorded; what remains needs a second monitor or Windows 11. |
| 1.1 | 09-07-26 20:41 | Claude (Claude Code) | Windows backend implemented (Section 1.7); its stub deviation removed and four new ones recorded; `test_windows.py` added; the Windows follow-up closed; Windows hand-verification results and what is still owed recorded. |
| 1.0 | 09-07-26 16:05 | Claude (Claude Code) | Initial implementation notes for the Screen Capture PRD. |
