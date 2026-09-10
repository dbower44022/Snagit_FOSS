"""Group commands — Group and Ungroup of General UI PRD 3.6, both undoable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QTransform

from snapmock.commands.arrange_commands import apply_layer_z_values
from snapmock.core.command_stack import BaseCommand
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.group_item import GroupItem

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager


def _select(manager: SelectionManager | None, items: list[SnapGraphicsItem]) -> None:
    if manager is not None:
        manager.select_items(list(items))


def _top_level_transform(item: SnapGraphicsItem) -> QTransform:
    """The item-to-scene transform of a member about to become a top-level item."""
    return item.sceneTransform()


def _detach_with_transform(member: SnapGraphicsItem, group: GroupItem) -> None:
    """Make *member* a top-level item at the place the group showed it.

    Qt composes an item's rotation first, then its ``transform()``, then its position,
    so the group's part is folded into the member's transform and position while the
    member's own rotation is kept.
    """
    full = _top_level_transform(member)
    group.remove_member(member)
    new_pos = full.map(QPointF(0, 0))
    rotation_inverse, _ok = QTransform().rotate(member.rotation()).inverted()
    member.setPos(new_pos)
    member.setTransform(
        rotation_inverse * full * QTransform().translate(-new_pos.x(), -new_pos.y())
    )


class GroupItemsCommand(BaseCommand):
    """Combine the selected items into one group on their layer.

    Every item must be a top-level item on the same layer (the window checks both under
    General UI PRD 1.3). The group is placed at the members' top-left, the members keep
    their scene positions and transforms, the group takes the topmost member's place in
    the layer's z-order and ``item_ids``, and the selection becomes the group. Undo puts
    the members back and selects them again.
    """

    def __init__(
        self,
        scene: SnapScene,
        items: list[SnapGraphicsItem],
        selection_manager: SelectionManager | None = None,
    ) -> None:
        self._scene = scene
        self._items = list(items)
        self._selection = selection_manager
        self._layer_id = items[0].layer_id if items else ""
        self._group: GroupItem | None = None
        self._old_positions: list[QPointF] = []
        self._old_locks: list[bool] = []
        self._old_z: list[float] = []
        self._old_item_ids: list[str] = []
        self._new_item_ids: list[str] = []

    @property
    def group(self) -> GroupItem | None:
        return self._group

    def redo(self) -> None:
        layer = self._scene.layer_manager.layer_by_id(self._layer_id)
        if layer is None or not self._items:
            return
        order = {item_id: n for n, item_id in enumerate(layer.item_ids)}
        ordered = sorted(self._items, key=lambda i: (order.get(i.item_id, len(order)), i.zValue()))
        if self._group is None:
            union = QRectF(ordered[0].sceneBoundingRect())
            for item in ordered[1:]:
                union = union.united(item.sceneBoundingRect())
            self._group = GroupItem()
            self._group.setPos(union.topLeft())
            self._old_positions = [QPointF(i.pos()) for i in ordered]
            self._old_locks = [i.locked for i in ordered]
            self._old_z = [i.zValue() for i in ordered]
            self._items = ordered
            self._old_item_ids = list(layer.item_ids)
            member_ids = {i.item_id for i in ordered}
            topmost = ordered[-1].item_id
            new_ids: list[str] = []
            for item_id in layer.item_ids:
                if item_id == topmost:
                    new_ids.append(self._group.item_id)
                elif item_id not in member_ids:
                    new_ids.append(item_id)
            if self._group.item_id not in new_ids:
                new_ids.append(self._group.item_id)
            self._new_item_ids = new_ids
        group = self._group
        top_left = group.pos()
        group.layer_id = self._layer_id
        for index, (item, old_pos) in enumerate(zip(self._items, self._old_positions)):
            item.setPos(old_pos - top_left)
            item.setZValue(index)
            group.add_member(item)
        if group.scene() is not self._scene:
            self._scene.addItem(group)
        layer.item_ids[:] = self._new_item_ids
        apply_layer_z_values(self._scene, self._layer_id)
        _select(self._selection, [group])

    def undo(self) -> None:
        layer = self._scene.layer_manager.layer_by_id(self._layer_id)
        group = self._group
        if layer is None or group is None:
            return
        for item, old_pos, old_lock, old_z in zip(
            self._items, self._old_positions, self._old_locks, self._old_z
        ):
            group.remove_member(item)
            item.setPos(old_pos)
            item.setZValue(old_z)
            item.locked = old_lock
        self._scene.removeItem(group)
        layer.item_ids[:] = self._old_item_ids
        apply_layer_z_values(self._scene, self._layer_id)
        _select(self._selection, self._items)

    @property
    def description(self) -> str:
        return f"Group {len(self._items)} items"


class UngroupItemsCommand(BaseCommand):
    """Dissolve the selected groups into their members, one level at a time.

    Each member returns to the scene as a top-level item with the group's transform
    composed into its own, so its position and shape are what the user saw, in the
    group's place in the layer's z-order. A member that is itself a group stays a group.
    The selection becomes the members; undo rebuilds the groups and selects them.
    """

    def __init__(
        self,
        scene: SnapScene,
        groups: list[GroupItem],
        selection_manager: SelectionManager | None = None,
    ) -> None:
        self._scene = scene
        self._groups = [g for g in groups if isinstance(g, GroupItem)]
        self._selection = selection_manager
        # Per group: its members bottom first, each with the position and transform it
        # had inside the group.
        self._members: dict[str, list[tuple[SnapGraphicsItem, QPointF, QTransform, float]]] = {}
        self._old_item_ids: dict[str, list[str]] = {}
        self._new_item_ids: dict[str, list[str]] = {}

    def redo(self) -> None:
        manager = self._scene.layer_manager
        released: list[SnapGraphicsItem] = []
        touched: set[str] = set()
        for group in self._groups:
            layer = manager.layer_by_id(group.layer_id)
            if layer is None:
                continue
            if layer.layer_id not in self._old_item_ids:
                self._old_item_ids[layer.layer_id] = list(layer.item_ids)
            members = group.members
            self._members[group.item_id] = [
                (m, QPointF(m.pos()), QTransform(m.transform()), m.zValue()) for m in members
            ]
            for member in members:
                _detach_with_transform(member, group)
            self._scene.removeItem(group)
            ids = layer.item_ids
            member_ids = [m.item_id for m in members]
            if group.item_id in ids:
                at = ids.index(group.item_id)
                ids[at : at + 1] = member_ids
            else:
                ids.extend(member_ids)
            touched.add(layer.layer_id)
            released.extend(members)
        for layer_id in touched:
            layer = manager.layer_by_id(layer_id)
            if layer is not None:
                self._new_item_ids[layer_id] = list(layer.item_ids)
            apply_layer_z_values(self._scene, layer_id)
        _select(self._selection, released)

    def undo(self) -> None:
        manager = self._scene.layer_manager
        for group in self._groups:
            records = self._members.get(group.item_id)
            if records is None:
                continue
            if group.scene() is not self._scene:
                self._scene.addItem(group)
            for member, pos, transform, z in records:
                member.setPos(pos)
                member.setTransform(transform)
                member.setZValue(z)
                group.add_member(member)
        for layer_id, ids in self._old_item_ids.items():
            layer = manager.layer_by_id(layer_id)
            if layer is not None:
                layer.item_ids[:] = ids
            apply_layer_z_values(self._scene, layer_id)
        _select(self._selection, list(self._groups))

    @property
    def description(self) -> str:
        count = len(self._groups)
        return "Ungroup" if count == 1 else f"Ungroup {count} groups"
