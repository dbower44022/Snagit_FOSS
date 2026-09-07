"""LibraryModel — table model over one library folder (files and subfolders)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QMimeData,
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle

from snapmock.config.constants import LIBRARY_PATHS_MIME
from snapmock.library.file_info import LibraryFileInfo
from snapmock.library.manager import LibraryManager

PATH_ROLE = Qt.ItemDataRole.UserRole + 1
IS_FOLDER_ROLE = Qt.ItemDataRole.UserRole + 2
INFO_ROLE = Qt.ItemDataRole.UserRole + 3
IS_OPEN_ROLE = Qt.ItemDataRole.UserRole + 4
SUBTITLE_ROLE = Qt.ItemDataRole.UserRole + 5

COL_NAME = 0
COL_SIZE = 1
COL_MODIFIED = 2
COL_CAPTURED = 3
COLUMN_TITLES = ["Name", "Size", "Date Modified", "Date Captured"]

SORT_OPTIONS: list[tuple[str, str]] = [
    ("name_asc", "Name (A-Z)"),
    ("name_desc", "Name (Z-A)"),
    ("date_modified_desc", "Date Modified (Newest First)"),
    ("date_modified_asc", "Date Modified (Oldest First)"),
    ("date_captured_desc", "Date Captured (Newest First)"),
    ("date_captured_asc", "Date Captured (Oldest First)"),
    ("size_desc", "File Size (Largest First)"),
    ("size_asc", "File Size (Smallest First)"),
]
SORT_COLUMN_TO_KEY = {
    COL_NAME: "name",
    COL_SIZE: "size",
    COL_MODIFIED: "date_modified",
    COL_CAPTURED: "date_captured",
}


@dataclass
class LibraryEntry:
    """One row: a subfolder or a .smk file."""

    path: Path
    is_folder: bool
    info: LibraryFileInfo | None = None
    folder_item_count: int = 0

    @property
    def name(self) -> str:
        if self.info is not None:
            return self.info.display_name
        return self.path.name

    @property
    def modified_at(self) -> datetime | None:
        if self.info is not None:
            return self.info.modified_at
        try:
            return datetime.fromtimestamp(self.path.stat().st_mtime)
        except OSError:
            return None

    @property
    def captured_at(self) -> datetime | None:
        return self.info.captured_at if self.info is not None else None

    @property
    def size(self) -> int:
        return self.info.file_size if self.info is not None else 0


def human_size(num: int) -> str:
    """Human-readable byte count (e.g. ``1.2 MB``)."""
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def format_datetime(dt: datetime | None) -> str:
    """Local-time display such as ``Mar 1, 2026 2:23 PM``."""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    # %-d and %-I are glibc extensions that raise ValueError on Windows, so the
    # unpadded day and hour are composed here instead.
    hour = dt.hour % 12 or 12
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} {hour}:{dt.strftime('%M %p')}"


class LibraryModel(QAbstractTableModel):
    """Rows for the current folder; sorting and filtering are applied in-model.

    Signals
    -------
    current_path_changed(object)
        Folder navigation happened (Path).
    rename_requested(object, str)
        The user finished an inline edit: (Path, new name).
    move_requested(list, object)
        Internal drag-and-drop onto a folder: (list[Path], destination Path).
    import_requested(list, object)
        External files dropped: (list[Path], destination Path).
    """

    current_path_changed = pyqtSignal(object)
    rename_requested = pyqtSignal(object, str)
    move_requested = pyqtSignal(list, object)
    import_requested = pyqtSignal(list, object)

    def __init__(self, manager: LibraryManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._current = manager.root
        self._entries: list[LibraryEntry] = []
        self._all_files: list[LibraryEntry] = []
        self._folders: list[LibraryEntry] = []
        self._sort_key = "date_modified"
        self._descending = True
        self._filter = ""
        self._thumb_size = 128
        self._info_cache: dict[str, tuple[float, int, LibraryFileInfo]] = {}
        self._pixmap_cache: dict[tuple[str, float, int], QPixmap] = {}
        self._is_open: Callable[[Path], bool] = lambda _p: False
        self._export_for_drag: Callable[[list[Path]], list[Path]] | None = None
        manager.root_changed.connect(self._on_root_changed)
        manager.files_changed.connect(self.refresh)
        manager.file_written.connect(self._on_file_written)
        self.refresh()

    # --- configuration ---

    @property
    def manager(self) -> LibraryManager:
        return self._manager

    @property
    def current_path(self) -> Path:
        return self._current

    def set_is_open_provider(self, fn: Callable[[Path], bool]) -> None:
        self._is_open = fn

    def set_drag_exporter(self, fn: Callable[[list[Path]], list[Path]] | None) -> None:
        """Provide a function that renders files to PNGs for drag-out to the OS."""
        self._export_for_drag = fn

    @property
    def thumb_size(self) -> int:
        return self._thumb_size

    def set_thumb_size(self, size: int) -> None:
        if size == self._thumb_size:
            return
        self._thumb_size = size
        if self._entries:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._entries) - 1, 0),
                [Qt.ItemDataRole.DecorationRole],
            )

    def set_sort_id(self, sort_id: str) -> None:
        key, _, direction = sort_id.rpartition("_")
        self.set_sort(key or "date_modified", direction == "desc")

    @property
    def sort_id(self) -> str:
        return f"{self._sort_key}_{'desc' if self._descending else 'asc'}"

    def set_sort(self, key: str, descending: bool) -> None:
        self._sort_key = key
        self._descending = descending
        self._rebuild()

    def set_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self._rebuild()

    @property
    def filter_text(self) -> str:
        return self._filter

    # --- navigation ---

    def navigate_to(self, path: Path) -> None:
        if not path.is_dir():
            return
        self._current = path
        self.refresh()
        self.current_path_changed.emit(path)

    def go_up(self) -> None:
        if self.can_go_up:
            self.navigate_to(self._current.parent)

    @property
    def can_go_up(self) -> bool:
        return self._current.resolve() != self._manager.root.resolve()

    def breadcrumbs(self) -> list[tuple[str, Path]]:
        """(label, path) pairs from the library root to the current folder."""
        root = self._manager.root.resolve()
        cur = self._current.resolve()
        crumbs: list[tuple[str, Path]] = []
        try:
            rel = cur.relative_to(root)
        except ValueError:
            return [(root.name or str(root), self._manager.root)]
        crumbs.append((root.name or str(root), self._manager.root))
        acc = self._manager.root
        for part in rel.parts:
            acc = acc / part
            crumbs.append((part, acc))
        return crumbs

    def _on_root_changed(self, root: Path) -> None:
        self._current = root
        self._info_cache.clear()
        self._pixmap_cache.clear()
        self.refresh()
        self.current_path_changed.emit(root)

    def _on_file_written(self, path: Path) -> None:
        key = str(path)
        self._info_cache.pop(key, None)
        for k in [k for k in self._pixmap_cache if k[0] == key]:
            self._pixmap_cache.pop(k, None)
        row = self.row_for_path(path)
        if row >= 0:
            self._entries[row].info = self._load_info(path)
            self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1))
        else:
            self.refresh()

    # --- loading ---

    def refresh(self) -> None:
        if not self._current.is_dir():
            self._current = self._manager.root
        self._folders = [
            LibraryEntry(p, True, None, self._manager.folder_item_count(p))
            for p in self._manager.list_folders(self._current)
        ]
        files: list[LibraryEntry] = []
        for p in sorted(self._current.glob("*.smk")):
            if not p.is_file():
                continue
            files.append(LibraryEntry(p, False, self._load_info(p)))
        self._all_files = files
        self._rebuild()

    def _load_info(self, path: Path) -> LibraryFileInfo:
        key = str(path)
        try:
            st = path.stat()
            stamp = (st.st_mtime, st.st_size)
        except OSError:
            stamp = (0.0, 0)
        cached = self._info_cache.get(key)
        if cached is not None and (cached[0], cached[1]) == stamp:
            return cached[2]
        info = LibraryFileInfo.from_path(path)
        self._info_cache[key] = (stamp[0], stamp[1], info)
        return info

    def _rebuild(self) -> None:
        self.beginResetModel()
        files = self._all_files
        if self._filter:
            files = [e for e in files if self._filter in e.name.lower()]
        self._entries = self._sorted(self._folders) + self._sorted(files)
        self.endResetModel()

    def _sorted(self, entries: list[LibraryEntry]) -> list[LibraryEntry]:
        key = self._sort_key
        if key == "name":
            return sorted(entries, key=lambda e: e.name.lower(), reverse=self._descending)
        if key == "size":
            return sorted(entries, key=lambda e: e.size, reverse=self._descending)
        if key == "date_captured":

            def cap(e: LibraryEntry) -> float:
                return e.captured_at.timestamp() if e.captured_at else 0.0

            return sorted(entries, key=cap, reverse=self._descending)

        def mod(e: LibraryEntry) -> float:
            return e.modified_at.timestamp() if e.modified_at else 0.0

        return sorted(entries, key=mod, reverse=self._descending)

    # --- counts ---

    @property
    def file_count(self) -> int:
        return sum(1 for e in self._entries if not e.is_folder)

    @property
    def total_file_count(self) -> int:
        return len(self._all_files)

    @property
    def folder_count(self) -> int:
        return len(self._folders)

    # --- lookup ---

    def entry(self, index: QModelIndex) -> LibraryEntry | None:
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None
        return self._entries[index.row()]

    def row_for_path(self, path: Path) -> int:
        for i, e in enumerate(self._entries):
            if e.path == path:
                return i
        return -1

    def entries(self) -> list[LibraryEntry]:
        return list(self._entries)

    # --- QAbstractTableModel ---

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMN_TITLES)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMN_TITLES[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        entry = self.entry(index)
        if index.column() == COL_NAME:
            base |= Qt.ItemFlag.ItemIsEditable
        if entry is not None and entry.is_folder:
            base |= Qt.ItemFlag.ItemIsDropEnabled
        return base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: C901
        entry = self.entry(index)
        if entry is None:
            return None
        col = index.column()
        if role == PATH_ROLE:
            return entry.path
        if role == IS_FOLDER_ROLE:
            return entry.is_folder
        if role == INFO_ROLE:
            return entry.info
        if role == IS_OPEN_ROLE:
            return (not entry.is_folder) and self._is_open(entry.path)
        if role == SUBTITLE_ROLE:
            if entry.is_folder:
                return f"{entry.folder_item_count} items"
            return format_datetime(entry.modified_at)
        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_NAME:
                return entry.name
            if entry.is_folder:
                return "" if col != COL_MODIFIED else format_datetime(entry.modified_at)
            if col == COL_SIZE:
                return human_size(entry.size)
            if col == COL_MODIFIED:
                return format_datetime(entry.modified_at)
            if col == COL_CAPTURED:
                return format_datetime(entry.captured_at)
        if role == Qt.ItemDataRole.EditRole and col == COL_NAME:
            return entry.name
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(entry.path)
        if role == Qt.ItemDataRole.DecorationRole and col == COL_NAME:
            return self._decoration(entry)
        return None

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:  # noqa: N802
        entry = self.entry(index)
        if entry is None or role != Qt.ItemDataRole.EditRole or index.column() != COL_NAME:
            return False
        new_name = str(value).strip()
        if not new_name or new_name == entry.name:
            return False
        self.rename_requested.emit(entry.path, new_name)
        return True

    # --- decorations ---

    def _decoration(self, entry: LibraryEntry) -> QIcon | QPixmap:
        if entry.is_folder:
            return self._folder_pixmap(entry)
        info = entry.info
        stamp = info.modified_at.timestamp() if info and info.modified_at else 0.0
        key = (str(entry.path), stamp, self._thumb_size)
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached
        thumb = info.thumbnail if info is not None else None
        pix = self._framed(thumb, self._thumb_size)
        self._pixmap_cache[key] = pix
        return pix

    def _framed(self, thumb: QPixmap | None, size: int) -> QPixmap:
        canvas = QPixmap(size, size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        if thumb is not None and not thumb.isNull():
            scaled = thumb.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (size - scaled.width()) // 2
            y = (size - scaled.height()) // 2
            painter.fillRect(x, y, scaled.width(), scaled.height(), QColor("white"))
            painter.drawPixmap(x, y, scaled)
            painter.setPen(QColor(0, 0, 0, 60))
            painter.drawRect(x, y, scaled.width() - 1, scaled.height() - 1)
        else:
            style = QApplication.style()
            if style is not None:
                icon = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
                icon.paint(painter, 0, 0, size, size)
        painter.end()
        return canvas

    def _folder_pixmap(self, entry: LibraryEntry) -> QPixmap:
        key = (str(entry.path), -1.0, self._thumb_size)
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached
        size = self._thumb_size
        canvas = QPixmap(size, size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        style = QApplication.style()
        if style is not None:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            icon.paint(painter, 0, 0, size, size)
        # Mosaic of the first four files inside
        previews: list[QPixmap] = []
        try:
            for p in sorted(entry.path.glob("*.smk"))[:4]:
                t = LibraryFileInfo.from_path(p).thumbnail
                if t is not None:
                    previews.append(t)
        except OSError:
            previews = []
        if previews:
            cell = max(8, size // 3)
            margin = size // 6
            for i, t in enumerate(previews):
                x = margin + (i % 2) * cell
                y = margin + (i // 2) * cell + size // 8
                scaled = t.scaled(cell - 2, cell - 2, Qt.AspectRatioMode.KeepAspectRatio)
                painter.drawPixmap(x, y, scaled)
        painter.end()
        self._pixmap_cache[key] = canvas
        return canvas

    # --- drag and drop ---

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def supportedDragActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def mimeTypes(self) -> list[str]:  # noqa: N802
        return [LIBRARY_PATHS_MIME, "text/uri-list"]

    def mimeData(self, indexes: Iterable[QModelIndex]) -> QMimeData:  # noqa: N802
        paths: list[Path] = []
        for idx in indexes:
            if idx.column() != COL_NAME:
                continue
            entry = self.entry(idx)
            if entry is not None and entry.path not in paths:
                paths.append(entry.path)
        mime = QMimeData()
        mime.setData(LIBRARY_PATHS_MIME, "\n".join(str(p) for p in paths).encode("utf-8"))
        files = [p for p in paths if not self._is_folder_path(p)]
        urls: list[QUrl] = []
        if self._export_for_drag is not None and files:
            urls = [QUrl.fromLocalFile(str(p)) for p in self._export_for_drag(files)]
        if urls:
            mime.setUrls(urls)
        return mime

    def canDropMimeData(  # noqa: N802
        self,
        data: QMimeData | None,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        if data is None:
            return False
        if data.hasFormat(LIBRARY_PATHS_MIME):
            target = self.entry(parent)
            return target is not None and target.is_folder
        return data.hasUrls()

    def dropMimeData(  # noqa: N802
        self,
        data: QMimeData | None,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        if data is None:
            return False
        target = self.entry(parent)
        dest = target.path if target is not None and target.is_folder else self._current
        if data.hasFormat(LIBRARY_PATHS_MIME):
            raw = bytes(data.data(LIBRARY_PATHS_MIME).data()).decode("utf-8")
            paths = [Path(line) for line in raw.splitlines() if line]
            paths = [p for p in paths if p.parent != dest and p != dest]
            if paths:
                self.move_requested.emit(paths, dest)
            return True
        if data.hasUrls():
            local = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile()]
            local = [p for p in local if self._manager.is_importable(p)]
            if local:
                self.import_requested.emit(local, dest)
            return True
        return False

    @staticmethod
    def _is_folder_path(path: Path) -> bool:
        return path.is_dir()
