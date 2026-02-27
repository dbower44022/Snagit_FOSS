"""Path utilities — point simplification and smoothing algorithms."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF


def _perpendicular_distance(point: QPointF, line_start: QPointF, line_end: QPointF) -> float:
    """Compute the perpendicular distance from *point* to the line (start→end)."""
    dx = line_end.x() - line_start.x()
    dy = line_end.y() - line_start.y()
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(point.x() - line_start.x(), point.y() - line_start.y())
    t = ((point.x() - line_start.x()) * dx + (point.y() - line_start.y()) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    proj_x = line_start.x() + t * dx
    proj_y = line_start.y() + t * dy
    return math.hypot(point.x() - proj_x, point.y() - proj_y)


def simplify_rdp(points: list[QPointF], epsilon: float = 2.0) -> list[QPointF]:
    """Simplify a polyline using the Ramer-Douglas-Peucker algorithm.

    Parameters
    ----------
    points : list[QPointF]
        The input polyline.
    epsilon : float
        Maximum deviation threshold.  Larger values produce more simplification.

    Returns
    -------
    list[QPointF]
        The simplified polyline.
    """
    if len(points) <= 2:
        return list(points)

    # Find the point with the maximum distance from the start→end line
    max_dist = 0.0
    max_idx = 0
    for i in range(1, len(points) - 1):
        d = _perpendicular_distance(points[i], points[0], points[-1])
        if d > max_dist:
            max_dist = d
            max_idx = i

    if max_dist > epsilon:
        left = simplify_rdp(points[: max_idx + 1], epsilon)
        right = simplify_rdp(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]
