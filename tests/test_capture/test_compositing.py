"""Tests for frozen-image compositing (PRD 2.2 to 2.4, 4.2, 4.5)."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from snapmock.capture.backend import FakeCaptureBackend
from snapmock.capture.compositing import (
    composite_cursor,
    max_ratio,
    physical_rect_for,
    render_region,
)
from snapmock.capture.models import MonitorInfo


def _two_monitors(ratio_b: float = 1.0) -> list[MonitorInfo]:
    a = MonitorInfo("A", QRect(0, 0, 100, 60), QSize(100, 60), 1.0, True)
    b = MonitorInfo(
        "B", QRect(100, 0, 100, 60), QSize(round(100 * ratio_b), round(60 * ratio_b)), ratio_b
    )
    return [a, b]


def test_physical_rect_rounds_outward() -> None:
    assert physical_rect_for(QRect(1, 1, 3, 3), 1.5) == QRect(1, 1, 5, 5)
    assert physical_rect_for(QRect(10, 20, 30, 40), 2.0) == QRect(20, 40, 60, 80)


def test_render_region_within_one_monitor_is_exact_copy(qapp: QApplication) -> None:
    backend = FakeCaptureBackend(_two_monitors())
    grab = backend.grab_screens(False)
    region = render_region(grab, QRect(10, 5, 20, 10), 1.0)
    assert region.size() == QSize(20, 10)
    assert region.pixel(0, 0) == grab.images["A"].pixel(10, 5)
    assert region.pixel(19, 9) == grab.images["A"].pixel(29, 14)


def test_render_region_spans_two_monitors_same_ratio(qapp: QApplication) -> None:
    backend = FakeCaptureBackend(_two_monitors())
    grab = backend.grab_screens(False)
    region = render_region(grab, QRect(90, 0, 20, 10), 1.0)
    assert region.pixel(0, 0) == grab.images["A"].pixel(90, 0)
    assert region.pixel(19, 0) == grab.images["B"].pixel(9, 0)


def test_render_all_monitors_mixed_ratio_uses_highest_and_fills_black(
    qapp: QApplication,
) -> None:
    monitors = _two_monitors(2.0)
    monitors[1].logical_geometry = QRect(100, 20, 100, 60)  # offset creates a gap
    backend = FakeCaptureBackend(monitors)
    grab = backend.grab_screens(False)
    assert max_ratio(grab.monitors) == 2.0
    image = render_region(grab, grab.virtual_logical_rect, 2.0)
    assert image.size() == QSize(400, 160)
    # The gap below monitor A (rows 120..159 on the left) is black.
    assert QColor(image.pixel(10, 150)) == QColor(0, 0, 0)
    assert QColor(image.pixel(210, 50)) != QColor(0, 0, 0)


def test_composite_cursor_draws_at_hotspot(qapp: QApplication) -> None:
    backend = FakeCaptureBackend(_two_monitors(2.0))
    cursor = QImage(4, 4, QImage.Format.Format_ARGB32)
    cursor.fill(QColor(255, 255, 255))
    backend.fake_cursor_image = cursor
    backend.fake_cursor_hotspot = QPoint(1, 1)
    backend.fake_cursor_position = QPoint(150, 30)  # on B, ratio 2 -> physical (100, 60)
    grab = backend.grab_screens(True)
    assert composite_cursor(grab)
    assert QColor(grab.images["B"].pixel(99, 59)) == QColor(255, 255, 255)
    assert QColor(grab.images["B"].pixel(102, 62)) == QColor(255, 255, 255)
    assert QColor(grab.images["B"].pixel(98, 58)) != QColor(255, 255, 255)


def test_composite_cursor_without_cursor_is_noop(qapp: QApplication) -> None:
    grab = FakeCaptureBackend().grab_screens(False)
    assert composite_cursor(grab) is False
