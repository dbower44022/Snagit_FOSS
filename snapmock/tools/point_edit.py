"""Point editing — the control-point handles of Basic Shape PRD 3.5, 4.5, 4.6, 7.5, 8.5, 9.7.

Point-editing mode is a mode of the Select tool (Basic Shape remainder decision 1,
option A): a double-click on a line, an arrow, an arc, a polygon, or a freehand item
starts a :class:`PointEditSession` for it. The session knows the item's handles in scene
coordinates, applies a drag with its modifiers, and builds the command the drag pushes,
a :class:`ModifyGeometryCommand` (11.3). :class:`PointHandlesItem` draws the handles as a
scene item above every annotation item, as the transform handles are drawn.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsItem

from snapmock.commands.geometry_commands import ModifyGeometryCommand, copy_geometry
from snapmock.config.constants import LineStyle
from snapmock.core.command_stack import BaseCommand
from snapmock.core.path_utils import BezierSegment, constrain_angle
from snapmock.core.theme_manager import current_theme
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.freehand_item import FreehandItem
from snapmock.items.line_item import LineItem

CONTROL_COLOR = QColor("#2E9E44")
"""The green of a control point, a bend point, and an off-curve handle (4.5, 9.7)."""

HANDLE_HIT_SLOP = 3.0
"""Scene pixels beyond a handle's radius that still grab it."""

HANDLES_Z = 999998.0


class HandleKind(Enum):
    """How a handle is drawn: its diameter in pixels, colour, and fill (3.5, 4.5, 9.7)."""

    ENDPOINT = "endpoint"  # an 8 px filled circle in the accent colour
    CONTROL = "control"  # a 10 px filled green circle
    ON_CURVE = "on_curve"  # a 6 px filled circle in the accent colour
    OFF_CURVE = "off_curve"  # a 5 px hollow green circle


HANDLE_DIAMETER: dict[HandleKind, float] = {
    HandleKind.ENDPOINT: 8.0,
    HandleKind.CONTROL: 10.0,
    HandleKind.ON_CURVE: 6.0,
    HandleKind.OFF_CURVE: 5.0,
}


@dataclass(frozen=True)
class PointHandle:
    """One draggable point: its key within the session, its scene position, its look."""

    key: str
    pos: QPointF
    kind: HandleKind = HandleKind.ENDPOINT


def _mirror(item: SnapGraphicsItem, point: QPointF) -> QPointF:
    """*point* mirrored as the item's flips mirror its painting (around the bounding-rect
    centre); the mirror is its own inverse."""
    if not (item.flip_horizontal or item.flip_vertical):
        return QPointF(point)
    centre = item.boundingRect().center()
    x = 2.0 * centre.x() - point.x() if item.flip_horizontal else point.x()
    y = 2.0 * centre.y() - point.y() if item.flip_vertical else point.y()
    return QPointF(x, y)


class PointEditSession:
    """The point editing of one item. Subclasses name the handles and apply the drags."""

    HINT: str = "Drag points to reshape. Escape: exit."

    @property
    def status_hint(self) -> str:
        """The status bar text while the mode lasts (the PRD's Point editing rows)."""
        return self.HINT

    def __init__(self, item: SnapGraphicsItem) -> None:
        self.item = item
        self._drag_key: str | None = None
        self._drag_property = ""
        self._drag_old: Any = None

    # --- coordinates ---

    def to_scene(self, local: QPointF) -> QPointF:
        """The scene position where the item paints its local point *local*."""
        return self.item.mapToScene(_mirror(self.item, local))

    def to_local(self, scene_pos: QPointF) -> QPointF:
        """The item's local point that paints at *scene_pos*."""
        return _mirror(self.item, self.item.mapFromScene(scene_pos))

    # --- what the subclass supplies ---

    def handles(self) -> list[PointHandle]:
        raise NotImplementedError

    def guide_lines(self) -> list[QLineF]:
        """Dashed lines in scene coordinates, from a control point to its anchors."""
        return []

    def property_for(self, key: str) -> str:
        """The item property a drag of the handle *key* changes."""
        raise NotImplementedError

    def drag_to(self, key: str, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        """Move the handle *key* to *scene_pos*, live."""
        raise NotImplementedError

    def double_click(self, scene_pos: QPointF) -> BaseCommand | None:
        """The command a double-click on the item makes (an inserted point), if any."""
        return None

    def right_click(self, scene_pos: QPointF) -> BaseCommand | None:
        """The command a right-click on a handle makes (a deleted point), if any."""
        return None

    # --- hit testing ---

    def handle_at(self, scene_pos: QPointF) -> str | None:
        """The key of the handle under *scene_pos*; the topmost (last drawn) wins."""
        for handle in reversed(self.handles()):
            reach = HANDLE_DIAMETER[handle.kind] / 2.0 + HANDLE_HIT_SLOP
            delta = handle.pos - scene_pos
            if delta.x() * delta.x() + delta.y() * delta.y() <= reach * reach:
                return handle.key
        return None

    # --- a drag ---

    @property
    def dragging(self) -> str | None:
        return self._drag_key

    def begin_drag(self, key: str) -> None:
        self._drag_key = key
        self._drag_property = self.property_for(key)
        self._drag_old = copy_geometry(getattr(self.item, self._drag_property))

    def cancel_drag(self) -> None:
        """Put the dragged property back as it was before the drag began."""
        if self._drag_key is not None:
            setattr(self.item, self._drag_property, copy_geometry(self._drag_old))
            self._drag_key = None

    def end_drag(self) -> BaseCommand | None:
        """The command for the drag that just ended, or None when nothing moved."""
        key, prop, old = self._drag_key, self._drag_property, self._drag_old
        self._drag_key = None
        if key is None:
            return None
        new = copy_geometry(getattr(self.item, prop))
        if new == old:
            return None
        return ModifyGeometryCommand(self.item, prop, old, new, point=key)


class LinePointSession(PointEditSession):
    """A line's two endpoints (Basic Shape PRD 3.5)."""

    HINT = "Drag endpoints to reshape. Shift: constrain angle. Escape: exit."

    item: LineItem | ArrowItem

    def handles(self) -> list[PointHandle]:
        line = self.item.line
        return [
            PointHandle("start", self.to_scene(line.p1())),
            PointHandle("end", self.to_scene(line.p2())),
        ]

    def property_for(self, key: str) -> str:
        return "line"

    def drag_to(self, key: str, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        line = self.item.line
        if key not in ("start", "end"):
            return
        anchor = self.to_scene(line.p2() if key == "start" else line.p1())
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            scene_pos = constrain_angle(anchor, scene_pos)
        local = self.to_local(scene_pos)
        if key == "start":
            line.setP1(local)
        else:
            line.setP2(local)
        self.item.line = line


class ArrowPointSession(LinePointSession):
    """An arrow's endpoints, and its control point when curved (4.5) or its bend point
    when an elbow (4.6), each as the green handle of 4.5."""

    item: ArrowItem

    @property
    def status_hint(self) -> str:
        style = self.item.line_style
        if style is LineStyle.CURVED:
            return "Drag endpoints or control point to reshape. Escape: exit."
        if style is LineStyle.ELBOW:
            return "Drag endpoints or bend point to reshape. Escape: exit."
        return self.HINT

    def handles(self) -> list[PointHandle]:
        handles = super().handles()
        style = self.item.line_style
        if style is LineStyle.CURVED:
            control = self.to_scene(self.item.effective_control_point())
            handles.append(PointHandle("control", control, HandleKind.CONTROL))
        elif style is LineStyle.ELBOW:
            bend = self.to_scene(self.item.bend_handle_point())
            handles.append(PointHandle("bend", bend, HandleKind.CONTROL))
        return handles

    def guide_lines(self) -> list[QLineF]:
        if self.item.line_style is not LineStyle.CURVED:
            return []
        line = self.item.line
        control = self.to_scene(self.item.effective_control_point())
        return [
            QLineF(control, self.to_scene(line.p1())),
            QLineF(control, self.to_scene(line.p2())),
        ]

    def property_for(self, key: str) -> str:
        if key == "control":
            return "control_point"
        if key == "bend":
            return "bend_point"
        return "line"

    def drag_to(self, key: str, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if key == "control":
            self.item.control_point = self.to_local(scene_pos)
        elif key == "bend":
            # Only across: the bend keeps every segment at a right angle (4.6)
            line = self.item.line
            local = self.to_local(scene_pos)
            self.item.bend_point = QPointF(local.x(), (line.y1() + line.y2()) / 2.0)
        else:
            super().drag_to(key, scene_pos, modifiers)


def _lerp(a: QPointF, b: QPointF, t: float) -> QPointF:
    return QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)


def _cubic_at(seg: BezierSegment, t: float) -> QPointF:
    p0, p1, p2, p3 = seg
    u = 1.0 - t
    return QPointF(
        u**3 * p0.x() + 3 * u * u * t * p1.x() + 3 * u * t * t * p2.x() + t**3 * p3.x(),
        u**3 * p0.y() + 3 * u * u * t * p1.y() + 3 * u * t * t * p2.y() + t**3 * p3.y(),
    )


def split_cubic(seg: BezierSegment, t: float) -> tuple[BezierSegment, BezierSegment]:
    """*seg* split at *t* into two segments that trace the same curve (de Casteljau)."""
    p0, p1, p2, p3 = seg
    a, b, c = _lerp(p0, p1, t), _lerp(p1, p2, t), _lerp(p2, p3, t)
    d, e = _lerp(a, b, t), _lerp(b, c, t)
    f = _lerp(d, e, t)
    return (QPointF(p0), a, d, f), (QPointF(f), e, c, QPointF(p3))


class FreehandPointSession(PointEditSession):
    """A freehand stroke's Bezier points (Basic Shape PRD 9.7): the on-curve points as blue
    6 px circles and each segment's two control handles as green 5 px hollow circles on
    dashed lines to their on-curve point.

    Dragging an on-curve point carries its two handles along, so the curve stays smooth
    through it; dragging a handle turns the opposite handle to stay in line, keeping its
    length. Alt breaks that continuity: the point or the handle moves alone, making a
    corner. A double-click on the stroke inserts an on-curve point there, splitting the
    segment without changing the curve; a right-click on an on-curve point deletes it,
    merging its two segments, while at least two points remain.
    """

    HINT = (
        "Drag points to reshape. Alt+drag: corner. Double-click segment: insert. "
        "Right-click: delete. Escape: exit."
    )

    item: FreehandItem

    @staticmethod
    def _parse(key: str) -> tuple[str, int]:
        """("point", i), ("cp1", i), or ("cp2", i) for a handle key."""
        if key.startswith("p"):
            return "point", int(key[1:])
        return ("cp1" if key.endswith("a") else "cp2"), int(key[1:-1])

    def handles(self) -> list[PointHandle]:
        segments = self.item.bezier_segments
        handles: list[PointHandle] = []
        for i, (_start, cp1, cp2, _end) in enumerate(segments):
            handles.append(PointHandle(f"c{i}a", self.to_scene(cp1), HandleKind.OFF_CURVE))
            handles.append(PointHandle(f"c{i}b", self.to_scene(cp2), HandleKind.OFF_CURVE))
        # The on-curve points last, so they win where a handle lies on its point
        for i, seg in enumerate(segments):
            handles.append(PointHandle(f"p{i}", self.to_scene(seg[0]), HandleKind.ON_CURVE))
        if segments:
            end = self.to_scene(segments[-1][3])
            handles.append(PointHandle(f"p{len(segments)}", end, HandleKind.ON_CURVE))
        return handles

    def guide_lines(self) -> list[QLineF]:
        lines: list[QLineF] = []
        for start, cp1, cp2, end in self.item.bezier_segments:
            lines.append(QLineF(self.to_scene(start), self.to_scene(cp1)))
            lines.append(QLineF(self.to_scene(end), self.to_scene(cp2)))
        return lines

    def property_for(self, key: str) -> str:
        return "bezier_segments"

    def drag_to(self, key: str, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        segs = [list(s) for s in self.item.bezier_segments]
        if not segs:
            return
        local = self.to_local(scene_pos)
        corner = bool(modifiers & Qt.KeyboardModifier.AltModifier)
        kind, i = self._parse(key)
        n = len(segs)
        if kind == "point":
            old = segs[i][0] if i < n else segs[n - 1][3]
            delta = local - old
            if i < n:
                segs[i][0] = QPointF(local)
                if not corner:
                    segs[i][1] = segs[i][1] + delta
            if i > 0:
                segs[i - 1][3] = QPointF(local)
                if not corner:
                    segs[i - 1][2] = segs[i - 1][2] + delta
        elif kind == "cp1":
            segs[i][1] = QPointF(local)
            if not corner and i > 0:
                self._align(segs[i][0], segs[i][1], segs[i - 1], 2)
        else:
            segs[i][2] = QPointF(local)
            if not corner and i + 1 < n:
                self._align(segs[i][3], segs[i][2], segs[i + 1], 1)
        self.item.bezier_segments = [(s[0], s[1], s[2], s[3]) for s in segs]

    @staticmethod
    def _align(anchor: QPointF, moved: QPointF, other: list[QPointF], index: int) -> None:
        """Turn *other*'s handle at *index* to point away from *moved* through *anchor*,
        keeping its length, so the curve stays smooth through the anchor."""
        length = QLineF(anchor, other[index]).length()
        direction = QLineF(moved, anchor)
        if direction.length() <= 1e-9:
            return
        direction.setLength(direction.length() + length)
        other[index] = direction.p2()

    def _nearest_on_path(self, scene_pos: QPointF) -> tuple[int, float, float]:
        """The segment, the parameter, and the distance of the stroke nearest *scene_pos*."""
        local = self.to_local(scene_pos)
        best = (0, 0.0, float("inf"))
        for i, seg in enumerate(self.item.bezier_segments):
            for step in range(1, 64):
                t = step / 64.0
                p = _cubic_at(seg, t)
                d = QLineF(p, local).length()
                if d < best[2]:
                    best = (i, t, d)
        return best

    def double_click(self, scene_pos: QPointF) -> BaseCommand | None:
        segs = self.item.bezier_segments
        if not segs:
            return None
        index, t, distance = self._nearest_on_path(scene_pos)
        if distance > max(self.item.stroke_width / 2.0 + 4.0, 6.0):
            return None
        left, right = split_cubic(segs[index], t)
        new = segs[:index] + [left, right] + segs[index + 1 :]
        return ModifyGeometryCommand(self.item, "bezier_segments", segs, new, point="insert")

    def right_click(self, scene_pos: QPointF) -> BaseCommand | None:
        key = self.handle_at(scene_pos)
        segs = self.item.bezier_segments
        if key is None or not key.startswith("p") or len(segs) < 2:
            return None  # a stroke keeps at least two on-curve points
        i = int(key[1:])
        if i == 0:
            new = segs[1:]
        elif i == len(segs):
            new = segs[:-1]
        else:
            before, after = segs[i - 1], segs[i]
            new = segs[: i - 1] + [(before[0], before[1], after[2], after[3])] + segs[i + 1 :]
        return ModifyGeometryCommand(self.item, "bezier_segments", segs, new, point="delete")


def session_for(item: SnapGraphicsItem) -> PointEditSession | None:
    """The point-editing session for *item*, or None when the item has no points to edit."""
    if isinstance(item, FreehandItem):
        return FreehandPointSession(item)
    if isinstance(item, ArrowItem):
        return ArrowPointSession(item)
    if isinstance(item, LineItem):
        return LinePointSession(item)
    return None


class PointHandlesItem(QGraphicsItem):
    """The handles and guide lines of a point-editing session, drawn above every item.

    Ephemeral user interface, like the transform handles: never serialized, on no layer,
    and not a :class:`SnapGraphicsItem`, so no walk over the annotation items meets it.
    """

    def __init__(self) -> None:
        super().__init__()
        self._handles: list[PointHandle] = []
        self._guides: list[QLineF] = []
        self._rect = QRectF()
        self.setZValue(HANDLES_Z)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    @property
    def handles(self) -> list[PointHandle]:
        return list(self._handles)

    def set_handles(self, handles: list[PointHandle], guides: list[QLineF]) -> None:
        self.prepareGeometryChange()
        self._handles = list(handles)
        self._guides = list(guides)
        rect = QRectF()
        for handle in self._handles:
            r = HANDLE_DIAMETER[handle.kind] / 2.0 + 2.0
            rect = rect.united(QRectF(handle.pos.x() - r, handle.pos.y() - r, 2 * r, 2 * r))
        for guide in self._guides:
            rect = rect.united(QRectF(guide.p1(), guide.p2()).normalized().adjusted(-1, -1, 1, 1))
        self._rect = rect
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(self._rect)

    def paint(self, painter: QPainter | None, option: Any, widget: Any = None) -> None:
        if painter is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        theme = current_theme()
        guide_pen = QPen(theme.selection_outline, 1, Qt.PenStyle.DashLine)
        guide_pen.setCosmetic(True)
        painter.setPen(guide_pen)
        for guide in self._guides:
            painter.drawLine(guide)
        outline = QPen(QColor(255, 255, 255), 1)
        for handle in self._handles:
            r = HANDLE_DIAMETER[handle.kind] / 2.0
            if handle.kind is HandleKind.OFF_CURVE:
                painter.setPen(QPen(CONTROL_COLOR, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
            else:
                color = CONTROL_COLOR if handle.kind is HandleKind.CONTROL else theme.accent
                painter.setPen(outline)
                painter.setBrush(color)
            painter.drawEllipse(handle.pos, r, r)
