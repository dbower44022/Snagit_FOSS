"""Tests for ItemPropertiesDialog."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF
from pytestqt.qtbot import QtBot

from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem
from snapmock.items.text_item import TextItem
from snapmock.ui.item_properties_dialog import ItemPropertiesDialog


def _make_scene_and_rect(x: float = 10.0, y: float = 20.0) -> tuple[SnapScene, RectangleItem]:
    scene = SnapScene()
    item = RectangleItem(rect=QRectF(0, 0, 100, 60))
    item.setPos(x, y)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.addItem(item)
    item.layer_id = layer.layer_id
    layer.item_ids.append(item.item_id)
    return scene, item


class TestItemPropertiesDialogGeneral:
    def test_shows_correct_type_name(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg._type_label.text() == "RectangleItem"

    def test_shows_truncated_id(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg._id_label.text() == item.item_id[:12] + "..."

    def test_shows_layer_name(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        layer = scene.layer_manager.active_layer
        assert layer is not None
        assert dlg._layer_label.text() == layer.name


class TestItemPropertiesDialogTransform:
    def test_shows_position_values(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect(x=42.5, y=77.3)
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg._x_spin.value() == pytest.approx(42.5, abs=0.1)
        assert dlg._y_spin.value() == pytest.approx(77.3, abs=0.1)

    def test_shows_rotation(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        item.rotation_deg = 45.0
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg._rotation_spin.value() == pytest.approx(45.0, abs=0.1)

    def test_shows_opacity(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        item.opacity_pct = 50.0
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg._opacity_spin.value() == 50  # noqa: PLR2004


class TestItemPropertiesDialogAppearance:
    def test_appearance_visible_for_vector_item(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert not dlg._appearance_group.isHidden()

    def test_appearance_hidden_for_non_vector_item(self, qtbot: QtBot) -> None:
        scene = SnapScene()
        item = TextItem(text="hello")
        layer = scene.layer_manager.active_layer
        assert layer is not None
        scene.addItem(item)
        item.layer_id = layer.layer_id
        layer.item_ids.append(item.item_id)

        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg._appearance_group.isHidden()


class TestItemPropertiesDialogText:
    def test_text_group_visible_for_text_item(self, qtbot: QtBot) -> None:
        scene = SnapScene()
        item = TextItem(text="hello")
        layer = scene.layer_manager.active_layer
        assert layer is not None
        scene.addItem(item)
        item.layer_id = layer.layer_id
        layer.item_ids.append(item.item_id)

        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert not dlg._text_group.isHidden()

    def test_text_group_hidden_for_rectangle(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg._text_group.isHidden()


class TestItemPropertiesDialogGetChanges:
    def test_returns_empty_when_nothing_changed(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        assert dlg.get_changes() == {}

    def test_detects_position_change(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect(x=10.0, y=20.0)
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        dlg._x_spin.setValue(99.0)
        changes = dlg.get_changes()
        assert "pos_x" in changes
        assert changes["pos_x"][1] == pytest.approx(99.0, abs=0.1)

    def test_detects_locked_toggle(self, qtbot: QtBot) -> None:
        scene, item = _make_scene_and_rect()
        item.locked = False
        dlg = ItemPropertiesDialog(item, scene)
        qtbot.addWidget(dlg)
        dlg._locked_cb.setChecked(True)
        changes = dlg.get_changes()
        assert "locked" in changes
        assert changes["locked"] == (False, True)
