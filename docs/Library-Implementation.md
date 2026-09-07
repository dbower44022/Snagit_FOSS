# Library Implementation Notes

Last Updated: 09-07-26 01:30 · Revision 1.0

Implements the SnapMock Library PRD (version 1.0, March 2026): tabbed multi-document editing, the Library panel, continuous write-back, the Library menu, preferences, session persistence, drag-and-drop import and export, and library file commands.

## 1. Architecture

### 1.1 Documents and tabs (PRD Section 4)

| Component | File | Role |
|---|---|---|
| `Document` | `snapmock/core/document.py` | One open file: its own `SnapScene`, `SnapView`, `SelectionManager`, `ClipboardManager`, file path, `is_library_file`, display name, `library_metadata`. `is_dirty` is always False for library files. |
| `DocumentManager` | `snapmock/core/document_manager.py` | Ordered list of open documents and the active one. Signals: `document_added`, `document_removed`, `active_changed`, `document_title_changed`, `documents_reordered`. |
| `DocumentTabs` | `snapmock/ui/document_tabs.py` | Central widget: a `QTabBar` above a `QStackedWidget` of views. Hidden with 0 or 1 tabs. Movable, closable, middle-click close, tab context menu (Close, Close Others, Close All, Close Tabs to the Right, Reveal in Library, Reveal in File Manager). |

`MainWindow` keeps one shared `ToolManager`. On `active_changed` it cancels the active tool, rebinds the tool manager's scene and selection manager, re-activates the tool, and points the layer panel, property panel, and status bar at the new document. The attributes `_scene`, `_view`, `_selection_manager`, `_clipboard`, and `_current_file` are read-only properties of the active document, so the existing menu handlers did not change.

Design decisions:

- **One view per document.** Each `Document` owns its `SnapView`, so zoom and scroll position survive tab switches for free. Cost: one `QGraphicsView` per open tab.
- **One document is always open.** Closing the last tab creates a fresh Untitled document. This keeps every `self._scene` call site safe.
- **Pristine Untitled tabs are replaced.** File > New or File > Open replaces an unsaved, untouched Untitled tab instead of leaving it behind.
- **Prompting.** Only dirty non-library documents prompt Save / Discard / Cancel on close and on window close.
- **Per-document wiring happens once** (`_wire_document`), keyed by `tab_id`, so switching back and forth never duplicates signal connections.

Shortcuts added: `file.close_tab` (Ctrl+W), `view.next_tab` (Ctrl+Tab), `view.previous_tab` (Ctrl+Shift+Tab), `library.toggle_panel` (Ctrl+L).

### 1.2 The .smk archive (PRD Sections 2.4, 11)

`snapmock/io/project_serializer.py`:

- `save_project(scene, path, library_metadata=None, *, write_thumbnail=True)` now writes `thumbnails/thumb.png` (a flattened preview, at most 256 px) and stores `library_metadata` and `active_layer_id` in `manifest.json`. Writes go to a sibling `.tmp` file and then `replace()` the target, so a crash mid-write never leaves a truncated archive.
- `read_manifest`, `read_library_metadata`, `read_thumbnail`, `read_project_summary` read facts without building a scene (used by the Library panel).
- `update_library_metadata(path, **fields)` rewrites only `manifest.json` inside the archive (used by rename).
- `load_project` restores the active layer from the manifest.

`RasterRegionItem` caches its base64 PNG keyed on the pixmap cache key, so continuous write-back does not re-encode unchanged rasters.

### 1.3 Library package (PRD Sections 2, 3, 6, 9, 10)

| Component | File | Role |
|---|---|---|
| `LibraryManager` | `snapmock/library/manager.py` | Root directory, naming (`Capture_YYYY-MM-DD_HH-MM-SS`), creation from image / blank / import, continuous write-back (debounced 300 ms after `stack_changed`), listing, rename (disk + manifest), delete (system trash via `send2trash`), move, copy (" (Copy)" suffix), folders, `move_library`, total size. Owns a `CommandStack` for library operations. |
| `LibraryFileInfo` | `snapmock/library/file_info.py` | PRD 9.1 record; thumbnail loaded lazily; invalid archives flagged rather than raising. |
| `LibraryModel` | `snapmock/library/model.py` | `QAbstractTableModel` for the current folder: folders first, in-model sort and filter, breadcrumbs, drag (internal paths mime + exported PNG URLs) and drop (internal move onto folders, external import). |
| Commands | `snapmock/library/commands.py` | `RenameLibraryFileCommand`, `MoveLibraryFileCommand`, `CreateFolderCommand` (undo blocked with a message once the folder has content). |
| Rendering | `snapmock/library/render.py` | `render_file_to_image`, `export_files_to_png`, `export_for_drag`. |

### 1.4 Library panel (PRD Section 3)

`snapmock/ui/library_panel.py` is a `QDockWidget` (default bottom, 250 px). Header: elided path, Change Library, Grid / List toggle, size slider (80 to 256 px grid, 48 to 128 px list), search. Navigation bar: back button and breadcrumbs. Content: `QListView` in icon mode with a card delegate (thumbnail, name, gray modified date, open badge) or a `QTreeView` with sortable columns (Name, Size, Date Modified, Date Captured); the two views share one selection model. Footer: file count ("N of M files" while filtering, "in K folders"), library size (computed on a worker thread), sort dropdown.

Keys are claimed at `ShortcutOverride` so they beat the window-level Edit shortcuts while the panel has focus: Enter open, F2 rename, Delete, Ctrl+A select files only, Ctrl+C / Ctrl+V copy and paste files, Ctrl+Shift+C copy flattened PNG to the system clipboard, Ctrl+Z / Ctrl+Shift+Z library undo and redo.

Context menus follow PRD 3.14 for files, folders, and empty space. Unmet requirements show an information message instead of a disabled item (never-disabled controls).

### 1.5 MainWindow wiring (PRD Sections 4 to 8)

- Opening a path under the library root marks the document `is_library_file` and attaches write-back. File > Save on a library document writes back immediately. File > Save As on a library document writes a copy and leaves the tab bound to the library file.
- Library menu after Tools: Show Library Panel (Ctrl+L), Open Library, Move Library (progress dialog, re-points open tabs), New Folder, Reveal in File Manager, Library Preferences.
- `MainWindow.add_to_library(image, source)` is the capture entry point (PRD 6.1): creates the file in the current library folder, opens it when Auto-open is on, and shows a toast with an Open link. There is no screen-capture feature yet; this is the hook for it.
- Deleting a file from the panel closes its tab first, without a prompt.
- Export from the panel: one file opens it and runs File > Export; several files prompt for an output directory and export PNGs with a progress dialog and a per-file error summary.
- Dragging a library file onto the canvas opens it (`SnapView.library_files_dropped`).
- Session: open tab paths and the active index are saved on close and restored when the app starts (`MainWindow(restore_session=True)` in `app.py`).
- Preferences: a Library group (directory, auto-open, default view mode, default thumbnail size, default sort, toast notifications). Changes apply immediately.

## 2. Deviations from the PRD

- **Delete has no undo.** Files go to the system trash through `send2trash`, which does not report where the file landed, so `DeleteLibraryFileCommand` (PRD 10.2) is not implemented. The confirmation dialog is the safeguard.
- **Raster data is rewritten on every write-back.** The .smk format embeds rasters in `items.json`, so PRD 2.3's "raster written only on raster operations" is approximated by caching the PNG encoding and debouncing writes.
- **Export dialog.** SnapMock has no Export dialog yet (General UI PRD 11.2). Multi-select export prompts for a directory and writes PNGs; per-format options are not offered.
- **New Canvas.** Added to the empty-space context menu so the `new` source is reachable. File > New still creates an unsaved, non-library tab.
- **Open in New Window** opens a second `MainWindow` in the same process.

## 3. Tests

- `tests/test_documents.py`: Document, DocumentManager, tab behavior in MainWindow.
- `tests/test_library_manager.py`: naming, creation, import, rename, move, folders, copy, size, write-back, move library, commands.
- `tests/test_library_panel.py`: model sort / filter / navigation / drag-drop, panel behavior, MainWindow integration, preferences.
- `tests/conftest.py` isolates `AppSettings` in a temporary INI file and points the library at a temporary directory for every test.

## 4. Follow-ups

- Screen capture (hotkey, tray) feeding `MainWindow.add_to_library`.
- Export dialog with per-format options and "Apply to All".
- Write-back on a worker thread for very large rasters.
- Thumbnail refresh in the panel after write-back is immediate; a size recalculation runs on every change and could be throttled for very large libraries.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-07-26 01:30 | Claude (Claude Code) | Initial implementation notes for the Library PRD. |
