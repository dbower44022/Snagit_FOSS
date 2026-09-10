# Kickoff Prompt: Check for Updates

Last Updated: 09-10-26 14:40 · Revision 1.0

Paste everything below the line into a new Claude Code session rooted in this repository on the Linux machine. Start it only when no other session is committing in this working directory: this work changes `snapmock/main_window.py`, adds one module under `snapmock/core/`, and edits the acceptance test, which every other session touches too.

This prompt is the Check for Updates kickoff that the acceptance-pass decision of 09-10-26 on row 6 and the first bullet of `docs/General-UI-Implementation.md` Section 16.10 point at. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) still governs the standards; this one governs the work. Where the two disagree, the general prompt wins and this one is corrected.

---

Operating mode: DETAIL

Read the project `CLAUDE.md` at the repository root. No other repository is involved in this session.

## Task

Build Help > Check for Updates of `PRDs/SnapMock-General-UI-PRD.html` Section 3.8 (version 2.8 at the start of this work; the work bumps it to 2.9): "Check if a newer version is available (queries GitHub releases API)". Today the row is present and shows the recorded deferral through `MainWindow._help_check_updates` and `show_not_available` ("Update checking is scheduled for a later phase."). The work replaces the message with the behaviour: a query of the GitHub releases API for the repository named by `REPOSITORY_URL` in `snapmock/config/constants.py` (`dbower44022/Snagit_FOSS`), a version comparison against `snapmock.__version__`, a message with the result, and the Section 1.3 message when the network is unavailable. It is the last open row of the General UI PRD; after it, no Section 3 row explains a deferral, and `tests/test_acceptance.py::test_17_2_every_section_3_row_is_present_and_the_deferred_rows_say_so` asserts that every row acts.

The session opens with two display checks owed from earlier work, then presents the two decisions below with the consequential decision template and waits. Nothing is built before they are taken.

## Display checks first

Both are owed since the acceptance pass of 09-10-26 and cost two minutes each. Ask Doug to run them from a terminal in the repository with `XDG_CONFIG_HOME=/tmp/snapmock-acceptance uv run python -m snapmock`, and record each answer, quoted, in the Section 16 row it belongs to.

1. **Step B17 of notes Section 16.9** (row 36, the canvas focus frame of commit efaa830): click inside the zoom percentage box on the Main Toolbar, press Tab slowly until the focus passes the Left Tool Palette, and say whether a 2 px blue frame appears inside the canvas when the focus lands on it.
2. **Row 20, the Zoom tool** (commit 47ef98d): press Z, click on the canvas (it zooms in), then Alt+click on the canvas and say what happens (the window may move instead: Cinnamon's window manager takes Alt+left-button), then right-click on the canvas and say whether it zooms out.

## Read first, in this order

1. `docs/General-UI-Implementation.md`, revision 1.26: Section 1 (every row done); Section 5.1 (the 09-10-26 decision that put Check for Updates on the follow-up list); Section 6 (the Check for Updates deviation, which this work closes); Section 16 row 6 (the one deferred row left), rows 20 and 36 (the display checks above), and Section 16.10 (the first bullet: what the row needs); Section 18 (the follow-up that closed everything else; its Section 18.2 names the patterns a window handler follows).
2. `PRDs/SnapMock-General-UI-PRD.html`: Section 3.8 (the Help menu table: Documentation, Report a Bug, Check for Updates, About), 1.3 (never-disabled controls: a row whose requirement is unmet says which), 11.3 (Preferences: there is no update row, which decision 2 is about), 11.6 (the About dialog's version and links), 14 (accessible names), and the change log from 2.8 down to 2.5 (the 2.5 rows carry the Check for Updates decision).
3. `PRDs/SnapMock-Technical-Architecture-PRD.html`, version 1.15: Section 9.1 (the dependency policy: core functionality depends only on PyQt6, Pillow, and NumPy; `PyQt6.QtNetwork` ships inside PyQt6 and imports on this machine), Section 8 (platforms: the check must behave the same on Windows and macOS), and Section 10 (binding: every new module gets a row in the commit that creates it).
4. `snapmock/main_window.py` (`_help_check_updates`, `_help_about`, `_help_report_bug` or the row that opens `ISSUES_URL`, `_setup_help_menu` or wherever the Help rows are built, `show_status_hint`, `_require`), `snapmock/ui/unmet_requirements.py` (`check_requirements`, `show_not_available`), `snapmock/ui/about_dialog.py` (`version_info_text`, the links), `snapmock/config/constants.py` (`APP_VERSION`, `REPOSITORY_URL`, `ISSUES_URL`), `snapmock/__init__.py` (`__version__`), `snapmock/config/settings.py` (`AppSettings`, in case decision 2 adds a key), and `snapmock/capture/wayland_portal.py` for the one place the code already talks to something outside the process asynchronously, as a pattern for callbacks that arrive later.
5. `tests/test_menus.py::test_help_menu_order_and_links`, `tests/test_about_dialog.py`, `tests/test_acceptance.py::test_17_2_every_section_3_row_is_present_and_the_deferred_rows_say_so` (its last assertions are the deferral message; they change in the commit that builds the row), and `tests/conftest.py` (`unmet_messages`, `main_window`): read the test names to know what each area already asserts.

Do not write anything until all five are read.

## Starting state, verified at commit d8c5de8 on 09-10-26

- Every General UI phase, the acceptance pass, the Group and Ungroup kickoff, and the Navigation and Raster Operations follow-up are done. The suite passes 1000 tests with 13 skipped and one environmental deselection (`test_font_combo_reflects_text_item_font`); ruff and mypy are clean.
- General UI PRD 2.8, Technical Architecture PRD 1.15, Navigation and Raster Operations PRD 1.3, implementation notes 1.26.
- `snapmock.__version__`, `APP_VERSION`, and `pyproject.toml` all read `0.1.0`; no release has been published on GitHub, so the releases API returns 404 for `releases/latest` today. The work must handle that as a result, not as an error.
- Nothing in `snapmock/` makes a network request; the Wayland portal talks to D-Bus, not the network. There is no update-related setting.

## Steps, one commit each

1. **Display checks and decisions.** Record the two display answers in Section 16 rows 36 and 20 (quoted, with a verdict change if row 36 now passes). Present decisions 1 and 2 below; record the choices in a new Section 19 of `docs/General-UI-Implementation.md`, "Check for Updates", with a phase-table row in Section 1 marked in progress; bump the notes' revision.
2. **The module.** `snapmock/core/update_check.py` (Technical Architecture PRD 1.16, Section 10 row): the release endpoint for the repository, the request headers, `parse_version` (a tag with or without a leading v, into a tuple of integers; None when it does not parse), `compare` (newer, same, older), and the outcome model (a small enumeration or dataclass: newer with the tag and the release page URL, up to date, no release published, could not read the release, network unavailable, rate limited), all pure and tested without the network. Then the request itself per decision 1, behind a small object that takes the reply and emits or calls back with an outcome, so a test can feed it a canned reply.
3. **The Help row.** `MainWindow._help_check_updates` starts the check, shows "Checking for updates…" in the status bar's hint zone, and on the outcome shows one message: a newer release with an Open Release Page button (through `QDesktopServices`, as Report a Bug opens the issues page) and a Close button; up to date; no release published yet; the release could not be read; or the Section 1.3 message "Check for Updates needs a network connection" for a failed or timed-out request. A second click while a check runs shows the Section 1.3 message "Check for Updates needs the running check to finish". The acceptance test's last deferral assertion becomes a behaviour assertion. Tests: every outcome through a canned reply, the buttons and the opened URL, the status hint, the second click, and the accessible names of any dialog built.
4. **Close-out.** General UI PRD 2.9: the row built, the two decisions, every silence decided, the two display checks. Technical Architecture PRD 1.16 if not already bumped. Implementation notes: Section 19 complete with what was built and the deviations, Section 16 row 6 gains "fixed since" with the commit hash, Section 16.10's first bullet closed, Section 6's Check for Updates deviation closed, Section 7 the tests, the phase-table row done, the revision bumped, and the next required step stated: the General UI PRD has no open row; the next kickoff belongs to another PRD (the Numbered Steps, Stamps, and Emoji work, or the Windows backend on Windows), and the acceptance pass's row 35 (Orca) stays as recorded.

Each commit is ruff-clean and mypy-strict-clean with the suite passing. Run the full suite as `QT_QPA_PLATFORM=offscreen uv run pytest -q -o faulthandler_timeout=120 --deselect tests/test_property_panel.py::test_font_combo_reflects_text_item_font` to a log file in the background: it takes about fourteen to eighteen minutes, and a modal dialog left open by a test hangs the run, and the dump names the test. The last two kickoffs ran each commit's suite in a scratch `git worktree` with `python -m pytest` from the worktree's root, so the next step's edits did not disturb the run; the same works here. A test must never reach the real network: every test feeds the check a canned reply or a failure.

## Decisions to surface

Apply the two-part test from the global guidance. Two decisions are expected to pass it; present both with the consequential decision template before step 2 and wait.

- **1. How the request is made.** Option A, `QNetworkAccessManager` from `PyQt6.QtNetwork`: asynchronous on the Qt event loop, no thread, the reply arrives as a signal, a timeout through `setTransferTimeout`, and no new dependency, since QtNetwork ships inside the PyQt6 wheel already installed (Technical Architecture PRD 9.1 holds). Its cost is a second Qt module in the import footprint and TLS through Qt's own backend, which on some Linux installs lacks OpenSSL and reports a failure the message must treat as "network unavailable". Option B, `urllib.request` from the standard library on a worker `QThread`: no Qt networking, the system's TLS; its cost is a thread that must not touch widgets, a signal to hand the outcome back, and a request that cannot be cancelled once started. Recommendation: A; it is the shape the rest of the code has (signals, no threads), and the TLS caveat is one outcome the message already covers.
- **2. Whether the check also runs at startup.** Option A, manual only: the Help row is the only trigger, as Section 3.8 lists it and as Section 11.3 lists no preference; nothing leaves the machine unless the user asks. Option B, a Preferences > General row "Check for updates at startup" (off by default) that runs the check once per launch a few seconds after the window shows and reports only when a newer release exists; its cost is a network request the user did not ask for on each launch it is on, a new settings key, a new Preferences row the PRD does not list (a 2.9 row), and a message that can appear over whatever the user is doing. Recommendation: A; the PRD asks for the row alone, and a startup check can be added by a later PRD row when a release exists to find.

Everything else follows the PRDs; where they are silent, decide, note it under the notes' Section 19 and the PRD 2.9 rows, and continue. Seven silences are known:

- Which endpoint: `https://api.github.com/repos/dbower44022/Snagit_FOSS/releases/latest`, which excludes drafts and pre-releases; headers `Accept: application/vnd.github+json` and `User-Agent: SnapMock/<version>`; a 10 second timeout. Recommended as stated; the repository path is derived from `REPOSITORY_URL`, not written twice.
- What "newer" means: the release's `tag_name` with an optional leading v parsed into integers and compared as a tuple with `snapmock.__version__` parsed the same way; a tag that does not parse is "the release could not be read"; a release older than or equal to the running version is "up to date". Recommended as stated.
- What a 404 means: "No release has been published yet." with the repository page offered, since the repository has no release today. Recommended as stated.
- What a 403 or 429 means: rate limited; "GitHub declined the request; try again later." Recommended as stated.
- What the newer-release message offers: the tag, the running version, and an Open Release Page button that opens the release's `html_url`; no download inside the application. Recommended as stated.
- Whether the outcome is remembered: no; nothing is written to settings under decision 2 option A. Recommended as stated.
- Where the message is shown: a `QMessageBox` from the main window, information icon, with `apply_default_names` if a dialog of its own is built instead; the status hint returns to the active tool's hint when the message closes. Recommended as stated.

## Standards that apply

- Terminology Precision, Writing Register, and Reply Format from the global guidance apply to every reply and to the documents.
- Every new module gets a row in Technical Architecture PRD Section 10 in the commit that creates it.
- Departures from any PRD are recorded in that PRD's change log with a version bump, not only in code comments.
- No control is disabled (General UI PRD 1.3); a row whose requirement is unmet says which, through `check_requirements`.
- Every new control gets an accessible name as it is created (`apply_default_names` on any new dialog).
- `uv run ruff check .`, `uv run ruff format .`, `uv run mypy snapmock`, and `uv run pytest` must pass before each commit, with `QT_QPA_PLATFORM` set to `offscreen` for pytest.
- No new runtime dependency without surfacing it as a decision; decision 1 is that decision.
- No test touches the network.
- Commit messages end with the attribution block the session provides.

## When the work is complete

Update the phase table in `docs/General-UI-Implementation.md`, bump its revision, add a change-log row, and state the next required step: the General UI PRD has no open row, so the next kickoff is chosen from the other PRDs (the Numbered Steps, Stamps, and Emoji work is the one the RasterRegion layer type and the StampItem registry gap are waiting on; the Windows backend kickoff waits for a Windows machine).

---

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-10-26 14:40 | Claude (Claude Code) | Initial kickoff prompt: starting state at commit d8c5de8, two display checks owed, the read list, four steps, two decisions (how the request is made; whether the check runs at startup), seven known silences. |
