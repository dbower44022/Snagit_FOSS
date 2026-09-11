"""Stamp library — the index of built-in and custom stamps and their SVG rendering.

Numbered Steps, Stamps & Emoji PRD Section 3.2: the built-in stamps live under
``resources/stamps/<category>/`` with ``stamp_index.json`` beside them; the user's custom
stamps live under the application data directory (``stamps/custom/``) with their own
index and are merged in; both are loaded once and cached. Colorizable stamps carry the
placeholder colours ``#FF0000`` (primary) and ``#0000FF`` (secondary), substituted at
render time. A stamp the index does not know renders as the missing-stamp placeholder
(PRD 7.2). This is not the capture Library of ``snapmock/library/``.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from PyQt6.QtGui import QColor
from PyQt6.QtSvg import QSvgRenderer

from snapmock.core.theme_manager import RESOURCES_DIR
from snapmock.core.tool_themes import application_data_directory

BUILTIN_STAMPS_DIR = RESOURCES_DIR / "stamps"
INDEX_FILENAME = "stamp_index.json"
CUSTOM_CATEGORY = "custom"
PRIMARY_PLACEHOLDER = "#FF0000"
SECONDARY_PLACEHOLDER = "#0000FF"
DEFAULT_STAMP_SIZE = 48.0
STAMP_SIZE_MIN = 16.0
STAMP_SIZE_MAX = 512.0
INDEX_FORMAT_VERSION = 1

BUILTIN = "builtin"
CUSTOM = "custom"
EMBEDDED = "embedded"

_PRIMARY_RE = re.compile(re.escape(PRIMARY_PLACEHOLDER), re.IGNORECASE)
_SECONDARY_RE = re.compile(re.escape(SECONDARY_PLACEHOLDER), re.IGNORECASE)
_RENDERER_CACHE_MAX = 256

PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" '
    'fill="none" stroke="#888888" stroke-width="3" stroke-linecap="round" '
    'stroke-linejoin="round"><rect x="6" y="6" width="52" height="52" rx="6" '
    'stroke-dasharray="6 5"/><path d="M24 26a8 8 0 1 1 12 7c-3 2 -4 3 -4 7"/>'
    '<circle cx="32" cy="48" r="1.5" fill="#888888"/></svg>'
)
"""The missing-stamp icon (PRD 7.2): a dashed square with a question mark."""


@dataclass(frozen=True)
class StampInfo:
    """One index entry (PRD 3.2)."""

    id: str
    name: str
    category: str
    filename: str
    tags: tuple[str, ...] = ()
    default_size: float = DEFAULT_STAMP_SIZE
    colorizable: bool = True
    source: str = BUILTIN
    """``builtin`` or ``custom``; an item's ``embedded`` never appears in an index."""
    path: Path | None = field(default=None, compare=False)
    """The SVG file, resolved against the index's directory."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "filename": self.filename,
            "tags": list(self.tags),
            "default_size": self.default_size,
            "colorizable": self.colorizable,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any], root: Path, source: str) -> StampInfo | None:
        stamp_id = raw.get("id")
        filename = raw.get("filename")
        if not isinstance(stamp_id, str) or not isinstance(filename, str):
            return None
        tags = raw.get("tags", [])
        return cls(
            id=stamp_id,
            name=str(raw.get("name", stamp_id.rsplit("/", 1)[-1])),
            category=str(raw.get("category", stamp_id.split("/", 1)[0])),
            filename=filename,
            tags=tuple(str(t) for t in tags) if isinstance(tags, list) else (),
            default_size=_clamp_size(raw.get("default_size", DEFAULT_STAMP_SIZE)),
            colorizable=bool(raw.get("colorizable", True)),
            source=source,
            path=root / filename,
        )


def _clamp_size(value: object) -> float:
    try:
        size = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_STAMP_SIZE
    return max(STAMP_SIZE_MIN, min(STAMP_SIZE_MAX, size))


def substitute_colors(svg: str, primary: QColor, secondary: QColor) -> str:
    """*svg* with the two placeholder colours replaced (PRD 3.9), case-insensitively."""
    out = _PRIMARY_RE.sub(primary.name(QColor.NameFormat.HexRgb), svg)
    return _SECONDARY_RE.sub(secondary.name(QColor.NameFormat.HexRgb), out)


def has_secondary_region(svg: str) -> bool:
    """Whether *svg* uses the secondary placeholder (PRD 3.6: the second swatch)."""
    return _SECONDARY_RE.search(svg) is not None


def _read_index(root: Path, source: str) -> tuple[list[StampInfo], list[dict[str, str]]]:
    path = root / INDEX_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], []
    if not isinstance(data, dict):
        return [], []
    stamps: list[StampInfo] = []
    for raw in data.get("stamps", []):
        if isinstance(raw, dict):
            info = StampInfo.from_dict(raw, root, source)
            if info is not None:
                stamps.append(info)
    categories = [
        {"id": str(c.get("id", "")), "name": str(c.get("name", c.get("id", "")))}
        for c in data.get("categories", [])
        if isinstance(c, dict) and c.get("id")
    ]
    return stamps, categories


def default_custom_directory() -> Path:
    """Where imported stamps go (PRD 3.8): ``<application data>/stamps/custom``."""
    return application_data_directory() / "stamps" / CUSTOM_CATEGORY


class StampLibrary:
    """The merged built-in and custom index, the SVG data, and the renderer cache."""

    def __init__(self, builtin_dir: Path | None = None, custom_dir: Path | None = None) -> None:
        self._builtin_dir = builtin_dir if builtin_dir is not None else BUILTIN_STAMPS_DIR
        self._custom_dir = custom_dir if custom_dir is not None else default_custom_directory()
        self._stamps: dict[str, StampInfo] | None = None
        self._categories: list[dict[str, str]] = []
        self._svg_cache: dict[str, str] = {}
        self._renderers: dict[tuple[str, str, str, bool], QSvgRenderer] = {}

    # --- the index ---

    @property
    def custom_directory(self) -> Path:
        return self._custom_dir

    def reload(self) -> None:
        """Drop the caches; the next access reads the indexes again."""
        self._stamps = None
        self._svg_cache.clear()
        self._renderers.clear()

    def _ensure_loaded(self) -> dict[str, StampInfo]:
        if self._stamps is None:
            builtin, categories = _read_index(self._builtin_dir, BUILTIN)
            custom, _ = _read_index(self._custom_dir, CUSTOM)
            merged: dict[str, StampInfo] = {}
            for info in [*builtin, *custom]:
                merged[info.id] = info
            self._stamps = merged
            self._categories = categories
        return self._stamps

    def stamps(self) -> list[StampInfo]:
        """Every stamp, built-in first in index order, then custom."""
        return list(self._ensure_loaded().values())

    def stamp(self, stamp_id: str) -> StampInfo | None:
        return self._ensure_loaded().get(stamp_id)

    def categories(self) -> list[tuple[str, str]]:
        """The built-in categories as (id, name), then Custom (PRD 3.4)."""
        self._ensure_loaded()
        out = [(c["id"], c["name"]) for c in self._categories]
        out.append((CUSTOM_CATEGORY, "Custom"))
        return out

    def in_category(self, category: str) -> list[StampInfo]:
        if category == CUSTOM_CATEGORY:
            return [s for s in self.stamps() if s.source == CUSTOM]
        return [s for s in self.stamps() if s.category == category and s.source == BUILTIN]

    def search(self, query: str) -> list[StampInfo]:
        """The stamps whose name or tags contain every word of *query* (PRD 3.4)."""
        words = [w for w in query.casefold().split() if w]
        if not words:
            return self.stamps()
        found = []
        for info in self.stamps():
            haystack = " ".join([info.name, *info.tags]).casefold()
            if all(w in haystack for w in words):
                found.append(info)
        return found

    # --- the SVG data ---

    def svg_data(self, stamp_id: str) -> str | None:
        """The stamp's SVG text, read once; None for an unknown or unreadable stamp."""
        cached = self._svg_cache.get(stamp_id)
        if cached is not None:
            return cached
        info = self.stamp(stamp_id)
        if info is None or info.path is None:
            return None
        try:
            text = info.path.read_text(encoding="utf-8")
        except OSError:
            return None
        self._svg_cache[stamp_id] = text
        return text

    def renderer(
        self,
        svg: str,
        primary: QColor | None = None,
        secondary: QColor | None = None,
        *,
        colorizable: bool = True,
    ) -> QSvgRenderer:
        """A cached renderer for *svg* with the colours substituted (PRD 3.9).

        An SVG that does not parse renders the placeholder instead.
        """
        primary = primary if primary is not None else QColor(PRIMARY_PLACEHOLDER)
        secondary = secondary if secondary is not None else QColor(SECONDARY_PLACEHOLDER)
        key = (
            svg,
            primary.name(QColor.NameFormat.HexRgb) if colorizable else "",
            secondary.name(QColor.NameFormat.HexRgb) if colorizable else "",
            colorizable,
        )
        cached = self._renderers.get(key)
        if cached is not None:
            return cached
        data = substitute_colors(svg, primary, secondary) if colorizable else svg
        renderer = QSvgRenderer(data.encode("utf-8"))
        if not renderer.isValid():
            renderer = QSvgRenderer(PLACEHOLDER_SVG.encode("utf-8"))
        if len(self._renderers) >= _RENDERER_CACHE_MAX:
            self._renderers.clear()
        self._renderers[key] = renderer
        return renderer

    def placeholder_renderer(self) -> QSvgRenderer:
        """The missing-stamp icon (PRD 7.2)."""
        return self.renderer(PLACEHOLDER_SVG, colorizable=False)

    # --- custom stamps (PRD 3.8) ---

    def import_svg(
        self,
        source_path: Path,
        *,
        name: str | None = None,
        tags: tuple[str, ...] = (),
        colorizable: bool = True,
        default_size: float = DEFAULT_STAMP_SIZE,
    ) -> StampInfo:
        """Copy *source_path* into the custom directory and add it to the custom index.

        The id is ``custom/<stem>``, made unique with a numeric suffix. Raises OSError when
        the file cannot be read or copied and ValueError when it is not an SVG QtSvg
        accepts.
        """
        text = source_path.read_text(encoding="utf-8")
        if not QSvgRenderer(text.encode("utf-8")).isValid():
            raise ValueError(f"{source_path.name} is not an SVG file QtSvg can read")
        self._custom_dir.mkdir(parents=True, exist_ok=True)
        existing = self._ensure_loaded()
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", source_path.stem).strip("-").lower() or "stamp"
        candidate = stem
        n = 2
        while (
            f"{CUSTOM_CATEGORY}/{candidate}" in existing
            or (self._custom_dir / f"{candidate}.svg").exists()
        ):
            candidate = f"{stem}-{n}"
            n += 1
        filename = f"{candidate}.svg"
        shutil.copyfile(source_path, self._custom_dir / filename)
        info = StampInfo(
            id=f"{CUSTOM_CATEGORY}/{candidate}",
            name=name or source_path.stem,
            category=CUSTOM_CATEGORY,
            filename=filename,
            tags=tuple(t for t in tags if t),
            default_size=_clamp_size(default_size),
            colorizable=colorizable,
            source=CUSTOM,
            path=self._custom_dir / filename,
        )
        self._write_custom_index([*self.in_category(CUSTOM_CATEGORY), info])
        self.reload()
        return info

    def update_custom(self, info: StampInfo) -> None:
        """Rewrite a custom stamp's metadata (name, tags, colorizable, size)."""
        entries = [s for s in self.in_category(CUSTOM_CATEGORY) if s.id != info.id]
        entries.append(replace(info, source=CUSTOM))
        self._write_custom_index(entries)
        self.reload()

    def remove_custom(self, stamp_id: str) -> bool:
        """Delete a custom stamp's file and index entry; False when it is not custom."""
        info = self.stamp(stamp_id)
        if info is None or info.source != CUSTOM:
            return False
        if info.path is not None:
            try:
                info.path.unlink()
            except OSError:
                pass
        self._write_custom_index(
            [s for s in self.in_category(CUSTOM_CATEGORY) if s.id != stamp_id]
        )
        self.reload()
        return True

    def _write_custom_index(self, entries: list[StampInfo]) -> None:
        self._custom_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "format_version": INDEX_FORMAT_VERSION,
            "stamps": [e.to_dict() for e in entries],
        }
        (self._custom_dir / INDEX_FILENAME).write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )


_default: StampLibrary | None = None


def stamp_library() -> StampLibrary:
    """The application's library over the built-in and the user's custom stamps."""
    global _default
    if _default is None:
        _default = StampLibrary()
    return _default


def set_stamp_library(library: StampLibrary | None) -> None:
    """Replace the application's library (tests)."""
    global _default
    _default = library
