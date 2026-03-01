"""Tests for raster clipboard operations and paste routing."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=400, height=300)


@pytest.fixture()
def clipboard(scene: SnapScene) -> ClipboardManager:
    return ClipboardManager(scene)


# --- ClipboardManager raster operations ---


def test_clipboard_copy_raster_region(clipboard: ClipboardManager) -> None:
    """copy_raster_region stores image and source rect."""
    img = QImage(50, 30, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 0, 0))
    rect = QRectF(10, 20, 50, 30)

    clipboard.copy_raster_region(img, rect)

    assert clipboard.has_raster
    assert not clipboard.has_internal  # internal items should be cleared


def test_clipboard_paste_raster(clipboard: ClipboardManager) -> None:
    """paste_raster returns stored image and source rect."""
    img = QImage(60, 40, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 255, 0))
    rect = QRectF(5, 10, 60, 40)

    clipboard.copy_raster_region(img, rect)
    result_img, result_rect = clipboard.paste_raster()

    assert result_img is not None
    assert result_img.width() == 60
    assert result_img.height() == 40
    assert result_rect is not None
    assert result_rect.x() == pytest.approx(5)
    assert result_rect.width() == pytest.approx(60)


def test_clipboard_paste_raster_empty(clipboard: ClipboardManager) -> None:
    """paste_raster returns (None, None) when no raster data stored."""
    result_img, result_rect = clipboard.paste_raster()
    assert result_img is None
    assert result_rect is None


def test_clipboard_clear_resets_raster(clipboard: ClipboardManager) -> None:
    """clear() should remove raster data."""
    img = QImage(10, 10, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 255))
    clipboard.copy_raster_region(img, QRectF(0, 0, 10, 10))
    assert clipboard.has_raster

    clipboard.clear()
    assert not clipboard.has_raster
    assert not clipboard.has_internal


def test_clipboard_raster_clears_internal(scene: SnapScene, clipboard: ClipboardManager) -> None:
    """Copying raster data should clear internal item data."""
    # First copy some items
    item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    scene.addItem(item)
    clipboard.copy_items([item])
    assert clipboard.has_internal

    # Now copy raster data
    img = QImage(20, 20, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(128, 128, 128))
    clipboard.copy_raster_region(img, QRectF(0, 0, 20, 20))

    assert clipboard.has_raster
    assert not clipboard.has_internal  # items should be cleared


def test_clipboard_changed_signal_on_raster_copy(
    clipboard: ClipboardManager,
) -> None:
    """clipboard_changed should emit when raster region is copied."""
    signals: list[bool] = []
    clipboard.clipboard_changed.connect(lambda: signals.append(True))

    img = QImage(10, 10, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0))
    clipboard.copy_raster_region(img, QRectF(0, 0, 10, 10))

    assert len(signals) == 1


# --- Paste priority (unit tests on ClipboardManager) ---


def test_paste_items_priority_over_raster(scene: SnapScene, clipboard: ClipboardManager) -> None:
    """Internal items should take priority over raster when both present.

    Actually, copy_raster_region clears internal items, so we can't have both.
    This test verifies that once raster is copied, paste_items returns empty.
    """
    item = RectangleItem(rect=QRectF(0, 0, 50, 50))
    layer = scene.layer_manager.active_layer
    assert layer is not None
    item.layer_id = layer.layer_id
    scene.addItem(item)
    clipboard.copy_items([item])

    # Now copy raster — should clear items
    img = QImage(20, 20, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0))
    clipboard.copy_raster_region(img, QRectF(0, 0, 20, 20))

    assert clipboard.paste_items() == []
    raster, _ = clipboard.paste_raster()
    assert raster is not None
