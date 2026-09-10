"""Group and Ungroup (General UI PRD 3.6): the group item, its commands, and the walks."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QTransform
from PyQt6.QtWidgets import QApplication

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.arrange_commands import apply_layer_z_values
from snapmock.commands.group_commands import GroupItemsCommand, UngroupItemsCommand
from snapmock.commands.move_item_layer import MoveItemToLayerCommand
from snapmock.core.clipboard_manager import ClipboardManager
from snapmock.core.scene import SnapScene
from snapmock.core.selection_manager import SelectionManager
from snapmock.io.project_serializer import ITEM_REGISTRY, load_project, save_project
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.ellipse_item import EllipseItem
from snapmock.items.group_item import GroupItem, transform_from_list, transform_to_list
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow


@pytest.fixture()
def scene(qapp: QApplication) -> SnapScene:
    return SnapScene(width=800, height=600)


def _rect(x: float, y: float, w: float = 100, h: float = 60) -> RectangleItem:
    item = RectangleItem(rect=QRectF(0, 0, w, h))
    item.setPos(x, y)
    return item


def _group_of(*items: SnapGraphicsItem) -> GroupItem:
    """A group at the members' top-left, the members offset to keep their scene positions."""
    union = items[0].sceneBoundingRect()
    for item in items[1:]:
        union = union.united(item.sceneBoundingRect())
    group = GroupItem()
    group.setPos(union.topLeft())
    for index, item in enumerate(items):
        item.setPos(item.pos() - union.topLeft())
        item.setZValue(index)
        group.add_member(item)
    return group


def _add(scene: SnapScene, item: SnapGraphicsItem) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))


# --- the item (step 2) ---


def test_group_is_registered_and_named() -> None:
    assert ITEM_REGISTRY["GroupItem"] is GroupItem
    assert GroupItem().type_name == "Group"


def test_group_members_keep_their_scene_positions_and_stacking() -> None:
    a = _rect(10, 20)
    b = _rect(200, 100)
    group = _group_of(a, b)
    assert group.pos() == QPointF(10, 20) - QPointF(1, 1)  # the stroke's half width
    assert a.sceneBoundingRect().topLeft() == QPointF(9, 19)
    assert b.sceneBoundingRect().topLeft() == QPointF(199, 99)
    assert group.members == [a, b]
    assert group.member_count == 2
    assert group.boundingRect() == group.childrenBoundingRect()
    assert group.sceneBoundingRect() == a.sceneBoundingRect().united(b.sceneBoundingRect())


def test_group_shape_is_the_union_of_the_members_shapes() -> None:
    a = _rect(0, 0)
    b = _rect(300, 300)
    group = _group_of(a, b)
    on_a = group.mapFromScene(QPointF(0, 30))  # a's left stroke
    gap = group.mapFromScene(QPointF(200, 200))
    assert group.shape().contains(on_a)
    assert not group.shape().contains(gap)
    assert group.boundingRect().contains(gap)


def test_group_paints_nothing_and_members_are_carried(scene: SnapScene) -> None:
    from snapmock.core.render_engine import RenderEngine

    a = _rect(10, 10)
    a.fill_color = a.stroke_color  # a filled red square
    group = _group_of(a)
    _add(scene, group)
    image = RenderEngine(scene).render_to_image()
    assert image.pixelColor(50, 30) == a.stroke_color
    group.setPos(group.pos() + QPointF(300, 0))
    image = RenderEngine(scene).render_to_image()
    assert image.pixelColor(50, 30).name() == "#ffffff"
    assert image.pixelColor(350, 30) == a.stroke_color


def test_layer_state_and_lock_reach_the_members(scene: SnapScene) -> None:
    a = _rect(0, 0)
    group = _group_of(a)
    manager = scene.layer_manager
    other = manager.add_layer("Layer 2")
    _add(scene, group)
    assert a.layer_id == group.layer_id
    group.layer_id = other.layer_id
    assert a.layer_id == other.layer_id
    manager.set_opacity(other.layer_id, 0.5)
    assert group.layer_opacity == 0.5
    assert a.layer_opacity == 0.5
    manager.set_visibility(other.layer_id, False)
    assert not a.isVisible()
    group.locked = True
    assert a.locked
    group.locked = False
    assert not a.locked


def test_group_flip_is_a_transform_about_the_centre() -> None:
    a = _rect(0, 0, 100, 50)
    b = _rect(200, 0, 100, 50)
    group = _group_of(a, b)
    centre = group.sceneBoundingRect().center()
    left_before = a.sceneBoundingRect()
    group.flip_horizontal = True
    assert group.flip_horizontal
    assert group.sceneBoundingRect().center() == centre
    # a now sits where b was, mirrored
    assert a.sceneBoundingRect().left() == pytest.approx(199)
    group.flip_horizontal = False
    assert a.sceneBoundingRect() == left_before
    assert group.transform().isIdentity()
    group.setRotation(30)
    group.flip_vertical = True
    group.flip_vertical = False
    assert group.transform().isIdentity()


def test_group_scale_geometry_scales_members_and_their_offsets() -> None:
    a = _rect(0, 0, 100, 50)
    b = _rect(200, 0, 100, 50)
    group = _group_of(a, b)
    width = group.boundingRect().width()
    group.scale_geometry(2.0, 1.0)
    assert b.pos().x() == pytest.approx(400 + 2)  # its offset from the group, doubled
    assert a.rect.width() == 200
    assert group.boundingRect().width() == pytest.approx(width * 2, abs=4)


def test_group_serialize_round_trip_carries_members_and_transform() -> None:
    a = _rect(10, 20)
    b = EllipseItem(rect=QRectF(0, 0, 40, 40))
    b.setPos(300, 300)
    group = _group_of(a, b)
    group.setTransform(QTransform().scale(2, 3))
    group.setRotation(15)
    group.setOpacity(0.5)
    data = group.serialize()
    assert data["type"] == "GroupItem"
    assert [m["type"] for m in data["members"]] == ["RectangleItem", "EllipseItem"]
    restored = GroupItem.deserialize(data)
    assert restored.item_id == group.item_id
    assert restored.pos() == group.pos()
    assert restored.rotation() == 15
    assert restored.opacity() == 0.5
    assert restored.transform() == group.transform()
    members = restored.members
    assert [type(m) for m in members] == [RectangleItem, EllipseItem]
    assert [m.item_id for m in members] == [a.item_id, b.item_id]
    assert members[1].pos() == b.pos()
    assert restored.sceneBoundingRect() == group.sceneBoundingRect()


def test_transform_list_helpers() -> None:
    t = QTransform().rotate(20).scale(1.5, 0.5).shear(0.1, 0)
    assert transform_from_list(transform_to_list(t)) == t
    assert transform_from_list(None).isIdentity()
    assert transform_from_list([1, 2]).isIdentity()
    assert transform_from_list(["x"] * 9).isIdentity()


def test_deserialize_skips_unknown_member_types() -> None:
    data = GroupItem().serialize()
    data["members"] = [{"type": "NoSuchItem"}, _rect(0, 0).serialize(), "junk"]
    restored = GroupItem.deserialize(data)
    assert restored.member_count == 1


def test_group_save_and_load_through_the_project_file(scene: SnapScene, tmp_path: Path) -> None:
    a = _rect(10, 20)
    b = _rect(200, 100)
    group = _group_of(a, b)
    _add(scene, group)
    path = tmp_path / "group.smk"
    save_project(scene, path)
    loaded = load_project(path)
    top_level = loaded.annotation_items()
    assert len(top_level) == 1
    assert len(loaded.all_annotation_items()) == 3
    loaded_group = top_level[0]
    assert isinstance(loaded_group, GroupItem)
    assert loaded_group.member_count == 2
    assert loaded_group.sceneBoundingRect() == group.sceneBoundingRect()
    layer = loaded.layer_manager.layers[0]
    assert layer.item_ids == [group.item_id]
    assert all(m.layer_id == layer.layer_id for m in loaded_group.members)


def test_group_of_groups_round_trips(scene: SnapScene, tmp_path: Path) -> None:
    inner = _group_of(_rect(0, 0), _rect(150, 0))
    outer = _group_of(inner, _rect(0, 200))
    _add(scene, outer)
    assert [type(m) for m in outer.members] == [GroupItem, RectangleItem]
    assert len(outer.descendants()) == 4
    path = tmp_path / "nested.smk"
    save_project(scene, path)
    loaded = load_project(path)
    groups = [i for i in loaded.annotation_items() if isinstance(i, GroupItem)]
    assert len(groups) == 1
    assert len(loaded.all_annotation_items()) == 5  # two groups and three rectangles
    assert isinstance(groups[0].members[0], GroupItem)
    assert groups[0].members[0].member_count == 2
    assert groups[0].sceneBoundingRect() == outer.sceneBoundingRect()


def test_clone_gives_every_item_a_new_id() -> None:
    inner = _group_of(_rect(0, 0), _rect(150, 0))
    outer = _group_of(inner, _rect(0, 200))
    copy = outer.clone()
    assert isinstance(copy, GroupItem)
    old_ids = {outer.item_id} | {i.item_id for i in outer.descendants()}
    new_ids = {copy.item_id} | {i.item_id for i in copy.descendants()}
    assert len(new_ids) == 5
    assert old_ids.isdisjoint(new_ids)
    assert copy.sceneBoundingRect() == outer.sceneBoundingRect()


def test_clipboard_carries_a_group_and_pastes_it_through_the_registry(scene: SnapScene) -> None:
    group = _group_of(_rect(0, 0), _rect(150, 0))
    _add(scene, group)
    clipboard = ClipboardManager(scene)
    clipboard.copy_items([group])
    data = clipboard.paste_items()
    assert len(data) == 1
    assert data[0]["type"] == "GroupItem"
    pasted = ITEM_REGISTRY[data[0]["type"]].deserialize(data[0])
    assert isinstance(pasted, GroupItem)
    assert pasted.member_count == 2


# --- the commands and the rows (step 3) ---


def _two_rects_on_layer(scene: SnapScene) -> tuple[RectangleItem, RectangleItem, RectangleItem]:
    """Three rectangles in z-order a, b, c; the tests group a and c."""
    a, b, c = _rect(0, 0), _rect(50, 50), _rect(300, 300)
    for item in (a, b, c):
        _add(scene, item)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    apply_layer_z_values(scene, layer.layer_id)
    return a, b, c


def test_group_command_builds_the_group_in_the_topmost_members_place(scene: SnapScene) -> None:
    a, b, c = _two_rects_on_layer(scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    manager = SelectionManager(scene)
    before = {i: i.sceneBoundingRect() for i in (a, b, c)}
    command = GroupItemsCommand(scene, [c, a], manager)
    scene.command_stack.push(command)
    group = command.group
    assert group is not None
    assert group.members == [a, c]  # bottom first, the layer's order
    assert group.layer_id == layer.layer_id
    assert layer.item_ids == [b.item_id, group.item_id]
    assert group.zValue() == layer.z_base + 1
    assert scene.annotation_items() == [group, b] or set(scene.annotation_items()) == {group, b}
    for item, rect in before.items():
        assert item.sceneBoundingRect() == rect
    assert group.sceneBoundingRect() == before[a].united(before[c])
    assert manager.items == [group]
    assert command.description == "Group 2 items"


def test_group_command_undo_and_redo_restore_items_and_selection(scene: SnapScene) -> None:
    a, b, c = _two_rects_on_layer(scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    ids_before = list(layer.item_ids)
    z_before = [i.zValue() for i in (a, b, c)]
    manager = SelectionManager(scene)
    command = GroupItemsCommand(scene, [a, c], manager)
    scene.command_stack.push(command)
    scene.command_stack.undo()
    assert layer.item_ids == ids_before
    assert [i.zValue() for i in (a, b, c)] == z_before
    assert all(i.parentItem() is None for i in (a, b, c))
    assert command.group is not None and command.group.scene() is None
    assert a.pos() == QPointF(0, 0) and c.pos() == QPointF(300, 300)
    assert manager.items == [a, c]
    scene.command_stack.redo()
    assert layer.item_ids == [b.item_id, command.group.item_id]
    assert a.parentItem() is command.group
    assert manager.items == [command.group]


def test_ungroup_command_restores_positions_and_properties(scene: SnapScene) -> None:
    a, b, c = _two_rects_on_layer(scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    manager = SelectionManager(scene)
    grouping = GroupItemsCommand(scene, [a, c], manager)
    scene.command_stack.push(grouping)
    group = grouping.group
    assert group is not None
    # The user moved, scaled, and rotated the group as one unit
    group.setPos(group.pos() + QPointF(40, 10))
    group.setTransform(QTransform().scale(2, 2))
    group.setRotation(30)
    shown = {i: (i.sceneBoundingRect(), i.mapToScene(QPointF(3, 4))) for i in (a, c)}
    ids_before = list(layer.item_ids)
    ungroup = UngroupItemsCommand(scene, [group], manager)
    scene.command_stack.push(ungroup)
    assert group.scene() is None
    assert layer.item_ids == [b.item_id, a.item_id, c.item_id]
    for item, (rect, point) in shown.items():
        assert item.parentItem() is None
        assert item.mapToScene(QPointF(3, 4)).x() == pytest.approx(point.x())
        assert item.mapToScene(QPointF(3, 4)).y() == pytest.approx(point.y())
        got = item.sceneBoundingRect()
        for attr in ("left", "top", "width", "height"):
            assert getattr(got, attr)() == pytest.approx(getattr(rect, attr)(), abs=1e-6)
        assert item.rotation() == 0  # the member's own rotation is untouched
    assert a.zValue() == layer.z_base + 1 and c.zValue() == layer.z_base + 2
    assert manager.items == [a, c]
    assert ungroup.description == "Ungroup"
    scene.command_stack.undo()
    assert group.scene() is scene
    assert a.parentItem() is group and c.parentItem() is group
    assert layer.item_ids == ids_before
    assert manager.items == [group]
    scene.command_stack.redo()
    assert layer.item_ids == [b.item_id, a.item_id, c.item_id]
    assert a.parentItem() is None


def test_ungroup_peels_one_level(scene: SnapScene) -> None:
    a, b, c = _two_rects_on_layer(scene)
    manager = SelectionManager(scene)
    inner_cmd = GroupItemsCommand(scene, [a, c], manager)
    scene.command_stack.push(inner_cmd)
    inner = inner_cmd.group
    assert inner is not None
    outer_cmd = GroupItemsCommand(scene, [inner, b], manager)
    scene.command_stack.push(outer_cmd)
    outer = outer_cmd.group
    assert outer is not None
    assert outer.members == [b, inner]
    scene.command_stack.push(UngroupItemsCommand(scene, [outer], manager))
    assert inner.parentItem() is None and inner.scene() is scene
    assert a.parentItem() is inner
    assert set(manager.items) == {b, inner}
    assert set(scene.annotation_items()) == {b, inner}


def test_group_row_checks_its_requirements(
    main_window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    scene = main_window.scene
    layer = scene.layer_manager.active_layer
    assert layer is not None
    a, b = _rect(0, 0), _rect(100, 100)
    _add(scene, a)
    _add(scene, b)
    main_window.selection_manager.select_items([a])
    main_window._arrange_group()  # noqa: SLF001
    assert unmet_messages == [("Group", "Group needs at least two items selected.")]
    unmet_messages.clear()
    other = scene.layer_manager.add_layer("Layer 2")
    scene.command_stack.push(MoveItemToLayerCommand(scene, [b], other.layer_id))
    main_window.selection_manager.select_items([a, b])
    main_window._arrange_group()  # noqa: SLF001
    assert unmet_messages == [("Group", "Group needs the selected items on one layer.")]
    assert all(i.parentItem() is None for i in (a, b))
    unmet_messages.clear()
    main_window._arrange_ungroup()  # noqa: SLF001
    assert unmet_messages == [("Ungroup", "Ungroup needs a group selected.")]


def test_group_and_ungroup_rows_act_through_the_window(main_window: MainWindow) -> None:
    scene = main_window.scene
    a, b = _rect(0, 0), _rect(100, 100)
    _add(scene, a)
    _add(scene, b)
    main_window.selection_manager.select_items([a, b])
    main_window._arrange_group()  # noqa: SLF001
    selected = main_window.selection_manager.items
    assert len(selected) == 1 and isinstance(selected[0], GroupItem)
    assert scene.command_stack.undo_text.endswith("Group 2 items")
    main_window._arrange_ungroup()  # noqa: SLF001
    assert main_window.selection_manager.items == [a, b]
    assert scene.command_stack.undo_text.endswith("Ungroup")
