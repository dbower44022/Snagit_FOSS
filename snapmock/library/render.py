"""Render library files without opening them in a tab."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from PyQt6.QtGui import QImage

from snapmock.core.render_engine import RenderEngine
from snapmock.io.project_serializer import load_project


def render_file_to_image(path: Path) -> QImage | None:
    """Load a .smk file and return its flattened rendering, or None on failure."""
    try:
        scene = load_project(path)
    except (OSError, zipfile.BadZipFile, KeyError, ValueError):
        return None
    image = RenderEngine(scene).render_to_image()
    scene.deleteLater()
    return image


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
