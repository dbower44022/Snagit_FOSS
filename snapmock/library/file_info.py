"""LibraryFileInfo — in-memory facts about one .smk file in the library."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PyQt6.QtGui import QPixmap

from snapmock.io.project_serializer import read_project_summary, read_thumbnail


@dataclass
class LibraryFileInfo:
    """Display and management data for a library file (Library PRD 9.1)."""

    file_path: Path
    display_name: str
    file_size: int = 0
    captured_at: datetime | None = None
    modified_at: datetime | None = None
    canvas_width: int = 0
    canvas_height: int = 0
    layer_count: int = 0
    item_count: int = 0
    source: str = ""
    is_open: bool = False
    is_valid: bool = True
    _thumbnail: QPixmap | None = field(default=None, repr=False, compare=False)
    _thumbnail_loaded: bool = field(default=False, repr=False, compare=False)

    @classmethod
    def from_path(cls, path: Path) -> LibraryFileInfo:
        """Build an info record from disk. Never raises; bad files are flagged invalid."""
        info = cls(file_path=path, display_name=path.stem)
        try:
            st = path.stat()
            info.file_size = st.st_size
            info.modified_at = datetime.fromtimestamp(st.st_mtime)
        except OSError:
            info.is_valid = False
            return info
        try:
            summary = read_project_summary(path)
        except (OSError, zipfile.BadZipFile, KeyError, ValueError):
            info.is_valid = False
            return info
        info.canvas_width = summary["canvas_width"]
        info.canvas_height = summary["canvas_height"]
        info.layer_count = summary["layer_count"]
        info.item_count = summary["item_count"]
        meta = summary.get("library_metadata") or {}
        name = meta.get("display_name")
        if isinstance(name, str) and name:
            info.display_name = name
        info.source = str(meta.get("source", ""))
        captured = meta.get("captured_at")
        if isinstance(captured, str) and captured:
            info.captured_at = _parse_iso(captured)
        return info

    @property
    def thumbnail(self) -> QPixmap | None:
        """Lazily loaded thumbnail from the archive (None if absent)."""
        if not self._thumbnail_loaded:
            self._thumbnail_loaded = True
            self._thumbnail = read_thumbnail(self.file_path) if self.is_valid else None
        return self._thumbnail

    def invalidate_thumbnail(self) -> None:
        self._thumbnail = None
        self._thumbnail_loaded = False


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
