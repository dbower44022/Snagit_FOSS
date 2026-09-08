# General UI Implementation Notes

Last Updated: 09-08-26 16:30 · Revision 1.4

Implements the SnapMock General User Interface PRD (version 1.9, `PRDs/SnapMock-General-UI-PRD.html`) in the eight phases defined by `docs/General-UI-Implementation-Kickoff-Prompt.md`. A session pasting that prompt starts at the first phase not marked done in Section 1.

## 1. Phase status

| Phase | Scope | Status | Commits |
|---|---|---|---|
| 0 | Inventory and notes | Done | 3972f47 |
| 1 | Menus, shortcuts, help, and window | Done | 9073edc to c7b88ba |
| 2 | Export | Done | 8a34cad to c5ddfe5 |
| 3 | Theme and Preferences | Done | a3d19a2 to 4e15e66 |
| 4 | Toolbars and status bar | Not started | |
| 5 | Canvas | Not started | |
| 6 | Panels and colour picker | Not started | |
| 7 | Tool themes and presets | Not started | |
| 8 | First run, accessibility, responsive behaviour | Not started | |

Phase 0 was verified against the repository at commit `a198744` on 09-07-26. The working tree also carried uncommitted Basic Shape Annotation Tools work in `snapmock/items/` and `tests/test_items.py`; it was left untouched and is not part of this inventory.

## 2. Verified inventory, by PRD section

Each entry states what the code does today. "Present" means the PRD is satisfied and the phase leaves the code alone. "Departs" means the code does something different from the PRD. "Missing" means nothing implements it. The phase that owns each gap is named in brackets.

### 2.1 Section 1.3, never-disabled controls

Departs. The kickoff prompt's inventory said one call disables a control; the count is higher. `MainWindow._update_menu_states` disables seven actions and two submenus (Arrange z-order, Flip, Align to Canvas Center, the Align and Distribute submenus, Layer Move Up/Down/Top/Bottom, Delete Layer, Merge Down). The Recent Files placeholder row is disabled. `snapmock/ui/context_menus.py` disables seventeen actions and submenus across the canvas, item, and layer context menus. `tests/test_menus.py` asserts the disabled state in two tests, which Phase 1 rewrites. The Preferences dialog disables the Autosave interval spinbox when Autosave is off and Keep Running in Tray when the tray is off; these are dependent settings inside a dialog and are recorded as a Deviation candidate for Phase 3 rather than a Phase 1 audit item. No control anywhere shows the PRD's unmet-requirement message. [Phase 1]

### 2.2 Section 2, main window layout

- Zones. Menu bar, one top toolbar (the tool palette, named "Tools"), the Tool Options Bar, the canvas (document tabs over one view per document), Layer Panel and Property Panel on the right, the Library Panel at the bottom, status bar. Present, except: no Main Toolbar (the top toolbar is the palette, and the Screen Capture Group 0 button sits at its left end) and no Left Tool Palette. [Phase 4] The Capture button moves into the Main Toolbar when the Main Toolbar exists; the Screen Capture implementation notes Section 1.5 describe the button. [Phase 4]
- Default proportions. The window opens at 1200 by 800, not 80 percent of the screen. The Layer Panel is sized to its row count; the Library Panel to 250 px. Departs. [Phase 1 for window size; Phase 4 for toolbar heights]
- Docking. Layer Panel and Property Panel allow the left and right areas only; the PRD allows bottom as well. Float, tab, close, reopen via the View menu, and QSettings persistence of geometry and state are present. Reset Layout is missing. [Phase 1]
- Window title. Code writes `*Name — SnapMock` with an em dash; the PRD pattern uses a hyphen. The dirty asterisk and "Untitled" are present. [Phase 1]

### 2.3 Section 3, menu bar

Menu order in code: File, Edit, View, Image, Layer, Arrange, Tools, Library, Capture, Help. The PRD orders Layer before Image; `tests/test_menus.py` asserts the current order. [Phase 1]

**File.** Present: New, Open, Save, Save As, Import Image, Export, Export Quick, Print, Preferences, Quit, plus Close (Ctrl+W) from the Library PRD. Departs: the recent-files submenu is named "Recent Files" not "Open Recent", sits after Print rather than after Open, and has no Clear Recent row; Export Quick is labelled "Export Quick PNG"; Export opens a save-file dialog rather than the Export dialog; Export Quick writes beside the current file or asks for a path, with no last-used settings; Print is a "coming soon" message box. [Phase 1 for labels, order, Clear Recent; Phase 2 for Export and Export Quick; Print is decision 6]

**Edit.** Present: Undo, Redo, Cut, Copy, Paste, Paste in Place, Delete, Duplicate, Select All, Select All Layers, Deselect. Departs: Undo and Redo do not show the action name; Delete is bound to Delete only, not Backspace, in the menu (the Select tool handles Backspace itself); Select All selects every item on every layer, the same as Select All Layers, where the PRD limits it to the active layer. Missing: Select All Text (Ctrl+T), Find/Replace Color. [Phase 1]

Bug found. Redo and Deselect are connected at construction to the first document's command stack and selection manager (`self._scene.command_stack.redo`, `self._selection_manager.deselect_all` evaluate the property once). After a tab switch both act on the wrong document. Every other Edit action goes through a method that reads the active document. [Phase 1]

**View.** Present: Zoom In (bound to Ctrl+= which Qt treats as Ctrl++), Zoom Out, Fit to Window, Zoom to 100% (labelled "Actual Size"), Zoom to Selection, Show Grid, Snap to Grid, Show Rulers, four panel toggles (labelled "Show Toolbar", "Show Options Bar", "Show Layers Panel", "Show Properties Panel"), the Library Panel toggle, Next Tab and Previous Tab. Missing: Show Crosshairs, Show Guides, Snap to Guides, Lock Guides, Clear All Guides, Show Tool Palette, Show Status Bar, Reset Layout, Dark Mode. [Phase 1 for labels, Show Status Bar, Reset Layout; Phase 3 for Dark Mode; Phase 4 for Show Tool Palette; Phase 5 for guides and crosshairs]

**Layer.** Every row is present with its shortcut; Delete Layer carries Ctrl+Shift+Delete, which the PRD does not assign. Departs: Duplicate Layer adds an empty layer named "copy" and does not copy items; Delete Layer does not confirm when the layer has items; Rename Layer opens an input dialog rather than editing inline; Merge Down, Merge Visible, and Flatten All are "coming soon" message boxes. Whether the three merge actions belong to this implementation is raised as a Phase 1 decision (Section 5). [Phase 1 for confirm and duplicate; inline rename with the Layer Panel in Phase 6]

**Image.** Present: Resize Canvas, Resize Image, Rotate 90° CW and CCW, Flip Horizontal and Vertical. Departs: Crop to Canvas removes items outside the canvas instead of activating the crop tool; Auto-Trim is a "coming soon" message box; row order differs from the PRD (Crop to Canvas is third, not first). [Phase 1 for order; Crop to Canvas and Auto-Trim are in the Phase 1 decision of Section 5]

**Arrange.** Present: the four z-order rows, Flip Horizontal and Vertical, Align to Canvas Center, and the six Align and two Distribute rows as two submenus rather than flat rows. Missing: Group, Ungroup. [Decision 4; submenu shape is noted under Deviations when Phase 1 reaches it]

**Tools.** All 18 registered tools appear as checkable rows with the active tool checked. Departs: six shortcuts differ from PRD Section 3.7, and the tool PRDs agree with the General UI PRD, not with the code (Line: PRD U, code L; Callout: PRD B, code C; Blur: General UI PRD Z, Blur PRD D, code B; Crop: PRD C, code X; Freeform selection: PRD L, code Shift+M; Zoom: PRD Ctrl+Space hold, code Z). Arc and Polygon are not registered tools; they belong to the Basic Shape Annotation Tools PRD. No icons. Missing: Tool Themes and the Active Theme label. [Shortcuts are a Phase 1 decision, Section 5; Phase 7 for themes]

**Help.** Present as rows: Welcome (labelled "Welcome", not "Welcome / Getting Started"), Documentation, Keyboard Shortcuts, Report a Bug, Check for Updates, About. Welcome, Keyboard Shortcuts, and Check for Updates are "coming soon" message boxes. Documentation opens `snapmock.org/docs` and Report a Bug opens `github.com/snapmock/snapmock/issues`; both are placeholders, not `dbower44022/Snagit_FOSS`. About shows name, version, and two sentences; no build date, licence, links, credits, or Copy Version Info. The repository has no licence file and `pyproject.toml` declares no licence, so the About dialog cannot name one until Doug decides (Section 5). [Phase 1; Welcome in Phase 8; Check for Updates is out of scope until decided]

**Library and Capture** menus come from their own PRDs and are not part of this inventory.

### 2.4 Section 4, Main Toolbar

Missing. The top toolbar is the tool palette. `ZoomDropdown` in `snapmock/ui/toolbar.py` implements the editable zoom combo box but nothing instantiates it. [Phase 4]

### 2.5 Section 5, Tool Options Bar

Departs. `ToolOptionsBar` adds a label and calls each tool's `build_options_widgets`. Six tools override it (Select, Text, Callout, Crop, Raster Select, Lasso Select); the twelve others show only the label. No preset dropdown, no shared control set. The shape and arrow tools keep their options in the Property Panel by their own PRDs; Phase 4 decides per tool which options the bar shows. [Phase 4; preset dropdown Phase 7]

### 2.6 Section 6, canvas area

- Pasteboard. Present, colour `#505050`. The PRD gives `#808080` in Section 6.1 and `#E0E0E0` (light) and `#1E1E1E` (dark) in Section 13; this PRD inconsistency is recorded in Section 4 below. The pasteboard colour is not configurable. [Phase 3 reads it from the theme manager]
- Canvas background. Empty-canvas prompt present with slightly different wording (no "(Ctrl+V)"). Checkerboard present at 8 px in white and `#CCCCCC`. Border and drop shadow present. Canvas colour is a scene property with a Property Panel swatch. [Present; wording Phase 5]
- Rulers. Present with adaptive tick spacing and a cursor marker. Colours are constants, not theme values. [Phase 3]
- Grid. Present at 20 percent opacity. Departs: major lines every 10 units, PRD says 5; minor lines hide when screen spacing drops below 4 px rather than below 200 percent zoom. [Phase 5]
- Guides. Missing entirely: no creation from rulers, move, delete, snap, lock, appearance, or persistence. [Phase 5; persistence is decision 3]
- Crosshairs. Missing. [Phase 5]
- Cursor table (Section 6.6). Present: arrow for Select, crosshair for every drawing tool and Crop, I-beam for Text, open and closed hand for Pan and middle-button drag, directional resize cursors on handles. Missing: open hand when hovering a selectable item, closed hand while dragging, rotation cursor on the rotate handle (arrow today), I-beam with highlight over an existing text item, crosshair with dotted square for raster selection, eyedropper cursor (crosshair today), magnifier cursors for the Zoom tool (crosshair today), forbidden cursor over a locked layer's item, copy cursor during external file drag. [Phase 5]

### 2.7 Section 7, Layer Panel

Departs. `LayerPanel` is a `QListWidget` of layer names with "+" and "-" buttons, a context menu, and active-row tracking. Missing: visibility and lock toggles in the row, thumbnails, opacity indicator, 48 px row, inline rename, drag reorder with insertion line, Ctrl+click multi-selection, hover highlight, the bottom action bar (Duplicate, Merge Down, blend mode dropdown), badges, the 70 percent locked-row treatment, the 200 px minimum width. [Phase 6]

### 2.8 Section 8, Property Panel

Present: collapsible sections with persisted collapse state; Transform (X, Y, W, H, Rotation, Flip H, Flip V); Appearance (stroke colour, stroke width slider and spinbox, fill colour, one opacity); Text (font, size, bold, italic, underline, colour, alignment); a Text Box section beyond the PRD; Item Info (type, layer dropdown, locked checkbox); Canvas (width and height as read-only labels, canvas colour). The tool-defaults mode when a creation tool is active is present. The kickoff prompt listed the Item Info layer dropdown and item lock as missing; both exist.

Missing or departing: chain-link aspect lock; stroke colour and fill colour hex inputs; Stroke Style dropdown; Fill Opacity and Stroke Opacity as two controls; Blend Mode; the whole Shadow section; Font Weight and Font Style dropdowns (checkboxes today); Line Spacing; Background Fill in the Text section (it is in the Text Box section); editable canvas size, Pasteboard Color, Grid Size, Snap to Grid, Canvas DPI in the Canvas section; mixed-value indicators for multi-selection (text formatting has partial mixed handling; nothing else does). [Phase 6]

### 2.9 Section 9, status bar

Departs. Zones present: tool hint, cursor position (formatted "Cursor: x, y"), zoom (formatted "Zoom: 100%", not clickable). Missing: selection size, canvas size, memory usage, fixed zone widths. [Phase 4; memory is decision 2]

### 2.10 Section 10, context menus

Present with the PRD's rows in the PRD's order for all three menus. Departs: Canvas Properties shows a "coming soon" message box instead of opening the Property Panel's canvas section; every conditional row uses `setEnabled` (Section 2.1). [Phase 1 for the audit; Canvas Properties with the Property Panel in Phase 6]

### 2.11 Section 11, dialogs

- Color Picker (11.1). Departs. `ColorPicker` opens `QColorDialog` with alpha, plus a "∅" toggle button beside the swatch. PRD version 1.6 removed that toggle and placed a Transparent option inside the popover. Recent colours, saved colours, HSL inputs, eyedropper button, and live preview are missing. [Phase 6]
- Export (11.2). Missing. [Phase 2]
- Preferences (11.3). Departs. One page of four group boxes: General (autosave on and interval), View (grid visible, grid size, rulers, snap), Library, Capture. The sidebar layout and the settings of the Appearance, Canvas & Grid, Tools, and Performance categories are missing; General lacks language, recent files count, default canvas size and colours, and confirm-before-delete. Library and Capture stay as categories of the rebuilt dialog. [Phase 3]
- Resize Canvas (11.4) and Resize Image (11.5). Present per the Navigation and Raster Operations implementation. Not re-audited here.
- About (11.6). Departs, see Help above. [Phase 1]
- Unsaved Changes (11.7). Departs: text is `Save changes to "Name" before closing?` with Save, Discard, Cancel; the PRD wording and "Don't Save" differ, and there is no canvas preview. [Phase 1 for wording; Phase 8 for the preview]
- Tool Themes (11.8) and Manage Presets (11.9). Missing. [Phase 7]
- Keyboard Shortcuts (Help menu). Missing. [Phase 1]

### 2.12 Section 12, keyboard shortcuts

Present: Ctrl+wheel zoom, middle-button pan, Space temporary pan, arrow nudge by 1 and Shift+arrow by 10, Shift and Ctrl selection modifiers, Shift and Alt drawing modifiers in the Select tool. Missing: Home and End pan, Tab and Shift+Tab selection cycling, Alt momentary eyedropper. The shortcut map lives in `snapmock/config/shortcuts.py` as the PRD says. [Phase 1]

### 2.13 Section 13, theming

Missing. No theme manager, no style sheets, `resources/themes/` holds only `.gitkeep`. Fifteen scattered `setStyleSheet` calls (main window separator, ruler corner, Preferences hint labels, the colour picker toggle, and others) carry hard-coded colours. Canvas rendering reads colours from `config/constants.py`. The Screen Capture overlay takes its accent from the palette highlight role and is waiting for the theme manager. [Phase 3]

### 2.14 Section 14, accessibility

Missing. No `setAccessibleName` or `setAccessibleDescription` anywhere. Tab order, focus outline, and status-bar announcements have not been set. [Phase 8]

### 2.15 Section 15, responsive behaviour and window management

Missing: minimum window size, panel collapse thresholds, multi-monitor recovery of floating panels. Session persistence present: window geometry and state, dock layout, panel and toolbar visibility, recent files, grid, snap, and ruler toggles. Missing from persistence: theme, last-used export settings, last-used tool and its options, zoom per recent project. `AppSettings.zoom_level` exists and is never read or written. [Phase 1 for minimum size and last-used tool; Phase 2 export settings; Phase 3 theme; Phase 8 collapse and monitors]

### 2.16 Section 16, first run

Missing. No welcome panel and no first-launch detection; Help > Welcome is a message box. Default tool configuration matches the PRD except the theme (no theme) and rulers (hidden, matches). [Phase 8; New Blank Canvas card is decision 5]

## 3. Corrections to the kickoff prompt's inventory

- Never-disabled controls: about twenty-six `setEnabled` calls across `main_window.py` and `context_menus.py`, not one, and two tests assert them.
- Property Panel Item Info: the layer dropdown and item lock exist. Phase 6's remaining Property Panel work is the list in Section 2.8.
- Tools menu: six shortcut letters conflict with the PRD and with the tool PRDs. Not listed in the prompt.
- Layer and Image menus were listed as "close to the PRD"; five of their actions are stubs or do something else (Section 2.3).
- Edit menu: Redo and Deselect act on the first document after a tab switch. A bug, not a gap.
- The zoom dropdown class exists but is unused; the prompt implied it was wired.

## 4. PRD inconsistencies found during the inventory

Recorded here so Phase 1 can propose change-log rows for the General UI PRD; none is resolved by this note.

- Pasteboard colour: Section 6.1 says `#808080`; Section 13.2 says `#E0E0E0` for the light theme and Section 13.3 `#1E1E1E` for the dark theme. The theme tables should win once the theme manager exists.
- Blur tool shortcut: Section 3.7 says Z; the Blur, Highlighter, and Eyedropper PRD says D.
- Tool count: Section 3.7 lists 20 tools including Arc and Polygon; Section 17.3 says the palette shows "all 18 tools".
- Section 17.4 cites "Section 6.5" for the cursor table; the table is Section 6.6 after the Guides insertion.
- Section 2.1 says the status bar is toggleable and Section 3.3 lists Show Status Bar; both are consistent, but Section 15.4 does not list status bar visibility among persisted toggles. Treated as covered by "toolbar and panel visibility toggles".

## 5. Decisions

### 5.1 Taken at the start of Phase 1 (09-08-26)

| Decision | Choice | Effect |
|---|---|---|
| Stubbed Layer and Image rows | B | Crop to Canvas and Auto-Trim built in Phase 1; Merge Down, Merge Visible, Flatten All deferred to a Navigation and Raster Operations follow-up with a General UI PRD change-log row. |
| Group and Ungroup | B | Own kickoff after Phase 8; rows present and explain the deferral. |
| Print | A | Built in Phase 1 through the system print dialog. |
| Tool shortcut letters | B | The shipped map stays; departure rows in the General UI, Text and Callout, Blur, Navigation, and Basic Shape PRDs. |
| Licence | A | MIT. LICENSE file, project metadata, and the About dialog. |

Taken at the start of Phase 3 (09-08-26):

| Decision | Choice | Effect |
|---|---|---|
| Icon set | A, Tabler Icons | The glyphs SnapMock uses are vendored from Tabler Icons v3.46.0 under `snapmock/resources/icons/tabler/` with the MIT licence file and a README; `snapmock/ui/icons.py` maps every tool, menu row, and panel button to a glyph; the About dialog credits the set. |

The kickoff's remaining decisions (memory zone, guide persistence, welcome-panel card) are presented at the start of the phase that needs them.

### 5.2 As raised by Phase 0

The kickoff prompt's six decisions stand. The inventory adds three that pass the two-part test and must be presented with the consequential decision template before Phase 1 writes code:

1. **Tool shortcut letters.** Realign `config/shortcuts.py` to the PRDs (Line U, Callout B, Crop C, Freeform selection L, Zoom Ctrl+Space hold, Blur to whichever of Z or D the PRD correction picks), or keep the code's letters and record a departure in the General UI PRD and the three tool PRDs. Realigning changes what every existing user presses; keeping them means four PRDs carry a deviation row.
2. **Licence for the About dialog.** The PRD says "MIT or Apache 2.0"; the repository has neither a licence file nor a `license` field. About cannot show licence text until one is chosen. Phase 1 builds the dialog with a placeholder line if the decision is deferred.
3. **Ownership of the raster-composite actions.** Merge Down, Merge Visible, Flatten All, Auto-Trim, and Crop to Canvas as "activate the crop tool" are General UI menu rows whose behaviour belongs to the layer compositing and raster subsystems. Options: implement them in Phase 1 as part of "every menu item present and working", or defer them to a Navigation and Raster Operations follow-up with a change-log row in the General UI PRD.

## 6. Deviations from the PRD

Each has its change-log row in `PRDs/SnapMock-General-UI-PRD.html` version 1.7 (Phase 1), 1.8 (Phase 2), or 1.9 (Phase 3) unless the entry says otherwise.

- **Tool shortcut letters** (Section 3.7). Six letters differ from the PRD tables by decision; rows in all five PRDs (the Basic Shape PRD's row for Line, PRD U and shipped L, followed once that file's other edits were committed).
- **Merge Down, Merge Visible, Flatten All** (Section 3.4). Deferred; the rows check their requirement, then say the feature is not available yet.
- **Group and Ungroup** (Section 3.6). Deferred to their own kickoff; rows present with shortcuts.
- **Align and Distribute as submenus** (Section 3.6). The PRD lists eight flat rows; the menu keeps two submenus in the PRD's position and order.
- **Check for Updates** (Section 3.8). Present; says it is scheduled for a later phase. No phase owns it yet.
- **Show Tool Palette** (Section 3.3). Toggles the existing top toolbar, which is the tool palette until Phase 4 builds the Main Toolbar and moves the palette to the left edge. Show Main Toolbar arrives with Phase 4. Not recorded in the PRD: it is an interim state, not a departure.
- **Last-used tool option values** (Section 15.4). Phase 1 persists the tool id only; option values persist with the preset work of Phase 7.
- **Select All Text batch changes** (Section 3.2). Phase 1 selects the text-containing items; applying a font, size, or colour to the whole selection at once arrives with the Property Panel's multi-selection behaviour in Phase 6 (Section 8.6).
- **Preferences dependent controls** (Section 1.3). Resolved in Phase 3: Auto-save is one spinbox where 0 means disabled, and Keep running in tray stays editable while the tray is off.
- **Pasteboard colour** (Sections 6.1, 13.2, 13.3). The theme tables win: #E0E0E0 light, #1E1E1E dark. Preferences offers an override that follows the theme by default. The PRD's Section 18 issue is closed.
- **Theme constants and palette** (Section 13.4). Each style sheet opens with `@name: value;` constants that the theme manager substitutes into the rules and reads for canvas rendering; a matching QPalette is applied beside the sheet so style-drawn parts follow the theme. The base widget style stays the platform default.
- **Theme colours beyond the tables** (Section 13). Ruler, canvas border and shadow, checkerboard, guide, crosshair, input, and tooltip colours are defined per theme in the style sheet constants; the PRD tables leave them to the implementation.
- **Preferences rows without a consumer yet** (Section 11.3). Language (English only), Snap tolerance, Guide color and opacity, and Thumbnail update delay are stored; guides use theirs in Phase 5, layer thumbnails in Phase 6, translation is unscheduled. Freehand smoothing is pushed into the freehand tool's creation defaults for the Phase 4 Tool Options Bar.
- **Preferences view toggles** (Section 11.3). Show grid, Show rulers, and Snap to grid are no longer in the dialog: they are View menu toggles, and the PRD's category list does not carry them.
- **Follow-theme states** (Section 11.3). Grid color, Grid opacity, the checkerboard colours, and the pasteboard colour default to the theme value and keep following the theme until set; the PRD lists fixed defaults.
- **Library variant of the Export dialog** (Section 11.2). No Export region group, since a file that is not open in a tab has no selection or visible area; a SnapMock Project format that copies the file, from Library PRD 7.1. With Apply to All unchecked the dialog reopens per file after the first, pre-filled with the directory (Library PRD 1.2 row).
- **SVG Embed raster images unchecked** (Section 11.2). Raster regions and stamps are omitted so the file is vector-only; the PRD does not define the unchecked output and the SVG generator cannot link external files.
- **SVG and PDF preview** (Section 11.2). The preview is the flattened raster of the region; the size estimate encodes the real export in memory (PDF through a temporary file).
- **Export Quick destination** (Section 3.1). Beside a saved non-Library document as `.png`, otherwise the last-used PNG directory under the display name; overwrites; the path is shown in the status bar. The PRD names the settings but not the destination.
- **Momentary eyedropper** (Section 12.2). Alt switches to the eyedropper and back, but the eyedropper's picked colour has no consumer until Phase 4 builds its options bar (Apply to Stroke / Apply to Fill).

## 7. Tests

Phase 3 adds `tests/test_theme.py` (26 tests: the two theme files define every constant and the Section 13 table values, constant substitution and the two parse errors, the manager's default, live dark switch with palette and sheet, no re-apply on the same mode, System following the style hint, UI font size, icon size, View > Dark Mode reflecting and persisting the mode, the view's pasteboard and grid pens and checkerboard tile reading the theme and its overrides, handle recolouring, the capture accent, every named icon file existing beside the licence, icon rendering and recolouring, the palette's icon-only buttons and tooltips, icon size, and menu icons) and rewrites `tests/test_preferences_dialog.py` (17 tests: category order and page switching, no disabled control, the defaults of every page, stored values shown, changed keys only, and the application of General, Performance, Appearance, Canvas & Grid, and Tools changes including tool defaults at startup and the Delete Layer confirmation preference). `tests/test_capture/test_preferences.py` now expects Keep running in tray to stay enabled. At the close of Phase 3 the suite passed 686 tests with 13 skipped and one environmental deselection (`test_font_combo_reflects_text_item_font`).

Phase 2 adds `tests/test_export_dialog.py` (17 tests: default path and format switching, custom DPI, the unmet-requirement messages for a missing path and for Selection Only without a selection, per-format persistence and restore, the Library variant's controls, File > Export and Export Quick through the dialog, the Library batch and its display-name targets, the SnapMock Project copy, Export Quick from the panel, the preview thumbnail, its debounce, and the size estimate) and ten tests to `tests/test_io/test_exporter.py` (settings round trip and tolerant load, region resolution, selection rectangle, PNG DPI and colour depth and transparency, JPEG quality, SVG viewbox and raster embedding, PDF page sizes, the project-file copy, byte-size text, `AppSettings` export keys). At the close of Phase 2 the suite passed 655 tests with 13 skipped and one environmental deselection (`test_font_combo_reflects_text_item_font`).

Phase 1 adds `tests/test_layer_menu_actions.py`, `tests/test_shortcuts_dialog.py`, `tests/test_about_dialog.py`, `tests/test_window_layout.py`, `tests/test_find_replace_color.py`, and `tests/test_navigation_keys.py`; extends `tests/test_menus.py`, `tests/test_context_menus.py`, `tests/test_documents.py`, `tests/test_app.py`, and `tests/test_io/test_exporter.py`; and adds the `unmet_messages` fixture to `tests/conftest.py`, which captures the never-disabled message instead of showing it. At the close of Phase 1 the suite passed 628 tests with 13 skipped and one environmental deselection (`test_font_combo_reflects_text_item_font`); `test_main_window_default_size` passes again now that the window has a minimum size.

Phase 0 adds no tests. On 09-07-26 the working tree (commit `a198744` plus the uncommitted Basic Shape work) was ruff-clean and mypy-strict-clean, and the suite passed 590 tests with 13 skipped, with the two known environmental failures deselected: `test_main_window_default_size` and `test_font_combo_reflects_text_item_font`.

## 8. What Phase 1 built

In commit order: the Redo and Deselect binding fix; the never-disabled audit with `snapmock/ui/unmet_requirements.py`; the menu bar aligned to Section 3 (order, labels, Open Recent with Clear Recent, Undo and Redo action names, Backspace for Delete, Show Status Bar, Group and Ungroup rows, Help labels and real links); Duplicate Layer copying items, Delete Layer confirming, Crop to Canvas as the crop tool, Auto-Trim; Print; the Keyboard Shortcuts dialog; the About dialog and the MIT licence; window management (object names so the layout persists, minimum size, 80 percent default, Reset Layout, the title pattern, the Unsaved Changes wording, the last-used tool); Select All Text and Find/Replace Color; Home and End, Tab cycling, the Alt eyedropper; and the PRD change-log rows. Technical Architecture PRD 1.5 lists the four new modules under `ui/`.

## 9. What Phase 2 built

In commit order: the export engine (`ExportSettings`, `ExportFormat`, `ExportRegion`, `PdfPageSize`, `export_scene`, `resolve_region`, `selection_rect`, `estimate_export_size`, `format_byte_size` in `snapmock/io/exporter.py`; `RenderEngine.render_region` takes a scale for DPI; `AppSettings` keeps the last-used settings and directory per format and the last format); the Export dialog (`snapmock/ui/export_dialog.py`) with its format pages, region radios, output path or directory, Apply to All, preview and size estimate, and the never-disabled Export button, wired to File > Export, Export Quick (PNG), and the Library panel's Export... and Export Quick (PNG) with the progress dialog; and the preview and size-estimate tests. Technical Architecture PRD 1.6 lists the new module. The Library PRD is at 1.2 and its implementation notes at 1.2 for the delivered variant.

## 10. What Phase 3 built

In commit order: the theme manager (`snapmock/core/theme_manager.py`: `ThemeMode`, `ThemeColors`, `parse_theme_file`, `ThemeManager` with `set_mode`, `apply`, `icon`, `set_icon_size`, `set_ui_font_size`, the `theme_changed` and `icon_size_changed` signals, and the process-wide `theme_manager()` and `current_theme()`), the two style sheets under `snapmock/resources/themes/`, the theme, icon-size, and UI-font-size settings, and View > Dark Mode; canvas rendering from the theme (the view's pasteboard, shadow, border, empty-canvas text, checkerboard, and grid pens with their Preferences overrides; rulers; transform handles with `apply_theme`; the crop overlay and capture overlay accents; hard-coded style sheets replaced by theme roles; the superseded colour constants removed from `config/constants.py`); the icon set (`snapmock/resources/icons/tabler/` with LICENSE and README, `snapmock/ui/icons.py`, icon-only palette buttons with tooltips, menu and tray icons, Layer Panel buttons, the About credit); and the Preferences dialog rebuilt as sidebar categories with every Section 11.3 setting in `AppSettings` and wired (view preferences per document, tool defaults through `_apply_tool_defaults`, `CommandStack.set_limit`, `LibraryManager.create_blank` taking a colour, `PropertyPanel.refresh_tool_defaults`). Technical Architecture PRD 1.7 lists `core/theme_manager.py`, `ui/icons.py`, and the resource files.

**Next required step:** Phase 4, Toolbars and status bar, in a new session pasting `docs/General-UI-Implementation-Kickoff-Prompt.md`. Phase 4 opens by presenting decision 2 (memory usage zone: a runtime dependency or platform calls in one module) with the consequential decision template and waiting.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.4 | 09-08-26 16:30 | Claude (Claude Code) | Phase 3 done: phase table, the icon-set decision (Section 5.1), seven deviations (Section 6), tests (Section 7), build summary and next step (Section 10). |
| 1.3 | 09-08-26 13:45 | Claude (Claude Code) | Phase 2 done: phase table, four deviations (Section 6), tests (Section 7), build summary and next step (Section 9). |
| 1.2 | 09-08-26 13:21 | Claude (Claude Code) | Basic Shape PRD shortcut row delivered; the owed item is closed. |
| 1.1 | 09-08-26 11:23 | Claude (Claude Code) | Phase 1 done: phase table, decisions taken (Section 5.1), ten deviations (Section 6), tests (Section 7), build summary and next step (Section 8). |
| 1.0 | 09-08-26 00:10 | Claude (Claude Code) | Phase 0: verified inventory by PRD section, corrections to the kickoff inventory, PRD inconsistencies, three added Phase 1 decisions, empty deviations list. |
