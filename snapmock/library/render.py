"""Render library files without opening them in a tab."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from PyQt6.QtGui import QImage

from snapmock.core.render_engine import RenderEngine
from snapmock.io.exporter import ExportSettings, export_scene
from snapmock.io.project_serializer import load_project
from snapmock.library.file_info import LibraryFileInfo


def render_file_to_image(path: Path) -> QImage | None:
    """Load a .smk file and return its flattened rendering, or None on failure."""
    try:
        scene = load_project(path)
    except (OSError, zipfile.BadZipFile, KeyError, ValueError):
        return None
    image = RenderEngine(scene).render_to_image()
    scene.deleteLater()
    return image


def export_target(path: Path, out_dir: Path, settings: ExportSettings) -> Path:
    """``out_dir/<display name><suffix>`` for a library file (Library PRD 7.2)."""
    name = LibraryFileInfo.from_path(path).display_name or path.stem
    return out_dir / f"{name}{settings.format.suffix}"


def export_file(path: Path, target: Path, settings: ExportSettings) -> str | None:
    """Export one .smk to *target* with the Export dialog's *settings*.

    Returns an error message, or None when the file was written.
    """
    try:
        scene = load_project(path)
    except (OSError, zipfile.BadZipFile, KeyError, ValueError):
        return f"{path.name}: could not be opened"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        export_scene(scene, target, settings, source_file=path)
    except OSError as exc:
        return f"{path.name}: could not write {target.name} ({exc.strerror or exc})"
    finally:
        scene.deleteLater()
    if not target.exists():
        return f"{path.name}: could not write {target.name}"
    return None


def export_files_to_png(paths: list[Path], out_dir: Path) -> tuple[list[Path], list[str]]:
    """Export each .smk in *paths* to ``out_dir/<stem>.png``.

    Returns (written paths, error messages). Errors do not stop the batch.
    """
    written: list[Path] = []
    errors: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in paths:
        image = render_file_to_image(p)
        if image is None:
            errors.append(f"{p.name}: could not be opened")
            continue
        target = out_dir / f"{p.stem}.png"
        if not image.save(str(target), "PNG"):
            errors.append(f"{p.name}: could not write {target.name}")
            continue
        written.append(target)
    return written, errors


def export_for_drag(paths: list[Path]) -> list[Path]:
    """Render files to PNGs in a temp folder so they can be dragged to the OS."""
    out_dir = Path(tempfile.mkdtemp(prefix="snapmock-drag-"))
    written, _errors = export_files_to_png(paths, out_dir)
    return written
