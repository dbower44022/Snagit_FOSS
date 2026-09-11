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
from snapmock.core.command_stack import BaseCommand
from snapmock.core.path_utils import constrain_angle
from snapmock.core.theme_manager import current_theme
from snapmock.items.arrow_item import ArrowItem
from snapmock.items.base_item import SnapGraphicsItem
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

    status_hint: str = "Drag points to reshape. Escape: exit."

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

    status_hint = "Drag endpoints to reshape. Shift: constrain angle. Escape: exit."

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
    """An arrow's endpoints (Basic Shape PRD 4.8: the straight arrow's point editing)."""


def session_for(item: SnapGraphicsItem) -> PointEditSession | None:
    """The point-editing session for *item*, or None when the item has no points to edit."""
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
