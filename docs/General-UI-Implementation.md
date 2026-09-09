# General UI Implementation Notes

Last Updated: 09-09-26 20:45 · Revision 1.10

Implements the SnapMock General User Interface PRD (version 2.3, `PRDs/SnapMock-General-UI-PRD.html`) in the eight phases defined by `docs/General-UI-Implementation-Kickoff-Prompt.md`. A session pasting that prompt starts at the first phase not marked done in Section 1.

## 1. Phase status

| Phase | Scope | Status | Commits |
|---|---|---|---|
| 0 | Inventory and notes | Done | 3972f47 |
| 1 | Menus, shortcuts, help, and window | Done | 9073edc to c7b88ba |
| 2 | Export | Done | 8a34cad to c5ddfe5 |
| 3 | Theme and Preferences | Done | a3d19a2 to 4e15e66 |
| 4 | Toolbars and status bar | Done | 4ddcf86 to a9ca773, then this close-out commit |
| 5 | Canvas | Done | 155f908 to 620da91, then this close-out commit |
| 6 | Panels and colour picker | Done | 485d496 to 0a488d1, then this close-out commit |
| 7 | Tool themes and presets | Done | 443ce55 to 2c3cc23, then this close-out commit |
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

### 3.1 Corrections found at the start of Phase 6

Verified at commit a180b07 on 09-09-26 and recorded in revision 1.1 of the Phase 6 kickoff prompt: the Property Panel's section collapse state is not persisted (Section 2.8 above said it was); a per-layer render exists in `RenderEngine.render_layer_region`; layer visibility and layer opacity have no effect on rendering, only on the Select tool's hit testing; the Layer Panel's own two buttons bypass the command stack; the Property Panel writes the canvas background colour and the text alignment directly; panel rebinding never disconnects the previous manager or scene; PRD 8.4's alignment toggle group is a dropdown in the code; the icon set lacks the chain-link glyphs.

## 4. PRD inconsistencies found during the inventory

Recorded here so Phase 1 can propose change-log rows for the General UI PRD; none is resolved by this note.

- Pasteboard colour: Section 6.1 says `#808080`; Section 13.2 says `#E0E0E0` for the light theme and Section 13.3 `#1E1E1E` for the dark theme. The theme tables should win once the theme manager exists.
- Blur tool shortcut: Section 3.7 says Z; the Blur, Highlighter, and Eyedropper PRD says D.
- Tool count: Section 3.7 lists 20 tools including Arc and Polygon; Section 17.3 says the palette shows "all 18 tools".
- Section 17.4 cites "Section 6.5" for the cursor table; the table is Section 6.6 after the Guides insertion.
- Section 2.1 says the status bar is toggleable and Section 3.3 lists Show Status Bar; both are consistent, but Section 15.4 does not list status bar visibility among persisted toggles. Treated as covered by "toolbar and panel visibility toggles".
- Section 4.3 describes a pressed state for grid and snap toggle buttons; no group in Section 4.2 contains one. Recorded in the PRD 2.0 change log; none built.

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

Taken at the start of Phase 4 (09-08-26):

| Decision | Choice | Effect |
|---|---|---|
| Memory usage zone | A, runtime dependency | `psutil` reads the process resident set size behind one guarded import in `snapmock/core/process_memory.py`; Technical Architecture PRD 1.8 lists the module and the dependency under its Section 9.1 policy (the readout is blank without the package). Screen Capture PRD Section 14.5 is unchanged. |

Taken in Phase 5 (09-08-26):

| Decision | Choice | Effect |
|---|---|---|
| Guide persistence | A, in the project file | `manifest.json` carries an optional `guides` list; `format_version` stays 1; guide changes are undoable commands that dirty the document. Technical Architecture PRD 1.10 records the format change in Section 6.1. |

Taken at the start of Phase 6 (09-09-26), from `docs/General-UI-Phase-6-Kickoff-Prompt.md`:

| Decision | Choice | Effect |
|---|---|---|
| 6.1 Layer blend mode | B, defer | The Layer has no blend mode or layer type in this phase. The action bar's blend-mode dropdown and the BG and raster badges of Section 7.4 and 7.5 go to the Navigation and Raster Operations follow-up that owns merging, since both need the per-layer compositing pass the display path lacks. General UI PRD 2.2 row. |
| 6.2 Item properties without a home | B, keep the Phase 4 deferral | Stroke Style, Fill Opacity, Stroke Opacity, the Shadow section, Blend Mode, and Line Spacing arrive with the Basic Shape and Text PRDs' item work. Every other Property Panel control of Section 8 is built here. General UI PRD 2.2 row. |

Taken at the start of Phase 7 (09-09-26), from `docs/General-UI-Phase-7-Kickoff-Prompt.md`:

| Decision | Choice | Effect |
|---|---|---|
| 7.1 Overrides saved with the project | B, application data directory only | Per-tool preset overrides and option values persist per user in the application data directory and never in `manifest.json`; a project file never carries tool settings, since one tool set is shared by every open tab and a per-project snapshot would overwrite the user's own setup on open. Technical Architecture PRD Section 6.1 is untouched. General UI PRD 2.3 row against Section 5.2. |
| 7.2 Preferences > Tools and the Default theme | A, Preferences edits the Default theme | The seven Preferences > Tools values are the Default theme's values for the keys they cover; the rest of Default comes from the tools' built-in constants. Startup loads the active theme instead of pushing Preferences into every tool; a Preferences change rewrites Default and reaches the tools only while Default is the active theme, and then only the tools without an override. The page names the active theme. General UI PRD 2.3 row against Section 11.3. |

The kickoff's remaining decision (welcome-panel card) is presented at the start of Phase 8.

### 5.2 As raised by Phase 0

The kickoff prompt's six decisions stand. The inventory adds three that pass the two-part test and must be presented with the consequential decision template before Phase 1 writes code:

1. **Tool shortcut letters.** Realign `config/shortcuts.py` to the PRDs (Line U, Callout B, Crop C, Freeform selection L, Zoom Ctrl+Space hold, Blur to whichever of Z or D the PRD correction picks), or keep the code's letters and record a departure in the General UI PRD and the three tool PRDs. Realigning changes what every existing user presses; keeping them means four PRDs carry a deviation row.
2. **Licence for the About dialog.** The PRD says "MIT or Apache 2.0"; the repository has neither a licence file nor a `license` field. About cannot show licence text until one is chosen. Phase 1 builds the dialog with a placeholder line if the decision is deferred.
3. **Ownership of the raster-composite actions.** Merge Down, Merge Visible, Flatten All, Auto-Trim, and Crop to Canvas as "activate the crop tool" are General UI menu rows whose behaviour belongs to the layer compositing and raster subsystems. Options: implement them in Phase 1 as part of "every menu item present and working", or defer them to a Navigation and Raster Operations follow-up with a change-log row in the General UI PRD.

## 6. Deviations from the PRD

Each has its change-log row in `PRDs/SnapMock-General-UI-PRD.html` version 1.7 (Phase 1), 1.8 (Phase 2), 1.9 (Phase 3), or 2.0 (Phase 4) unless the entry says otherwise.

- **Tool shortcut letters** (Section 3.7). Six letters differ from the PRD tables by decision; rows in all five PRDs (the Basic Shape PRD's row for Line, PRD U and shipped L, followed once that file's other edits were committed).
- **Merge Down, Merge Visible, Flatten All** (Section 3.4). Deferred; the rows check their requirement, then say the feature is not available yet.
- **Group and Ungroup** (Section 3.6). Deferred to their own kickoff; rows present with shortcuts.
- **Align and Distribute as submenus** (Section 3.6). The PRD lists eight flat rows; the menu keeps two submenus in the PRD's position and order.
- **Check for Updates** (Section 3.8). Present; says it is scheduled for a later phase. No phase owns it yet.
- **Show Tool Palette** (Section 3.3). Closed in Phase 4: the palette is the vertical Left Tool Palette and Show Main Toolbar toggles the new Main Toolbar.
- **Last-used tool option values** (Section 15.4). Closed in Phase 7: every tool's creation defaults and its applied preset are written to `tool_state.json` in the application data directory after each change and restored at startup over the active theme. PRD 2.3 row.
- **Select All Text batch changes** (Section 3.2). Closed in Phase 6: the Property Panel applies a font, size, or colour to every selected text item as one command (Section 8.6).
- **Preferences dependent controls** (Section 1.3). Resolved in Phase 3: Auto-save is one spinbox where 0 means disabled, and Keep running in tray stays editable while the tray is off.
- **Pasteboard colour** (Sections 6.1, 13.2, 13.3). The theme tables win: #E0E0E0 light, #1E1E1E dark. Preferences offers an override that follows the theme by default. The PRD's Section 18 issue is closed.
- **Theme constants and palette** (Section 13.4). Each style sheet opens with `@name: value;` constants that the theme manager substitutes into the rules and reads for canvas rendering; a matching QPalette is applied beside the sheet so style-drawn parts follow the theme. The base widget style stays the platform default.
- **Theme colours beyond the tables** (Section 13). Ruler, canvas border and shadow, checkerboard, guide, crosshair, input, and tooltip colours are defined per theme in the style sheet constants; the PRD tables leave them to the implementation.
- **Preferences rows without a consumer yet** (Section 11.3). Language (English only), Snap tolerance, Guide color and opacity, and Thumbnail update delay are stored; guides use theirs in Phase 5, layer thumbnails theirs in Phase 6, translation is unscheduled. Freehand smoothing is pushed into the freehand tool's creation defaults for the Phase 4 Tool Options Bar.
- **Preferences view toggles** (Section 11.3). Show grid, Show rulers, and Snap to grid are no longer in the dialog: they are View menu toggles, and the PRD's category list does not carry them.
- **Follow-theme states** (Section 11.3). Grid color, Grid opacity, the checkerboard colours, and the pasteboard colour default to the theme value and keep following the theme until set; the PRD lists fixed defaults.
- **Library variant of the Export dialog** (Section 11.2). No Export region group, since a file that is not open in a tab has no selection or visible area; a SnapMock Project format that copies the file, from Library PRD 7.1. With Apply to All unchecked the dialog reopens per file after the first, pre-filled with the directory (Library PRD 1.2 row).
- **SVG Embed raster images unchecked** (Section 11.2). Raster regions and stamps are omitted so the file is vector-only; the PRD does not define the unchecked output and the SVG generator cannot link external files.
- **SVG and PDF preview** (Section 11.2). The preview is the flattened raster of the region; the size estimate encodes the real export in memory (PDF through a temporary file).
- **Export Quick destination** (Section 3.1). Beside a saved non-Library document as `.png`, otherwise the last-used PNG directory under the display name; overwrites; the path is shown in the status bar. The PRD names the settings but not the destination.
- **Momentary eyedropper** (Section 12.2). Closed in Phase 4: the Eyedropper's options bar has Apply to Stroke and Apply to Fill, and a colour picked while Alt is held becomes the stroke colour default of the tool returned to (the Eyedropper PRD's default apply target).
- **Shared controls without an item property** (Sections 5.2, 8.3, 8.4). Stroke Style, Fill Opacity, Stroke Opacity, the Shadow section, Blend Mode, and Line Spacing are not built: no item exposes them, and a control with nothing behind it cannot be greyed out under Section 1.3. Vector tools and items show one Opacity control. Reaffirmed by Phase 6 decision 6.2: they arrive with the item work of the Basic Shape and Text and Callout PRDs. PRD 2.2 row.
- **Per-tool options bar contents** (Section 5.3). Recorded per tool in the PRD 2.0 row. Tool-specific controls whose item property does not exist yet (arrow head styles, corner radius, blend mode, blur mode and intensity, badge colour and size, stamp library) are omitted until their tool PRDs' item work lands. The bar edits creation defaults only; changes to selected items go through the Property Panel. Font Size is a spinbox (General UI PRD), not the Text PRD's editable combo box.
- **Zoom preset list** (Section 4.3). The dropdown and the status bar zoom menu use the PRD's eleven presets; Zoom In and Zoom Out step through the finer `ZOOM_STEPS` ladder of the Navigation PRD.
- **Grid and snap toolbar toggles** (Section 4.3). Mentioned by the PRD, listed in no group; none built. Added to Section 4 of these notes.
- **Memory zone units** (Section 9). A megabyte is 1,048,576 bytes; the zone stays in megabytes above 1 GB; a dash when the value cannot be read.
- **Selection size** (Section 9). The bounding box of the whole selection, stroke included, as the transform handles draw it.
- **Forbidden cursor over a locked layer's item** (Section 6.6). Shown by the Select tool and, over a locked text item, by the Text tool: the tools that would otherwise act on the item. Drawing tools keep their crosshair, since they draw on the active layer whatever lies beneath. PRD 2.1 row.
- **I-beam with highlight** (Section 6.6). Qt has no such cursor; `ui/cursors.py` draws an I-beam over a translucent accent bar. The rotate, magnifier, eyedropper, and raster-selection cursors are the Tabler glyphs with a white halo. PRD 2.1 row.
- **Alt with the Zoom tool** (Sections 6.6, 12.2). The momentary eyedropper of Section 12.2 no longer takes Alt while the Zoom tool is active, since the Zoom tool's own Alt+click zooms out and its cursor swaps to the minus magnifier. PRD 2.1 row.
- **Guides above handles** (Section 6.5). Guides draw in the view's foreground pass, above selection handles and tool overlays, where the Technical Architecture PRD Section 7.1 puts guide lines; the General UI PRD asked for below. Drawing there keeps them out of every export without a scene item. PRD 2.1 row.
- **Only the Select tool grabs a guide** (Section 6.5). A drawing tool started within the 4 px hit zone draws and snaps rather than moving the guide. PRD 2.1 row, with the other silent points: snap tolerance in screen pixels, Shift rounding on ruler drag-out, drop-to-delete only while rulers are shown, hidden guides not grabbable, Show Guides on by default.
- **Layer blend mode and badges** (Sections 7.4, 7.5). Deferred by decision 6.1 to the Navigation and Raster Operations follow-up with merging; the action bar has four buttons. PRD 2.2 row.
- **Layer visibility and opacity on the canvas** (Section 7.2). A bug before Phase 6: both were stored and only the Select tool honoured them. The scene now hides a hidden layer's items and gives each item its layer's opacity, applied in the item's paint pass; thumbnails still show a hidden layer's items. PRD 2.2 row.
- **Ctrl+click batches** (Section 7.3). Delete, lock, and hide act on the whole selection as one command when the clicked row is part of it; duplicate, rename, and reorder stay single-layer; Delete needs at least one layer left. PRD 2.2 row.
- **Hover highlight** (Section 7.3). Built, with the Preferences > Canvas & Grid row "Highlight layer items on hover" on by default; a dashed accent outline around the layer's visible items. PRD 2.2 row.
- **Section collapse persistence** (Section 8.2). Built in Phase 6; the Phase 0 inventory had recorded it as present. PRD 2.2 row.
- **Text section controls** (Section 8.4). Alignment stays a dropdown with Justify; Font Weight is Regular and Bold; Font Style is Normal and Italic; Underline stays a checkbox; Background Fill moved into the Text section. PRD 2.2 row.
- **Canvas DPI and canvas size** (Section 8.5). DPI lives on the scene and in the manifest's `canvas.dpi` (Technical Architecture PRD 1.11); export does not read it yet. The panel's width and height resize anchored top-left. Pasteboard Color, Grid Size, and Snap to Grid mirror the preference or View toggle. PRD 2.2 row.
- **Mixed indicators** (Section 8.6). A dash in spinboxes, a half-filled swatch, an empty dropdown, a part-checked box, and an unchecked Flip button with a "Mixed" tooltip; Item Type shows the shared type or "N items". PRD 2.2 row.
- **Picker square geometry and recent colours** (Section 11.1). The square is saturation by value at the hue bar's hue; recent colours are newest first, de-duplicated by ARGB, capped at twelve, and joined on popover close with a changed colour or on an eyedropper pick; saved slots fill by right-click. PRD 2.2 row.
- **Snap to Grid keyed to its toggle** (Section 3.3). A bug before Phase 5: the Select tool snapped whenever the grid was shown. Grid snapping now also covers new shapes and resizes. PRD 2.1 row.
- **Overrides not saved with the project** (Section 5.2). Decision 7.1, option B: per-tool preset overrides persist per user in the application data directory only; `manifest.json` and Technical Architecture PRD Section 6.1 are unchanged. PRD 2.3 row.
- **Preferences > Tools edits the Default theme** (Sections 11.3, 11.8). Decision 7.2, option A: the seven values are the Default theme's for the keys they cover; a change reaches the tools only while Default is active and only the tools that are not overridden; the page names the active theme. PRD 2.3 row.
- **Which tools have presets** (Section 5.3). The nine tools with creation defaults. The Crop, Raster Selection, and Lasso tools keep their options in the widgets they build, so they have no dropdown and a theme does not capture them; Select, Stamp, Blur, Eyedropper, Pan, and Zoom have nothing to capture. PRD 2.3 row.
- **"Custom" detection and the dropdown's text** (Section 5.2). The tool's current values are compared with the applied preset, or with the active theme when no preset is applied; the dropdown reads the preset name, the theme name, or "Custom". Update Preset appears only while a preset is applied and the values have moved off it. PRD 2.3 row.
- **Manage Presets not undoable** (Section 11.9). Renames and deletions apply to the files at once; presets are not document state and the command stack belongs to a document. Delete confirms; the row opens only when the tool has a preset. PRD 2.3 row.
- **Application data directory and theme rules** (Section 11.8). `QStandardPaths` generic configuration location under `snapmock` (`~/.config/snapmock` on Linux); the Default theme is not a file; the active theme cannot be deleted; an imported name collision is numbered; a theme lacking a tool or key falls back to Default; the preview lists every tool with presets in palette order with the Manage Presets summary. The `.smktheme` schema is Technical Architecture PRD Section 4.4. PRD 2.3 row.
- **"(modified)" on the Active Theme label** (Section 3.7). Shown once any tool differs from the active theme, through a preset or a Custom edit, not only after a preset is applied. PRD 2.3 row.

## 7. Tests

Phase 7 adds `tests/test_tool_themes.py` (19 tests: the codec round trip for every value type and its rejections, value equality, unique names, the preset store's save, list, rename, delete, slug collisions, and skipped files, the theme file round trip and its three refusals, the theme store ignoring a file named Default, the Default theme under Preferences, Preferences reaching only un-overridden tools and only under Default, presets' apply, label, Custom, update, and reset, rename and duplicate and delete following the applied name, Apply clearing overrides, fallback to Default for missing tools and keys, theme duplicate, rename, delete, import, and export, and the session state round trip across two tool sets), `tests/test_preset_dropdown.py` (8 tests: the dropdown as the leftmost control and its absence for tools without defaults, Custom after an edit on either surface, Save as Preset and every menu row, the name and replacement checks, Reset to Theme and its message, persistence across two windows, Preferences editing Default around an override with the dialog's note, and the isolated data directory), `tests/test_manage_presets_dialog.py` (6 tests: the summary text, the title and rows, inline rename following the applied preset, rejected names, duplicate and delete with the selection messages, and the dropdown row's message and dialog), and `tests/test_tool_themes_dialog.py` (7 tests: the Tools menu rows and the label's "(modified)", the list, mark, and preview, Apply clearing overrides and reaching the bar, New's name checks, duplicate, rename, and delete with the Default and active-theme refusals, import and export with a refused file, and the menu row opening the dialog). `tests/conftest.py` points the application data directory at a throwaway folder for every test. At the close of Phase 7 the suite passes 840 tests with 13 skipped and the one environmental deselection (`test_font_combo_reflects_text_item_font`).

Phase 6 adds `tests/test_layer_panel.py` (21 tests: layer visibility and opacity reaching items and the render, the per-layer render at scale, the row geometry and minimum width, the active row, the eye and lock toggles as commands, the opacity popover merging into one undo entry, inline rename and the F2 route, thumbnails after the delay, rebinding and disconnection, the drop-target mapping, reorder, Ctrl+click batches, batch delete through the window, the action bar reusing the menu actions and their messages, the standalone panel's commands, the hover highlight and its preference, the hovered-row signal), `tests/test_property_panel_phase6.py` (11 tests: collapse persistence, the aspect lock, mixed values and hex inputs, one undo entry per slider drag over a selection, the weight and style dropdowns and Background Fill's home, alignment and font changes as commands across a selection, the Canvas section's size, colour, and DPI commands, the manifest DPI round trip, the preference controls reaching the window, Canvas Properties), and `tests/test_color_picker.py` (9 tests: the popover beside the swatch with no toggle, the square and bars applying live, the inputs syncing, the Transparent swatch and its absence, recent colours' order and cap, saved slots, setting a colour into an open popover, the eyedropper without a window, and the eyedropper pick landing in the picker and restoring the tool). `tests/test_property_panel.py` reads the weight and style dropdowns; `tests/test_preferences_dialog.py` checks the hover-highlight row. At the close of Phase 6 the suite passes 800 tests with 13 skipped and the one environmental deselection (`test_font_combo_reflects_text_item_font`).

Phase 4 adds `tests/test_process_memory.py` (4 tests: a positive reading, the guarded import, the megabyte format, the thresholds), `tests/test_main_toolbar.py` (13 tests: the groups and dividers in PRD order, placement and object name, icon-only 32 px buttons with shortcut tooltips, the tooltip helper, an unmet requirement through a toolbar button, the Align group shown for two or more items and following the active tab, the zoom dropdown's presets, sync, custom entry and range message, and tab following, View > Show Main Toolbar and Reset Layout, the palette as a 48 px vertical left column, and its toggle), `tests/test_tool_options_bar.py` (15 tests: height and name, the shared set per shape tool, bar edits writing defaults, bar and Property Panel in step both ways, Preferences pushes, the Text tool's controls and alignment slot, the Callout's own controls applied to new items, the Select tool's label and alignment copies and their tab following, the Eyedropper's display and Apply buttons, the momentary pick, the numbered step Starting Number, freehand smoothing, the Rule of Thirds label, and the tools with a name only), and `tests/test_status_bar.py` (7 tests: zone widths and height, cursor and canvas formats, selection size, the clickable zoom menu, memory text and colour roles, the memory refresh, and tab following). `tests/test_capture/test_main_window.py` reads the Capture button from the Main Toolbar. At the close of Phase 4 the suite passed 725 tests with 13 skipped and one environmental deselection (`test_font_combo_reflects_text_item_font`).

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

## 11. What Phase 4 built

In commit order: decision 2 and `snapmock/core/process_memory.py` (`process_memory_bytes`, `format_memory`, `memory_role`, the 500 MB and 1 GB thresholds) with `psutil` and `types-psutil` in `pyproject.toml` and Technical Architecture PRD 1.8; the Main Toolbar (`MainToolBar`, `ZOOM_PRESETS`, `action_tooltip` in `snapmock/ui/toolbar.py`; `MainWindow._actions`, `_register`, `_populate_main_toolbar`, `_enforce_toolbar_layout`; View > Show Main Toolbar; the Capture button as Group 0; icon-map entries for the two Align labels with axis suffixes); the Left Tool Palette (`SnapToolBar` docked left, 48 px, one column); the Tool Options Bar's shared controls (`BaseTool.options_controls` and `on_option_changed`, `ToolManager.tool_defaults_changed`, `ControlSpec` and `SHARED_CONTROLS` in `snapmock/ui/tool_options_bar.py`, `ColorPicker(swatch_size=)`, the Property Panel's `_notify_defaults_changed`, the tools' declarations, freehand smoothing through `simplify_rdp`, the numbered step `next_number`, the callout's shape, tail style and tail width defaults, the eyedropper's `set_pick_callback` and `pick_serial`, `MainWindow._apply_momentary_pick`); and the status bar (`SnapStatusBar(document)` with `set_document`, the six zones, `zoom_menu`, `set_memory_bytes`, the 5-second timer).

## 12. What Phase 5 built

In commit order: the canvas corrections of Sections 6.2 and 6.4 (the empty-canvas prompt names Ctrl+V and File > Import Image; major grid lines every 5 units; minor lines hidden below 200 percent zoom; the `scene` test fixture creates the application first); View > Show Crosshairs (`AppSettings.crosshairs_visible`, `SnapView.set_crosshairs_visible` drawing in the theme's crosshair colour, the Tabler `crosshair` glyph); and the cursor table of Section 6.6 (`snapmock/ui/cursors.py`; `BaseTool.cursor` may return a `QCursor`; `SnapView.set_hover_cursor`; the Select tool's open hand, closed hand, handle cursors, and forbidden cursor; the Text tool's highlighted I-beam; the Zoom tool's magnifiers with Alt; the eyedropper and raster-selection cursors; the Pan tool's hands set on the viewport; the copy action on external image drags; handles ignored while not in the scene). Technical Architecture PRD 1.9 lists the module. Tests: three in `tests/test_canvas_area.py` for the corrections, two for crosshairs, one row added to `tests/test_menus.py`, and `tests/test_cursors.py` (9 tests). At this point the suite passes 739 tests with 13 skipped and the two environmental deselections.

Then the guides (commit 620da91): `snapmock/core/guides.py` (`Guide`, `GuideOrientation`, `snap_value`, `snap_rect_delta`), `snapmock/commands/guide_commands.py` (`AddGuideCommand`, `MoveGuideCommand` with merge, `RemoveGuideCommand`, `ClearGuidesCommand`), `SnapScene.guides` with `add_guide`, `remove_guide`, `replace_guide`, `set_guides`, and the `guides_changed` signal; `save_project` and `load_project` carry the manifest key; `SnapView` draws guides in the Preferences colour and opacity (`set_guide_style`), grabs one under the Select tool (`guide_at`, `GUIDE_HIT_TOLERANCE`), moves it with Shift rounding, drops it back on its ruler to remove it, and places a new one dragged out of a `RulerWidget` (`begin_guide_preview`, `update_guide_preview`, `finish_guide_preview`); `snap_point` and `snap_rect_offset` give tools grid and guide snapping under the View toggles (`BaseTool._snap_pos`; the Select tool's move and resize; the rectangle, ellipse, line, and arrow tools); `AppSettings` gains `guides_visible`, `snap_to_guides`, `guides_locked`; the View menu gains Show Guides (Ctrl+;), Snap to Guides, Lock Guides, and Clear All Guides with its confirmation; Preferences' guide colour, opacity, and snap tolerance reach every view. The `RulerWidget` now holds its view through a weak reference, which removes a reference cycle that let the garbage collector clear a view's attributes while Qt was still destroying it. Technical Architecture PRD 1.10 records the format change and the two modules. Tests: `tests/test_guides.py` (19 tests) and four rows added to `tests/test_menus.py`. At the close of Phase 5 the suite passes 758 tests with 13 skipped and the two environmental deselections.

## 13. What Phase 6 built

In commit order: decisions 6.1 and 6.2 with the prompt corrections (Section 3.1); the Layer Panel rows (`snapmock/ui/layer_panel.py` rewritten around a `QStyledItemDelegate`: the eye and lock toggles, the thumbnail on a checkerboard from `RenderEngine.render_layer_region` at thumbnail scale after the thumbnail delay, the elided name with the inline editor, the opacity text and its slider popover, the accent, hover, and locked-row treatments, the 200 px minimum; `SnapScene.apply_layer_state` and the `layer_opacity` paint pass on `SnapGraphicsItem`; `ChangeLayerPropertyCommand(mergeable=)`; `MainWindow._layer_rename` inline); the interactions and action bar (`_LayerList` with drag reorder through `ReorderLayerCommand` and the accent insertion line, `drop_target_index`, Ctrl+click batches through `LayerPanel.batch_ids` and `MacroCommand`, `set_actions` binding the Layer menu's `QAction`s to the bar, `layer_hovered` to `SnapView.set_highlighted_layer`, `AppSettings.layer_hover_highlight` with its Preferences row); the Property Panel (`snapmock/ui/property_panel.py` rewritten around `_selected_items`: the chain-link `aspect_locked` toggle with the vendored `link` and `link-off` glyphs, hex inputs, `FONT_WEIGHTS` and `FONT_STYLES` dropdowns, Background Fill in the Text section, the editable Canvas section with `canvas_setting_changed` for the preference-backed controls, `ModifyPropertiesCommand` in `commands/modify_property.py`, `SetCanvasPropertyCommand` in the new `commands/canvas_property_commands.py`, `SnapScene.canvas_dpi` and the manifest key, `horizontal_alignment` on the text items, `CollapsibleSection.set_expanded` and `toggled` with `AppSettings.property_section_expanded`, `ColorPicker.mixed`, `show_canvas_section` behind Canvas Properties); and the colour picker (`ColorPopover` in `snapmock/ui/color_picker.py` with the square, bars, inputs, swatch rows, Transparent, and eyedropper button; `AppSettings.recent_colors`, `push_recent_color`, `saved_colors`, `set_saved_color`; `ColorPicker.set_eyedropper_handler` served by `MainWindow._pick_color_for_picker` through `ToolManager.activate_temporary` and `EyedropperTool.pick_callback`). Technical Architecture PRD 1.11 records the manifest key and the new module; General UI PRD 2.2 carries the phase's rows.

## 14. What Phase 7 built

In commit order: decisions 7.1 and 7.2 (Section 5.1); the model and storage (`snapmock/core/tool_themes.py`: `ToolPreset`, `ToolTheme`, the value codec `encode_value`, `decode_value`, `encode_values`, `decode_values`, `values_equal`, `unique_name`, `PresetStore` under `presets/<tool_id>/`, `ThemeStore` under `themes/`, `read_theme_file` and `write_theme_file` for the `.smktheme` schema with `format_version` 1, `application_data_directory`, and `ToolThemeManager` with `default_theme`, `preferences_changed`, `apply_theme`, `capture_theme`, `duplicate_theme`, `rename_theme`, `delete_theme`, `import_theme`, `export_theme`, `apply_preset`, `save_preset`, `update_preset`, `rename_preset`, `duplicate_preset`, `delete_preset`, `reset_to_theme`, `is_overridden`, `is_modified`, `preset_is_modified`, `current_label`, `save_session`, and `load_session`, and the `active_theme_changed`, `presets_changed`, `themes_changed`, and `state_changed` signals; `AppSettings.active_tool_theme`; Technical Architecture PRD 1.12 with Section 4.4); the preset dropdown (`ToolOptionsBar.set_theme_manager`, `preset_button`, `_build_preset_dropdown`, `_populate_preset_menu`, the Save as Preset, Update Preset, Manage Presets, and Reset to Theme rows; `MainWindow._tool_themes`, `_load_tool_session` at startup in place of the Preferences push, `_apply_tool_defaults` now the Default theme's edit, `_save_window_state` writing the session; the Preferences > Tools note naming the active theme); the Manage Presets dialog (`snapmock/ui/manage_presets_dialog.py`: `ManagePresetsDialog` and `summarise_values`); and the Tool Themes dialog with the Tools menu rows (`snapmock/ui/tool_themes_dialog.py`: `ToolThemesDialog`; `MainWindow._tools_tool_themes`, `_update_active_theme_label`, `active_theme_text`, the `QWidgetAction` label row). General UI PRD 2.3 carries the phase's rows.

**Next required step:** Phase 8, First run, accessibility, and responsive behaviour, in a new session pasting `docs/General-UI-Implementation-Kickoff-Prompt.md` (a Phase 8 instance of the prompt, written as the Phase 6 and Phase 7 prompts were, would give the session the starting state). Phase 8 opens with kickoff decision 5, the welcome panel's New Blank Canvas card; the acceptance pass against PRD Section 17 follows Phase 8.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.10 | 09-09-26 20:45 | Claude (Claude Code) | Phase 7 done: phase table, decisions 7.1 and 7.2 (Section 5.1), seven deviations added and one closed (Section 6), tests (Section 7), build summary and next step (Section 14). General UI PRD 2.3, Technical Architecture PRD 1.12. |
| 1.9 | 09-09-26 16:30 | Claude (Claude Code) | Phase 6 done: phase table, nine deviations added and two closed (Section 6), tests (Section 7), build summary and next step (Section 13). General UI PRD 2.2, Technical Architecture PRD 1.11. |
| 1.8 | 09-09-26 09:40 | Claude (Claude Code) | Phase 6 in progress: decisions 6.1 and 6.2 (Section 5.1), the corrections found at the phase's start (Section 3.1). |
| 1.7 | 09-08-26 23:45 | Claude (Claude Code) | Phase 5 done: phase table, the guide-persistence decision (Section 5.1), three deviations added (Section 6), the guides build and next step (Section 12). General UI PRD 2.1, Technical Architecture PRD 1.10. |
| 1.6 | 09-08-26 22:20 | Claude (Claude Code) | Phase 5 in progress: phase table, three deviations (Section 6), what is built and what remains (Section 12), the Snap to Grid finding. |
| 1.5 | 09-08-26 19:40 | Claude (Claude Code) | Phase 4 done: phase table, the memory-zone decision (Section 5.1), seven deviations added and two closed (Section 6), a Section 4 inconsistency, tests (Section 7), build summary and next step (Section 11). |
| 1.4 | 09-08-26 16:30 | Claude (Claude Code) | Phase 3 done: phase table, the icon-set decision (Section 5.1), seven deviations (Section 6), tests (Section 7), build summary and next step (Section 10). |
| 1.3 | 09-08-26 13:45 | Claude (Claude Code) | Phase 2 done: phase table, four deviations (Section 6), tests (Section 7), build summary and next step (Section 9). |
| 1.2 | 09-08-26 13:21 | Claude (Claude Code) | Basic Shape PRD shortcut row delivered; the owed item is closed. |
| 1.1 | 09-08-26 11:23 | Claude (Claude Code) | Phase 1 done: phase table, decisions taken (Section 5.1), ten deviations (Section 6), tests (Section 7), build summary and next step (Section 8). |
| 1.0 | 09-08-26 00:10 | Claude (Claude Code) | Phase 0: verified inventory by PRD section, corrections to the kickoff inventory, PRD inconsistencies, three added Phase 1 decisions, empty deviations list. |
