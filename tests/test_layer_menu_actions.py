"""Layer and Image menu behaviour from General UI PRD 3.4 and 3.5."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.items.base_item import SnapGraphicsItem
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow


@pytest.fixture()
def window(qtbot: QtBot) -> MainWindow:
    w = MainWindow()
    qtbot.addWidget(w)
    return w


def _add_rect(
    window: MainWindow, x: float, y: float, w: float = 50, h: float = 40
) -> RectangleItem:
    layer = window.scene.layer_manager.active_layer
    assert layer is not None
    item = RectangleItem(rect=QRectF(0, 0, w, h))
    item.setPos(x, y)
    window.scene.command_stack.push(AddItemCommand(window.scene, item, layer.layer_id))
    return item


def _items_on(window: MainWindow, layer_id: str) -> list[SnapGraphicsItem]:
    return [
        i
        for i in window.scene.items()
        if isinstance(i, SnapGraphicsItem) and i.layer_id == layer_id
    ]


def test_duplicate_layer_copies_items_and_undoes(window: MainWindow) -> None:
    lm = window.scene.layer_manager
    source = lm.active_layer
    assert source is not None
    _add_rect(window, 10, 10)
    _add_rect(window, 100, 100)
    window._layer_duplicate()  # noqa: SLF001
    assert lm.count == 2
    copy = lm.layers[1]
    assert copy.name == f"{source.name} copy"
    assert lm.active_layer is copy
    assert len(_items_on(window, copy.layer_id)) == 2
    assert len(_items_on(window, source.layer_id)) == 2
    window.scene.command_stack.undo()
    assert lm.count == 1
    assert len(_items_on(window, source.layer_id)) == 2
    assert len([i for i in window.scene.items() if isinstance(i, SnapGraphicsItem)]) == 2
    window.scene.command_stack.redo()
    assert lm.count == 2
    window.scene.command_stack.mark_clean()


def test_delete_layer_confirms_and_removes_items(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    lm = window.scene.layer_manager
    lm.add_layer("Layer 2")
    top = lm.layers[1]
    lm.set_active(top.layer_id)
    _add_rect(window, 10, 10)
    asked: list[str] = []

    def _no(*a: object, **k: object) -> QMessageBox.StandardButton:
        asked.append(str(a[2]))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", _no)
    window._layer_delete()  # noqa: SLF001
    assert asked == ['Delete layer "Layer 2" and the 1 item on it?']
    assert lm.count == 2

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._layer_delete()  # noqa: SLF001
    assert lm.count == 1
    assert _items_on(window, top.layer_id) == []
    window.scene.command_stack.undo()
    assert lm.count == 2
    assert len(_items_on(window, top.layer_id)) == 1
    window.scene.command_stack.mark_clean()


def test_delete_empty_layer_does_not_ask(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    lm = window.scene.layer_manager
    lm.add_layer("Layer 2")
    lm.set_active(lm.layers[1].layer_id)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: pytest.fail("should not ask"))
    window._layer_delete()  # noqa: SLF001
    assert lm.count == 1
    window.scene.command_stack.mark_clean()


def test_crop_to_canvas_activates_the_crop_tool(window: MainWindow) -> None:
    window._image_crop_to_canvas()  # noqa: SLF001
    assert window.tool_manager.active_tool_id == "crop"


def test_auto_trim_crops_to_visible_content(window: MainWindow) -> None:
    _add_rect(window, 100, 50, 300, 200)
    window._image_auto_trim()  # noqa: SLF001
    size = window.scene.canvas_size
    assert (size.width(), size.height()) == (pytest.approx(302, abs=2), pytest.approx(202, abs=2))
    window.scene.command_stack.undo()
    assert window.scene.canvas_size.width() == 1920
    window.scene.command_stack.mark_clean()


def test_auto_trim_explains_on_an_empty_canvas(
    window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    window._image_auto_trim()  # noqa: SLF001
    assert unmet_messages == [("Auto-Trim", "Auto-Trim needs visible content on the canvas.")]
    assert window.scene.canvas_size.width() == 1920


# ---- the Background layer is pinned (follow-up decision 2) ----


def test_background_layer_pins_the_bottom_of_the_stack(
    window: MainWindow, unmet_messages: list[tuple[str, str]]
) -> None:
    lm = window.scene.layer_manager
    background = lm.layers[0]
    lm.set_layer_type(background.layer_id, "Background")
    above = lm.add_layer("Above")
    top = lm.add_layer("Top")
    lm.set_active(above.layer_id)
    window._layer_move_down()  # noqa: SLF001
    assert unmet_messages[-1][0] == "Move Layer Down"
    assert "not the Background layer" in unmet_messages[-1][1]
    window._layer_move_to_bottom()  # noqa: SLF001
    assert unmet_messages[-1][0] == "Move Layer to Bottom"
    assert [layer.name for layer in lm.layers] == ["Layer 1", "Above", "Top"]
    # Move to Bottom from higher up lands above the Background layer
    lm.set_active(top.layer_id)
    window._layer_move_to_bottom()  # noqa: SLF001
    assert [layer.name for layer in lm.layers] == ["Layer 1", "Top", "Above"]
    window.scene.command_stack.undo()
    assert [layer.name for layer in lm.layers] == ["Layer 1", "Above", "Top"]
    # The Background layer itself never moves up
    lm.set_active(background.layer_id)
    window._layer_move_up()  # noqa: SLF001
    assert unmet_messages[-1][0] == "Move Layer Up"
    window._layer_move_to_top()  # noqa: SLF001
    assert unmet_messages[-1][0] == "Move Layer to Top"
    assert lm.layers[0] is background
    # New Layer Below on the Background layer lands above it; a duplicate is an Annotation
    window._layer_new_relative(background.layer_id, above=False)  # noqa: SLF001
    assert lm.layers[0] is background and lm.layers[1].name == "Layer 4"
    window._layer_duplicate()  # noqa: SLF001
    assert lm.layers[0] is background and lm.layers[1].layer_type == "Annotation"
    assert lm.layers[1].name == "Layer 1 copy"
    window.scene.command_stack.mark_clean()
