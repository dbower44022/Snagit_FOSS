"""Layer Panel rows of General UI PRD Section 7 (Phase 6)."""

from __future__ import annotations

from PyQt6.QtCore import QItemSelectionModel, QPoint, QPointF, QRectF, Qt
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


# ---- interactions and action bar (PRD 7.3, 7.4) ----


def test_drop_target_index_mapping() -> None:
    from snapmock.ui.layer_panel import drop_target_index

    # Three rows top-to-bottom: rows 0,1,2 are manager indices 2,1,0.
    assert drop_target_index(drag_row=0, drop_row=2, above=False, count=3) == 0  # to bottom
    assert drop_target_index(drag_row=2, drop_row=0, above=True, count=3) == 2  # to top
    assert drop_target_index(drag_row=0, drop_row=1, above=True, count=3) == 2  # no move
    assert drop_target_index(drag_row=0, drop_row=3, above=True, count=3) == 0  # below all
    assert drop_target_index(drag_row=2, drop_row=1, above=False, count=3) == 0  # no move
    assert drop_target_index(drag_row=2, drop_row=1, above=True, count=3) == 1  # up one


def test_reorder_pushes_command(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    lm = scene.layer_manager
    top = lm.add_layer("Top")
    bottom = lm.layers[0]
    panel.reorder(top.layer_id, 0)
    assert lm.layers[0] is top and lm.layers[1] is bottom
    assert scene.command_stack.undo_text == "Reorder layers"
    scene.command_stack.undo()
    assert lm.layers[0] is bottom
    first = panel.list_widget.item(0)
    assert first is not None and first.text() == "Top"


def test_ctrl_click_batch_lock_and_hide_are_one_command(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    lm = scene.layer_manager
    a = lm.layers[0]
    b = lm.add_layer("B")
    c = lm.add_layer("C")
    lst = panel.list_widget
    lst.setCurrentRow(0)  # C
    item_a = lst.item(panel.row_for_layer(a.layer_id))
    assert item_a is not None
    item_a.setSelected(True)  # the Ctrl+click selection: C and A
    assert panel.selected_layer_ids() == [c.layer_id, a.layer_id]
    assert panel.batch_ids(b.layer_id) == [b.layer_id]
    panel.toggle_lock(c.layer_id)
    assert a.locked and c.locked and not b.locked
    assert scene.command_stack.count == 1
    assert scene.command_stack.undo_text == "Lock 2 layers"
    panel.toggle_visibility(a.layer_id)
    assert not a.visible and not c.visible and b.visible
    assert scene.command_stack.undo_text == "Hide 2 layers"
    scene.command_stack.undo()
    scene.command_stack.undo()
    assert a.visible and c.visible and not a.locked and not c.locked


def test_batch_delete_through_the_window(main_window: MainWindow, unmet_messages: list) -> None:
    lm = main_window.scene.layer_manager
    a = lm.layers[0]
    b = lm.add_layer("B")
    panel = main_window._layer_panel  # noqa: SLF001
    lst = panel.list_widget
    for row in range(lst.count()):
        item = lst.item(row)
        assert item is not None
        item.setSelected(True)
    main_window._layer_delete()  # noqa: SLF001
    assert unmet_messages == [("Delete Layer", "Delete Layer needs at least one layer left.")]
    assert lm.count == 2
    c = lm.add_layer("C")
    item_b = lst.item(panel.row_for_layer(b.layer_id))
    assert item_b is not None
    lst.setCurrentItem(item_b, QItemSelectionModel.SelectionFlag.ClearAndSelect)  # click B
    item_c = lst.item(panel.row_for_layer(c.layer_id))  # then Ctrl+click C
    assert item_c is not None
    item_c.setSelected(True)
    assert panel.selected_layer_ids() == [c.layer_id, b.layer_id]
    main_window._layer_delete()  # noqa: SLF001
    assert [layer.layer_id for layer in lm.layers] == [a.layer_id]
    assert main_window.scene.command_stack.undo_text == "Delete 2 layers"
    main_window.scene.command_stack.undo()
    assert lm.count == 3


def test_action_bar_reuses_menu_actions(main_window: MainWindow, unmet_messages: list) -> None:
    from snapmock.ui.layer_panel import ACTION_BAR_LABELS

    panel = main_window._layer_panel  # noqa: SLF001
    for label in ACTION_BAR_LABELS:
        button = panel.button(label)
        action = button.defaultAction()
        assert action is not None and action.text().replace("&", "") == label
        assert button.accessibleName() == label
        assert not button.icon().isNull()
        assert button.isEnabled()
    lm = main_window.scene.layer_manager
    panel.button("New Layer").click()
    assert lm.count == 2
    main_window._merge_dont_ask = True  # noqa: SLF001
    lm.set_active(lm.layers[-1].layer_id)
    panel.button("Merge Down").click()  # merges Layer 2 into Layer 1 (follow-up step 4)
    assert lm.count == 1 and unmet_messages == []
    assert main_window.scene.command_stack.undo_text == "Merge Down"
    panel.button("New Layer").click()
    lm.set_active(lm.layers[-1].layer_id)  # the empty layer: Delete Layer asks nothing
    panel.button("Delete Layer").click()
    assert lm.count == 1


def test_standalone_panel_buttons_use_commands(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    panel.button("New Layer").click()
    assert scene.layer_manager.count == 2
    assert scene.command_stack.undo_text == 'Add layer "Layer 2"'
    panel.button("Delete Layer").click()
    assert scene.layer_manager.count == 1
    assert scene.command_stack.undo_text == "Remove layer"


def test_hover_highlights_layer_items_unless_preference_off(
    main_window: MainWindow, qtbot: QtBot
) -> None:
    from snapmock.config.settings import AppSettings

    main_window.show()
    lm = main_window.scene.layer_manager
    layer = lm.active_layer
    assert layer is not None
    panel = main_window._layer_panel  # noqa: SLF001
    panel.layer_hovered.emit(layer.layer_id)
    assert main_window.view.highlighted_layer == layer.layer_id
    panel.layer_hovered.emit("")
    assert main_window.view.highlighted_layer is None
    AppSettings().set_layer_hover_highlight(False)
    panel.layer_hovered.emit(layer.layer_id)
    assert main_window.view.highlighted_layer is None
    main_window._apply_preference_changes({"layer_hover_highlight": (False, True)})  # noqa: SLF001
    assert AppSettings().layer_hover_highlight() is True


def test_list_reports_hovered_row(qtbot: QtBot, scene: SnapScene) -> None:
    panel = _panel(qtbot, scene)
    layer = scene.layer_manager.active_layer
    assert layer is not None
    seen: list[str] = []
    panel.layer_hovered.connect(seen.append)
    rects = _row_rect(panel, layer.layer_id)
    viewport = panel.list_widget.viewport()
    assert viewport is not None
    qtbot.mouseMove(viewport, pos=rects.name.center())
    qtbot.mouseMove(viewport, pos=QPoint(rects.name.center().x(), ROW_HEIGHT * 3))
    assert seen == [layer.layer_id, ""]


# ---- blend-mode dropdown and type badges (follow-up step 2, PRD 7.4 and 7.5) ----


def test_blend_mode_dropdown_follows_the_active_layer_and_pushes_a_command(
    qtbot: QtBot, scene: SnapScene
) -> None:
    from snapmock.ui.layer_panel import BLEND_MODE_COMBO_NAME

    panel = _panel(qtbot, scene)
    combo = panel.blend_combo
    assert combo.accessibleName() == BLEND_MODE_COMBO_NAME
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Normal",
        "Multiply",
        "Screen",
        "Overlay",
        "Darken",
        "Lighten",
        "Difference",
    ]
    lm = scene.layer_manager
    first = lm.layers[0]
    second = lm.add_layer("Second")
    lm.set_active(second.layer_id)
    # A pick pushes ChangeLayerPropertyCommand on the active layer
    combo.setCurrentText("Multiply")
    combo.activated.emit(combo.currentIndex())
    assert second.blend_mode == "Multiply" and first.blend_mode == "Normal"
    assert scene.command_stack.undo_text == "Change layer blend_mode"
    # The dropdown follows the active layer
    lm.set_active(first.layer_id)
    assert combo.currentText() == "Normal"
    lm.set_active(second.layer_id)
    assert combo.currentText() == "Multiply"
    scene.command_stack.undo()
    assert second.blend_mode == "Normal" and combo.currentText() == "Normal"
    assert panel.minimumWidth() == MIN_PANEL_WIDTH


def test_rows_carry_the_bg_and_raster_badges(qtbot: QtBot, scene: SnapScene) -> None:
    from snapmock.core.theme_manager import current_theme
    from snapmock.ui.layer_panel import BADGE_SIZE

    panel = _panel(qtbot, scene)
    lm = scene.layer_manager
    background = lm.layers[0]
    raster = lm.add_layer("Regions")
    plain = lm.add_layer("Marks")
    lm.set_layer_type(background.layer_id, "Background")
    lm.set_layer_type(raster.layer_id, "RasterRegion")
    rows = panel.list_widget
    texts = {
        rows.item(r).data(Qt.ItemDataRole.AccessibleTextRole)  # type: ignore[union-attr]
        for r in range(rows.count())
    }
    assert any("background layer" in t for t in texts)
    assert any("raster region layer" in t for t in texts)
    assert not any("layer," in t and "Marks" in t and "region" in t for t in texts)

    image = panel.list_widget.viewport().grab().toImage()  # type: ignore[union-attr]
    accent = current_theme().accent

    def badge_corner(layer_id: str) -> tuple[int, int]:
        rect = _row_rect(panel, layer_id).thumbnail
        return rect.right() - BADGE_SIZE + 2, rect.bottom() - BADGE_SIZE + 2

    x, y = badge_corner(background.layer_id)
    assert image.pixelColor(x, y).name() == accent.name()  # the BG badge's ground
    x, y = badge_corner(plain.layer_id)
    assert image.pixelColor(x, y).name() != accent.name()  # no badge on an Annotation layer
