"""Tests for export functions."""

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from snapmock.core.scene import SnapScene
from snapmock.io.exporter import export_jpg, export_png


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


def test_export_png(scene: SnapScene, tmp_path: Path) -> None:
    path = tmp_path / "test.png"
    export_png(scene, path)
    assert path.exists()
    assert path.stat().st_size > 0


def test_export_jpg(scene: SnapScene, tmp_path: Path) -> None:
    path = tmp_path / "test.jpg"
    export_jpg(scene, path)
    assert path.exists()
    assert path.stat().st_size > 0
