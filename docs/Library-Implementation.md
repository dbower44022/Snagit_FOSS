# Library Implementation Notes

Last Updated: 09-08-26 13:45 · Revision 1.2

Implements the SnapMock Library PRD (version 1.1, 09-07-26): tabbed multi-document editing, the Library panel, continuous write-back, the Library menu, preferences, session persistence, drag-and-drop import and export, and library file commands.

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
| `LibraryManager` | `snapmock/library/manager.py` | Root directory, naming (`Capture_YYYY-MM-DD_HH-MM-SS`), creation from image / blank / import, continuous write-back (debounced 300 ms after `stack_changed`), listing, rename (disk + manifest), session trash (`trash_files`, `restore_files`, `purge_session_trash`, `sweep_foreign_trash`, `sweep_trash`), move, copy (" (Copy)" suffix), folders, `move_library`, total size. Owns a `CommandStack` for library operations. |
| `LibraryFileInfo` | `snapmock/library/file_info.py` | PRD 9.1 record; thumbnail loaded lazily; invalid archives flagged rather than raising. |
| `LibraryModel` | `snapmock/library/model.py` | `QAbstractTableModel` for the current folder: folders first, in-model sort and filter, breadcrumbs, drag (internal paths mime + exported PNG URLs) and drop (internal move onto folders, external import). |
| Commands | `snapmock/library/commands.py` | `RenameLibraryFileCommand`, `DeleteLibraryFileCommand`, `MoveLibraryFileCommand`, `CreateFolderCommand` (undo blocked with a message once the folder has content). |
| Rendering | `snapmock/library/render.py` | `render_file_to_image`, `export_files_to_png`, `export_for_drag`. |

**Session trash (PRD 3.8, 10.2).** Delete is undoable without asking the system trash to give a file back, which `send2trash` cannot do. Each `LibraryManager` has a session id, `<pid>-<random>`, and a session trash folder `<root>/.trash/<session id>` created on first use. `DeleteLibraryFileCommand.redo` moves each file or whole folder into that folder under a unique name and records the pairs; `undo` moves them back to their original paths, or to the next free name if the original is now taken; `discard` sends whatever is still in the session trash to the system trash. `discard` is a hook added to `BaseCommand` for this: `CommandStack` calls it for the oldest command dropped by its limit, for redo history truncated by a push, and for everything on `clear`; scene commands inherit the empty default.

Files reach the system trash at four points: when the command is discarded; on the main window's close path, where `purge_session_trash` runs next to `flush`; at `LibraryManager` construction, where `sweep_foreign_trash` clears every `.trash` entry that is not this process's, which handles crashes and windows that closed without a clean exit while another window of the same process keeps its held deletes; and before `move_library` and `set_root`, which clear the Library command stack (sending held deletes through `discard`) and then sweep `.trash` so the old location is left with nothing in it. Switching or moving the library therefore ends the Library undo history. The panel's delete path is unchanged up to the push: confirmation dialog, `files_about_to_be_deleted` so the main window closes tabs, then the command. Undo does not reopen a closed tab. `.trash` was already hidden from the folder listing and skipped by the size total; `.trash` is removed once it is empty.

### 1.4 Library panel (PRD Section 3)

`snapmock/ui/library_panel.py` is a `QDockWidget` (default bottom, 250 px). Header: elided path, Change Library, Grid / List toggle, size slider (80 to 256 px grid, 48 to 128 px list), search. Navigation bar: back button and breadcrumbs. Content: `QListView` in icon mode with a card delegate (thumbnail, name, gray modified date, open badge) or a `QTreeView` with sortable columns (Name, Size, Date Modified, Date Captured); the two views share one selection model. Footer: file count ("N of M files" while filtering, "in K folders"), library size (computed on a worker thread), sort dropdown.

Keys are claimed at `ShortcutOverride` so they beat the window-level Edit shortcuts while the panel has focus: Enter open, F2 rename, Delete, Ctrl+A select files only, Ctrl+C / Ctrl+V copy and paste files, Ctrl+Shift+C copy flattened PNG to the system clipboard, Ctrl+Z / Ctrl+Shift+Z library undo and redo.

Context menus follow PRD 3.14 for files, folders, and empty space. Unmet requirements show an information message instead of a disabled item (never-disabled controls).

### 1.5 MainWindow wiring (PRD Sections 4 to 8)

- Opening a path under the library root marks the document `is_library_file` and attaches write-back. File > Save on a library document writes back immediately. File > Save As on a library document writes a copy and leaves the tab bound to the library file.
- Library menu after Tools: Show Library Panel (Ctrl+L), Open Library, Move Library (progress dialog, re-points open tabs), New Folder, New Canvas (blank canvas at the default size in the folder the panel is showing, the same action as the panel's empty-space context-menu item), Reveal in File Manager, Library Preferences.
- `MainWindow.add_to_library(image, source)` is the capture entry point (PRD 6.1): creates the file in the current library folder, opens it when Auto-open is on, and shows a toast with an Open link. There is no screen-capture feature yet; this is the hook for it.
- Deleting a file from the panel closes its tab first, without a prompt. Undo restores the file but not the tab.
- Export from the panel: the Export dialog's Library variant (`snapmock/ui/export_dialog.py`, General UI Phase 2). One file opens the dialog for that file without opening a tab; several files show Output Directory and Apply to All and run through the progress dialog with cancel and a per-file error summary. Export Quick (PNG) uses the last-used PNG settings, prompting for a directory, and opens the dialog on first use. `snapmock/library/render.py` gained `export_target` (display name plus suffix) and `export_file` (one file with an `ExportSettings`).
- Dragging a library file onto the canvas opens it (`SnapView.library_files_dropped`).
- Session: open tab paths and the active index are saved on close and restored when the app starts (`MainWindow(restore_session=True)` in `app.py`).
- Preferences: a Library group (directory, auto-open, default view mode, default thumbnail size, default sort, toast notifications). Changes apply immediately.

## 2. Deviations from the PRD

- **Raster data is rewritten on every write-back.** The .smk format embeds rasters in `items.json`, so PRD 2.3's "raster written only on raster operations" is approximated by caching the PNG encoding and debouncing writes.
- **Open in New Window** opens a second `MainWindow` in the same process. Each window builds its own `LibraryManager` and Library command stack over the same root; the per-manager session trash keeps their held deletes apart.

## 3. Tests

- `tests/test_documents.py`: Document, DocumentManager, tab behavior in MainWindow.
- `tests/test_command_stack.py`: `discard` is called for the oldest command under the limit, for truncated redo history, and on `clear`, and never by undo or redo.
- `tests/test_library_manager.py`: naming, creation, import, rename, move, folders, copy, size, write-back, move library, commands; session trash (`trash_files` / `restore_files`, unique names, restore into an occupied path), `DeleteLibraryFileCommand` undo / redo / discard, discard after undo sends nothing, whole-folder delete, `purge_session_trash`, the construction sweep sparing this process's folders, `move_library` and `set_root` sweeping `.trash` first. `send2trash` is replaced by a fake that records and removes.
- `tests/test_library_panel.py`: model sort / filter / navigation / drag-drop, panel behavior (delete pushes an undoable command and honors Cancel), MainWindow integration (window close purges the session trash, Library menu New Canvas uses the shown folder and sits after New Folder), preferences.
- `tests/conftest.py` isolates `AppSettings` in a temporary INI file and points the library at a temporary directory for every test.

## 4. Follow-ups

- Screen capture (hotkey, tray) feeding `MainWindow.add_to_library`.
- Write-back on a worker thread for very large rasters.
- Thumbnail refresh in the panel after write-back is immediate; a size recalculation runs on every change and could be throttled for very large libraries.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.2 | 09-08-26 13:45 | Claude (Claude Code) | Export dialog delivered by General UI Phase 2: Section 1.5 export bullet rewritten, the Section 4 follow-up closed. |
| 1.1 | 09-07-26 23:20 | Claude (Claude Code) | Three deviations closed per the 09-07-26 decisions: delete is undoable through a session trash (Section 1.3, tests in Section 3); New Canvas joins the Library menu (Section 1.5); the Export dialog moves to Section 4 with the Library variant named. |
| 1.0 | 09-07-26 01:30 | Claude (Claude Code) | Initial implementation notes for the Library PRD. |
