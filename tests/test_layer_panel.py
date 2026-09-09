"""Layer Panel rows of General UI PRD Section 7 (Phase 6)."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLineEdit
from pytestqt.qtbot import QtBot

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.render_engine import RenderEngine
from snapmock.core.scene import SnapScene
from snapmock.items.rectangle_item import RectangleItem
from snapmock.main_window import MainWindow
from snapmock.ui.layer_panel import (
    MIN_PANEL_WIDTH,
    ROW_HEIGHT,
    THUMBNAIL_SIZE,
    LayerPanel,
    _RowRects,
)


def _add_rect(scene: SnapScene, x: float = 10, y: float = 10) -> RectangleItem:
    item = RectangleItem(QRectF(0, 0, 50, 40))
    item.setPos(QPointF(x, y))
    item.fill_color = QColor("red")
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
    return item


def _panel(qtbot: QtBot, scene: SnapScene) -> LayerPanel:
    panel = LayerPanel(scene)
    qtbot.addWidget(panel)
    panel.resize(300, 400)
    panel.show()
    return panel


def _row_rect(panel: LayerPanel, layer_id: str) -> _RowRects:
    row = panel.row_for_layer(layer_id)
    item = panel.list_widget.item(row)
    assert item is not None
    return _RowRects(panel.list_widget.visualItemRect(item))


# ---- layer state reaches the items (Technical Architecture PRD 3.9.1) ----


def test_hidden_layer_hides_its_items(scene: SnapScene) -> None:
    item = _add_rect(scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.layer_manager.set_visibility(layer.layer_id, False)
    assert not item.isVisible()
    scene.layer_manager.set_visibility(layer.layer_id, True)
    assert item.isVisible()


def test_layer_opacity_reaches_items_and_render(scene: SnapScene) -> None:
    item = _add_rect(scene, 0, 0)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.layer_manager.set_opacity(layer.layer_id, 0.5)
    assert item.layer_opacity == 0.5
    image = RenderEngine(scene).render_region(QRectF(0, 0, 50, 40))
    assert image.pixelColor(10, 10).alpha() < 200
    assert "layer_opacity" not in item.serialize()


def test_item_added_to_hidden_layer_starts_hidden(scene: SnapScene) -> None:
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.layer_manager.set_visibility(layer.layer_id, False)
    item = _add_rect(scene)
    assert not item.isVisible()


def test_layer_region_render_shows_hidden_layer_and_scales(scene: SnapScene) -> None:
    _add_rect(scene, 0, 0)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    scene.layer_manager.set_visibility(layer.layer_id, False)
    image = RenderEngine(scene).render_layer_region(layer.layer_id, scene.canvas_rect, 0.1)
    assert image.width() == round(scene.canvas_rect.width() * 0.1)
    assert image.pixelColor(2, 2).alpha() > 0
    # The temporary reveal is undone afterwards
    assert all(not i.isVisible() for i in scene.items_on_layer(layer.layer_id))


# ---- rows (PRD 7.1, 7.2, 7.5) ----


def test_panel_geometry_and_rows(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    assert panel.minimumWidth() == MIN_PANEL_WIDTH
    scene.layer_manager.add_layer("Second")
    assert panel.list_widget.count() == 2
    first = panel.list_widget.item(0)
    assert first is not None
    assert first.text() == "Second"  # top of the stack is the first row
    assert panel.list_widget.sizeHintForRow(0) == ROW_HEIGHT
    rects = _row_rect(panel, scene.layer_manager.layers[0].layer_id)
    assert rects.eye.size().width() == 20 and rects.lock.size().height() == 20
    assert rects.thumbnail.width() == THUMBNAIL_SIZE
    assert rects.name.left() > rects.thumbnail.right()
    assert rects.opacity.left() > rects.name.left()


def test_active_row_follows_manager(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    second = scene.layer_manager.add_layer("Second")
    scene.layer_manager.set_active(second.layer_id)
    assert panel.list_widget.currentRow() == 0
    panel.list_widget.setCurrentRow(1)
    assert scene.layer_manager.active_layer_id == scene.layer_manager.layers[0].layer_id


def test_eye_and_lock_clicks_push_commands(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    rects = _row_rect(panel, layer.layer_id)
    viewport = panel.list_widget.viewport()
    assert viewport is not None
    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=rects.eye.center())
    assert not layer.visible
    assert scene.command_stack.undo_text == "Change layer visible"
    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=rects.lock.center())
    assert layer.locked
    assert scene.command_stack.count == 2
    scene.command_stack.undo()
    scene.command_stack.undo()
    assert layer.visible and not layer.locked
    item = panel.list_widget.item(0)
    assert item is not None
    assert item.data(Qt.ItemDataRole.AccessibleTextRole).endswith("100% opacity")


def test_opacity_text_opens_popover_and_merges_into_one_undo(
    qtbot: QtBot, scene: SnapScene
) -> None:
    panel = _panel(qtbot, scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    rects = _row_rect(panel, layer.layer_id)
    viewport = panel.list_widget.viewport()
    assert viewport is not None
    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=rects.opacity.center())
    popover = panel.opacity_popover
    assert popover is not None and popover.isVisible()
    popover.slider.setValue(60)
    popover.slider.setValue(40)
    assert layer.opacity == 0.4
    assert scene.command_stack.count == 1
    scene.command_stack.undo()
    assert layer.opacity == 1.0
    popover.close()


def test_inline_rename_pushes_command(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    panel.begin_rename(layer.layer_id)
    editor = panel.list_widget.findChild(QLineEdit)
    assert editor is not None
    assert editor.accessibleName() == "Layer name"
    editor.setText("Background")
    qtbot.keyClick(editor, Qt.Key.Key_Return)  # the delegate commits on the next event loop turn
    qtbot.waitUntil(lambda: layer.name == "Background", timeout=2000)
    assert scene.command_stack.undo_text == "Change layer name"
    scene.command_stack.undo()
    assert layer.name == "Layer 1"
    first = panel.list_widget.item(0)
    assert first is not None and first.text() == "Layer 1"


def test_thumbnail_renders_layer_items_after_delay(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    before = panel.thumbnail(layer.layer_id)
    assert before is not None and before.width() <= THUMBNAIL_SIZE
    _add_rect(scene, 0, 0)  # a command: the refresh is scheduled, not immediate
    qtbot.waitUntil(
        lambda: (
            panel.thumbnail(layer.layer_id) is not None
            and panel.thumbnail(layer.layer_id).toImage().pixelColor(0, 0).alpha() > 0
        ),  # type: ignore[union-attr]
        timeout=3000,
    )


def test_set_scene_rebinds_and_disconnects(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    other = SnapScene()
    other.layer_manager.add_layer("Other 2")
    panel.set_scene(other)
    assert panel.layer_manager is other.layer_manager
    assert panel.list_widget.count() == 2
    scene.layer_manager.add_layer("Stale")  # the old scene no longer drives the panel
    assert panel.list_widget.count() == 2


def test_rename_layer_action_edits_inline(main_window: MainWindow, qtbot: QtBot) -> None:
    main_window.show()
    main_window._layer_rename()  # noqa: SLF001
    editor = main_window._layer_panel.list_widget.findChild(QLineEdit)  # noqa: SLF001
    assert editor is not None
    editor.setText("Renamed")
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    layer = main_window.scene.layer_manager.active_layer
    assert layer is not None
    qtbot.waitUntil(lambda: layer.name == "Renamed", timeout=2000)


def test_row_rects_fit_minimum_width() -> None:
    from PyQt6.QtCore import QRect

    rects = _RowRects(QRect(QPoint(0, 0), QPoint(MIN_PANEL_WIDTH - 1, ROW_HEIGHT - 1)))
    assert rects.name.width() >= 10
    assert rects.opacity.right() < MIN_PANEL_WIDTH
