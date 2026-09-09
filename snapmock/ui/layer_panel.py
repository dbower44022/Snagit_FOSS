"""LayerPanel — dock widget showing the layer stack (General UI PRD Section 7).

Each row is painted by :class:`_LayerRowDelegate`: visibility and lock toggles,
a thumbnail on a checkerboard, the name with inline rename, and the opacity
text that opens a slider popover. Every change goes through a command on the
scene's command stack; the panel never writes to a :class:`Layer` directly.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING

from PyQt6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from snapmock.commands.layer_commands import (
    AddLayerCommand,
    ChangeLayerPropertyCommand,
    RemoveLayerCommand,
    ReorderLayerCommand,
)
from snapmock.commands.macro_command import MacroCommand
from snapmock.config.settings import AppSettings
from snapmock.core.command_stack import BaseCommand
from snapmock.core.render_engine import RenderEngine
from snapmock.core.theme_manager import current_theme, theme_manager
from snapmock.ui.icons import ACTION_ICONS

if TYPE_CHECKING:
    from snapmock.core.layer import Layer
    from snapmock.core.layer_manager import LayerManager
    from snapmock.core.scene import SnapScene

ROW_HEIGHT = 48
"""Layer row height (PRD 7.2)."""
TOGGLE_SIZE = 20
"""Side of the visibility and lock toggles (PRD 7.2)."""
THUMBNAIL_SIZE = 40
"""Side of the thumbnail preview (PRD 7.2)."""
MIN_PANEL_WIDTH = 200
"""Fixed minimum width of the panel (PRD 7.1)."""
LOCKED_ROW_OPACITY = 0.7
"""Whole-row opacity of a locked layer (PRD 7.5)."""
HIDDEN_TOGGLE_OPACITY = 0.4
"""Dimming of the eye glyph while the layer is hidden (PRD 7.2)."""

_MARGIN = 6
_GAP = 4
_OPACITY_TEXT_WIDTH = 44
_CHECKER_CELL = 5

LAYER_ID_ROLE = Qt.ItemDataRole.UserRole

ACTION_BAR_LABELS = ("New Layer", "Delete Layer", "Duplicate Layer", "Merge Down")
"""The bottom action bar's buttons in order (PRD 7.4); the blend-mode dropdown is deferred."""


def _checkerboard(size: int) -> QPixmap:
    theme = current_theme()
    pix = QPixmap(size, size)
    painter = QPainter(pix)
    for y in range(0, size, _CHECKER_CELL):
        for x in range(0, size, _CHECKER_CELL):
            even = ((x // _CHECKER_CELL) + (y // _CHECKER_CELL)) % 2 == 0
            painter.fillRect(
                x,
                y,
                _CHECKER_CELL,
                _CHECKER_CELL,
                theme.checkerboard_a if even else theme.checkerboard_b,
            )
    painter.end()
    return pix


class _RowRects:
    """The hit and paint rectangles of one row, left to right (PRD 7.2)."""

    def __init__(self, rect: QRect) -> None:
        cy = rect.center().y()
        x = rect.left() + _MARGIN
        self.eye = QRect(x, cy - TOGGLE_SIZE // 2, TOGGLE_SIZE, TOGGLE_SIZE)
        x += TOGGLE_SIZE + _GAP
        self.lock = QRect(x, cy - TOGGLE_SIZE // 2, TOGGLE_SIZE, TOGGLE_SIZE)
        x += TOGGLE_SIZE + _GAP + 2
        self.thumbnail = QRect(x, cy - THUMBNAIL_SIZE // 2, THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        x += THUMBNAIL_SIZE + _GAP + 2
        right = rect.right() - _MARGIN
        self.opacity = QRect(
            right - _OPACITY_TEXT_WIDTH, rect.top(), _OPACITY_TEXT_WIDTH, rect.height()
        )
        self.name = QRect(x, rect.top(), max(10, self.opacity.left() - _GAP - x), rect.height())


def drop_target_index(drag_row: int, drop_row: int, above: bool, count: int) -> int:
    """The layer-manager index a dragged row lands on (rows are top-to-bottom).

    *drop_row* is the row under the cursor, or ``count`` for the space below the
    last row; *above* says whether the insertion line is above it.
    """
    visual = drop_row if above else drop_row + 1
    if drag_row < visual:
        visual -= 1  # the dragged row leaves the list before the insert
    visual = max(0, min(visual, count - 1))
    return (count - 1) - visual


class _LayerList(QListWidget):
    """The row list: drag reorder with the accent insertion line, hover reporting."""

    reorder_requested = pyqtSignal(str, int)
    """(layer_id, new manager index) after a row is dropped."""
    hovered_layer_changed = pyqtSignal(str)
    """The layer id under the cursor, or an empty string."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drop_line_y: int | None = None
        self._hovered_id = ""
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(False)

    def _drop_target(self, pos: QPoint) -> tuple[int, bool]:
        index = self.indexAt(pos)
        if not index.isValid():
            return self.count(), True
        rect = self.visualRect(index)
        return index.row(), pos.y() < rect.center().y()

    def dragMoveEvent(self, event: QDragMoveEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        super().dragMoveEvent(event)
        row, above = self._drop_target(event.position().toPoint())
        if row >= self.count():
            last = self.item(self.count() - 1)
            self._drop_line_y = self.visualItemRect(last).bottom() if last is not None else 0
        else:
            item = self.item(row)
            rect = self.visualItemRect(item) if item is not None else QRect()
            self._drop_line_y = rect.top() if above else rect.bottom()
        event.acceptProposedAction()
        viewport = self.viewport()
        if viewport is not None:
            viewport.update()

    def dragLeaveEvent(self, event: QDragLeaveEvent | None) -> None:  # noqa: N802
        self._drop_line_y = None
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802
        """Route the drop to a command instead of letting the model move the row."""
        self._drop_line_y = None
        if event is None:
            return
        current = self.currentItem()
        if current is None:
            event.ignore()
            return
        layer_id = current.data(LAYER_ID_ROLE)
        drop_row, above = self._drop_target(event.position().toPoint())
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        if isinstance(layer_id, str):
            target = drop_target_index(self.row(current), drop_row, above, self.count())
            self.reorder_requested.emit(layer_id, target)

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._drop_line_y is None:
            return
        viewport = self.viewport()
        if viewport is None:
            return
        painter = QPainter(viewport)
        painter.setPen(QPen(current_theme().accent, 2))
        y = self._drop_line_y
        painter.drawLine(0, y, viewport.width(), y)
        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        if event is None:
            return
        index = self.indexAt(event.pos())
        layer_id = index.data(LAYER_ID_ROLE) if index.isValid() else ""
        self._set_hovered(layer_id if isinstance(layer_id, str) else "")

    def leaveEvent(self, event: QEvent | None) -> None:  # noqa: N802
        super().leaveEvent(event)
        self._set_hovered("")

    def _set_hovered(self, layer_id: str) -> None:
        if layer_id != self._hovered_id:
            self._hovered_id = layer_id
            self.hovered_layer_changed.emit(layer_id)


class _LayerRowDelegate(QStyledItemDelegate):
    """Paints a layer row and routes clicks on its toggles to the panel."""

    def __init__(self, panel: LayerPanel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._panel_ref = weakref.ref(panel)

    def _panel(self) -> LayerPanel | None:
        return self._panel_ref()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(MIN_PANEL_WIDTH, ROW_HEIGHT)

    def paint(  # noqa: C901
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        panel = self._panel()
        if painter is None or panel is None:
            return
        layer = panel.layer_for_index(index)
        if layer is None:
            return
        theme = current_theme()
        rect = option.rect
        rects = _RowRects(rect)
        painter.save()

        # Background: accent for the active layer, hover otherwise (PRD 7.3, 13)
        is_active = layer.layer_id == panel.layer_manager.active_layer_id
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if is_active:
            accent = QColor(theme.accent)
            accent.setAlpha(70)
            painter.fillRect(rect, accent)
        elif selected:
            accent = QColor(theme.accent)
            accent.setAlpha(40)
            painter.fillRect(rect, accent)
        elif hovered:
            painter.fillRect(rect, theme.button_hover)

        if layer.locked:
            painter.setOpacity(LOCKED_ROW_OPACITY)

        manager = theme_manager()
        # Visibility toggle
        eye = manager.icon("eye" if layer.visible else "eye-off")
        if not layer.visible:
            painter.save()
            painter.setOpacity(painter.opacity() * HIDDEN_TOGGLE_OPACITY)
        eye.paint(painter, rects.eye)
        if not layer.visible:
            painter.restore()
        # Lock toggle
        manager.icon("lock" if layer.locked else "lock-open").paint(painter, rects.lock)

        # Thumbnail on a checkerboard
        painter.drawPixmap(rects.thumbnail, panel.checkerboard())
        thumb = panel.thumbnail(layer.layer_id)
        if thumb is not None and not thumb.isNull():
            target = QRect(rects.thumbnail)
            target.setSize(thumb.size())
            target.moveCenter(rects.thumbnail.center())
            painter.drawPixmap(target, thumb)
        painter.setPen(theme.border)
        painter.drawRect(rects.thumbnail.adjusted(0, 0, -1, -1))
        if layer.locked:
            overlay = QRect(0, 0, TOGGLE_SIZE, TOGGLE_SIZE)
            overlay.moveCenter(rects.thumbnail.center())
            manager.icon("lock").paint(painter, overlay)

        # Name, elided (PRD 7.2)
        painter.setPen(theme.text_primary)
        metrics = QFontMetrics(option.font)
        text = metrics.elidedText(layer.name, Qt.TextElideMode.ElideRight, rects.name.width())
        painter.drawText(
            rects.name, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text
        )

        # Opacity text
        painter.setPen(theme.text_secondary)
        painter.drawText(
            rects.opacity,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            f"{round(layer.opacity * 100)}%",
        )
        painter.restore()

    def editorEvent(  # noqa: N802
        self,
        event: QEvent | None,
        model: QAbstractItemModel | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        panel = self._panel()
        if panel is None or not isinstance(event, QMouseEvent):
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        layer_id = index.data(LAYER_ID_ROLE)
        if not isinstance(layer_id, str):
            return False
        rects = _RowRects(option.rect)
        pos = event.pos()
        if event.type() == QEvent.Type.MouseButtonPress:
            if rects.eye.contains(pos):
                panel.toggle_visibility(layer_id)
                return True
            if rects.lock.contains(pos):
                panel.toggle_lock(layer_id)
                return True
            if rects.opacity.contains(pos):
                panel.open_opacity_popover(layer_id, rects.opacity)
                return True
        elif event.type() == QEvent.Type.MouseButtonDblClick and (
            rects.eye.contains(pos) or rects.lock.contains(pos) or rects.opacity.contains(pos)
        ):
            return True
        return False

    def createEditor(  # noqa: N802
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget | None:
        editor = QLineEdit(parent)
        editor.setAccessibleName("Layer name")
        editor.setFrame(True)
        return editor

    def updateEditorGeometry(  # noqa: N802
        self, editor: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if editor is None:
            return
        rects = _RowRects(option.rect)
        name = QRect(rects.name)
        name.setHeight(max(22, editor.sizeHint().height()))
        name.moveCenter(QPoint(rects.name.center().x(), option.rect.center().y()))
        editor.setGeometry(name)

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QLineEdit):
            editor.setText(str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
            editor.selectAll()

    def setModelData(  # noqa: N802
        self, editor: QWidget | None, model: QAbstractItemModel | None, index: QModelIndex
    ) -> None:
        panel = self._panel()
        layer_id = index.data(LAYER_ID_ROLE)
        if panel is None or not isinstance(editor, QLineEdit) or not isinstance(layer_id, str):
            return
        panel.rename_layer(layer_id, editor.text())


class _OpacityPopover(QWidget):
    """The slider popover the opacity text opens (PRD 7.2); one undo entry per drag."""

    def __init__(self, panel: LayerPanel, layer_id: str, opacity: float) -> None:
        super().__init__(panel, Qt.WindowType.Popup)
        self._panel_ref = weakref.ref(panel)
        self._layer_id = layer_id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(round(opacity * 100))
        self._slider.setFixedWidth(140)
        self._slider.setAccessibleName("Layer opacity")
        self._label = QLabel(f"{self._slider.value()}%")
        self._label.setFixedWidth(36)
        layout.addWidget(self._slider)
        layout.addWidget(self._label)
        self._slider.valueChanged.connect(self._on_value_changed)

    @property
    def slider(self) -> QSlider:
        return self._slider

    def _on_value_changed(self, value: int) -> None:
        self._label.setText(f"{value}%")
        panel = self._panel_ref()
        if panel is not None:
            panel.set_opacity(self._layer_id, value / 100.0, live=True)


class LayerPanel(QDockWidget):
    """Dockable layer panel: the rows of Section 7.2 over the action bar of 7.4.

    Signals
    -------
    layer_hovered(str)
        The id of the layer row under the cursor, or an empty string (PRD 7.3).
    """

    layer_hovered = pyqtSignal(str)

    def __init__(self, scene: SnapScene, parent: QWidget | None = None) -> None:
        super().__init__("Layers", parent)
        self._scene = scene
        self._layer_manager = scene.layer_manager
        self._settings = AppSettings()
        self._thumbnails: dict[str, QPixmap] = {}
        self._checkerboard: QPixmap | None = None
        self._popover: _OpacityPopover | None = None
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setMinimumWidth(MIN_PANEL_WIDTH)

        container = QWidget()
        layout = QVBoxLayout(container)

        self._list = _LayerList()
        self._list.setAccessibleName("Layers")
        self._list.setMouseTracking(True)
        self._list.setUniformItemSizes(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.reorder_requested.connect(self.reorder)
        self._list.hovered_layer_changed.connect(self.layer_hovered)
        self._list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._delegate = _LayerRowDelegate(self, self._list)
        self._list.setItemDelegate(self._delegate)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list)

        # Bottom action bar (PRD 7.4): the Layer menu's actions, never disabled
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)
        self._buttons: dict[str, QToolButton] = {}
        for label in ACTION_BAR_LABELS:
            button = QToolButton()
            button.setAutoRaise(True)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setIconSize(theme_manager().icon_qsize())
            btn_layout.addWidget(button)
            self._buttons[label] = button
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._fallback_actions: dict[str, QAction] = {}
        self._install_fallback_actions()
        theme_manager().theme_changed.connect(self._on_theme_changed)
        theme_manager().icon_size_changed.connect(self._on_icon_size_changed)

        self.setWidget(container)

        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.timeout.connect(self._refresh_thumbnails)

        self._connect_scene()
        self._refresh_void()
        self._refresh_thumbnails()

    # --- binding ---

    @property
    def layer_manager(self) -> LayerManager:
        return self._layer_manager

    def button(self, label: str) -> QToolButton:
        """An action bar button by its Section 7.4 label."""
        return self._buttons[label]

    def set_actions(self, actions: dict[str, QAction]) -> None:
        """Give the action bar the Layer menu's actions, keyed by :data:`ACTION_BAR_LABELS`."""
        for label, action in actions.items():
            button = self._buttons.get(label)
            if button is not None:
                button.setDefaultAction(action)
        self._apply_icons()

    def _install_fallback_actions(self) -> None:
        """Commands for a panel used without a main window (tests, previews)."""
        new = QAction("New Layer", self)
        new.triggered.connect(self._on_add_layer)
        delete = QAction("Delete Layer", self)
        delete.triggered.connect(self._on_remove_layer)
        self._fallback_actions = {"New Layer": new, "Delete Layer": delete}
        self.set_actions(self._fallback_actions)

    @property
    def list_widget(self) -> QListWidget:
        return self._list

    def _connect_scene(self) -> None:
        lm = self._layer_manager
        lm.layer_added.connect(self._refresh)
        lm.layer_removed.connect(self._refresh_str)
        lm.layers_reordered.connect(self._refresh_void)
        lm.active_layer_changed.connect(self._refresh_str)
        lm.layer_renamed.connect(self._refresh_renamed)
        lm.layer_visibility_changed.connect(self._refresh_flag)
        lm.layer_lock_changed.connect(self._refresh_flag)
        lm.layer_opacity_changed.connect(self._refresh_opacity)
        self._scene.command_stack.stack_changed.connect(self.schedule_thumbnails)

    def _disconnect_scene(self) -> None:
        lm = self._layer_manager
        pairs = (
            (lm.layer_added, self._refresh),
            (lm.layer_removed, self._refresh_str),
            (lm.layers_reordered, self._refresh_void),
            (lm.active_layer_changed, self._refresh_str),
            (lm.layer_renamed, self._refresh_renamed),
            (lm.layer_visibility_changed, self._refresh_flag),
            (lm.layer_lock_changed, self._refresh_flag),
            (lm.layer_opacity_changed, self._refresh_opacity),
            (self._scene.command_stack.stack_changed, self.schedule_thumbnails),
        )
        for signal, slot in pairs:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

    def set_scene(self, scene: SnapScene) -> None:
        """Rebind to another document's scene (tab switch, open, new)."""
        self._disconnect_scene()
        self._scene = scene
        self._layer_manager = scene.layer_manager
        self._thumbnails.clear()
        self._connect_scene()
        self._refresh_void()
        self._refresh_thumbnails()

    # --- refresh ---

    def _refresh(self, _layer: Layer | None = None) -> None:
        self._refresh_void()
        self.schedule_thumbnails()

    def _refresh_str(self, _id: str = "") -> None:
        self._refresh_void()

    def _refresh_renamed(self, _id: str, _name: str) -> None:
        self._refresh_void()

    def _refresh_flag(self, _id: str, _flag: bool) -> None:
        self._refresh_void()

    def _refresh_opacity(self, _id: str, _value: float) -> None:
        self._viewport().update()

    def _refresh_void(self) -> None:
        """Rebuild the rows from the manager, keeping a Ctrl+click multi-selection.

        With one row selected the selection follows the active layer; only a
        selection of two or more rows survives the rebuild.
        """
        multi = set(self.selected_layer_ids()) if len(self._list.selectedItems()) > 1 else set()
        current: QListWidgetItem | None = None
        self._list.blockSignals(True)
        self._list.clear()
        # Display top-to-bottom (reverse of internal bottom-to-top)
        for layer in reversed(self._layer_manager.layers):
            item = QListWidgetItem(layer.name)
            item.setData(LAYER_ID_ROLE, layer.layer_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            states = []
            if not layer.visible:
                states.append("hidden")
            if layer.locked:
                states.append("locked")
            state_text = f", {' and '.join(states)}" if states else ""
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                f"{layer.name}, {round(layer.opacity * 100)}% opacity{state_text}",
            )
            self._list.addItem(item)
            if layer.layer_id == self._layer_manager.active_layer_id:
                current = item
        if current is not None:
            flag = (
                QItemSelectionModel.SelectionFlag.NoUpdate
                if multi
                else QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
            self._list.setCurrentItem(current, flag)
        for row in range(self._list.count()):
            row_item = self._list.item(row)
            if row_item is not None and row_item.data(LAYER_ID_ROLE) in multi:
                row_item.setSelected(True)
        self._list.blockSignals(False)
        self._viewport().update()

    def _viewport(self) -> QWidget:
        viewport = self._list.viewport()
        assert viewport is not None
        return viewport

    def layer_for_index(self, index: QModelIndex) -> Layer | None:
        layer_id = index.data(LAYER_ID_ROLE)
        if isinstance(layer_id, str):
            return self._layer_manager.layer_by_id(layer_id)
        return None

    def row_for_layer(self, layer_id: str) -> int:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is not None and item.data(LAYER_ID_ROLE) == layer_id:
                return row
        return -1

    # --- thumbnails (PRD 7.2; Preferences > Performance thumbnail delay) ---

    def checkerboard(self) -> QPixmap:
        if self._checkerboard is None:
            self._checkerboard = _checkerboard(THUMBNAIL_SIZE)
        return self._checkerboard

    def thumbnail(self, layer_id: str) -> QPixmap | None:
        return self._thumbnails.get(layer_id)

    def schedule_thumbnails(self) -> None:
        """Re-render every thumbnail after the thumbnail update delay."""
        self._thumb_timer.start(self._settings.thumbnail_delay_ms())

    def _refresh_thumbnails(self) -> None:
        canvas = self._scene.canvas_rect
        if canvas.isEmpty():
            return
        scale = THUMBNAIL_SIZE / max(canvas.width(), canvas.height())
        engine = RenderEngine(self._scene)
        self._thumbnails = {
            layer.layer_id: QPixmap.fromImage(
                engine.render_layer_region(layer.layer_id, QRectF(canvas), scale)
            )
            for layer in self._layer_manager.layers
        }
        self._viewport().update()

    # --- row interactions, every one a command (PRD 7.3) ---

    def toggle_visibility(self, layer_id: str) -> None:
        """Hide or show *layer_id*, and every selected layer with it, as one command."""
        self._toggle_flag(layer_id, "visible")

    def toggle_lock(self, layer_id: str) -> None:
        """Lock or unlock *layer_id*, and every selected layer with it, as one command."""
        self._toggle_flag(layer_id, "locked")

    def _toggle_flag(self, layer_id: str, prop: str) -> None:
        layer = self._layer_manager.layer_by_id(layer_id)
        if layer is None:
            return
        new_value = not getattr(layer, prop)
        commands: list[BaseCommand] = []
        for lid in self.batch_ids(layer_id):
            target = self._layer_manager.layer_by_id(lid)
            if target is not None and getattr(target, prop) != new_value:
                commands.append(
                    ChangeLayerPropertyCommand(
                        self._layer_manager, lid, prop, getattr(target, prop), new_value
                    )
                )
        if not commands:
            return
        if len(commands) == 1:
            self._push(commands[0])
        else:
            verb = {
                "visible": "Hide" if not new_value else "Show",
                "locked": "Lock" if new_value else "Unlock",
            }[prop]
            self._push(MacroCommand(commands, f"{verb} {len(commands)} layers"))

    def set_opacity(self, layer_id: str, opacity: float, *, live: bool = False) -> None:
        """Set a layer's opacity; *live* merges slider steps into one undo entry."""
        layer = self._layer_manager.layer_by_id(layer_id)
        if layer is None or abs(layer.opacity - opacity) < 1e-6:
            return
        self._push(
            ChangeLayerPropertyCommand(
                self._layer_manager, layer_id, "opacity", layer.opacity, opacity, mergeable=live
            )
        )

    def rename_layer(self, layer_id: str, name: str) -> None:
        layer = self._layer_manager.layer_by_id(layer_id)
        name = name.strip()
        if layer is None or not name or name == layer.name:
            return
        self._push(
            ChangeLayerPropertyCommand(self._layer_manager, layer_id, "name", layer.name, name)
        )

    def begin_rename(self, layer_id: str) -> None:
        """Open the inline name editor on *layer_id*'s row (double-click, F2)."""
        row = self.row_for_layer(layer_id)
        if row < 0:
            return
        item = self._list.item(row)
        if item is None:
            return
        self._list.setCurrentItem(item)
        self._list.editItem(item)

    def open_opacity_popover(self, layer_id: str, anchor: QRect) -> None:
        layer = self._layer_manager.layer_by_id(layer_id)
        if layer is None:
            return
        popover = _OpacityPopover(self, layer_id, layer.opacity)
        popover.adjustSize()
        global_pos = self._viewport().mapToGlobal(anchor.bottomLeft())
        popover.move(global_pos.x() - popover.width() + anchor.width(), global_pos.y())
        popover.show()
        self._popover = popover

    @property
    def opacity_popover(self) -> _OpacityPopover | None:
        return self._popover

    def _push(self, command: BaseCommand) -> None:
        self._scene.command_stack.push(command)

    # --- list slots ---

    def _on_row_changed(self, row: int) -> None:
        item = self._list.item(row)
        if item is not None:
            layer_id = item.data(LAYER_ID_ROLE)
            if isinstance(layer_id, str):
                self._layer_manager.set_active(layer_id)

    def _on_theme_changed(self, _name: str) -> None:
        self._checkerboard = None
        self._apply_icons()
        self._viewport().update()

    def _on_icon_size_changed(self, _size: int) -> None:
        size = theme_manager().icon_qsize()
        for button in self._buttons.values():
            button.setIconSize(size)

    def _apply_icons(self) -> None:
        manager = theme_manager()
        for label, button in self._buttons.items():
            name = ACTION_ICONS.get(label)
            action = button.defaultAction()
            if name is None:
                continue
            icon = manager.icon(name)
            if action is not None:
                action.setIcon(icon)
            button.setIcon(icon)

    def _on_add_layer(self) -> None:
        self._push(AddLayerCommand(self._layer_manager, f"Layer {self._layer_manager.count + 1}"))

    def _on_remove_layer(self) -> None:
        active = self._layer_manager.active_layer
        if active is not None and self._layer_manager.count > 1:
            self._push(RemoveLayerCommand(self._layer_manager, active.layer_id))

    # --- selection and batches (PRD 7.3, Ctrl+click) ---

    def selected_layer_ids(self) -> list[str]:
        """The Ctrl+click selection, top row first; the active layer alone otherwise."""
        ids = [
            item.data(LAYER_ID_ROLE)
            for item in self._list.selectedItems()
            if isinstance(item.data(LAYER_ID_ROLE), str)
        ]
        ordered = [
            lid
            for lid in (
                self._list.item(r).data(LAYER_ID_ROLE)  # type: ignore[union-attr]
                for r in range(self._list.count())
            )
            if lid in ids
        ]
        if ordered:
            return ordered
        return [self._layer_manager.active_layer_id] if self._layer_manager.active_layer_id else []

    def batch_ids(self, layer_id: str) -> list[str]:
        """*layer_id* alone, or every selected layer when it is part of a multi-selection."""
        selected = self.selected_layer_ids()
        if layer_id in selected and len(selected) > 1:
            return selected
        return [layer_id]

    def reorder(self, layer_id: str, new_index: int) -> None:
        if self._layer_manager.index_of(layer_id) in (-1, new_index):
            return
        self._push(ReorderLayerCommand(self._layer_manager, layer_id, new_index))

    def _on_context_menu(self, pos: object) -> None:
        if not isinstance(pos, QPoint):
            return
        list_item = self._list.itemAt(pos)
        if list_item is None:
            return
        layer_id = list_item.data(LAYER_ID_ROLE)
        if not isinstance(layer_id, str):
            return
        # Activate the right-clicked layer
        self._layer_manager.set_active(layer_id)
        # Find MainWindow ancestor
        from snapmock.main_window import MainWindow

        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, MainWindow):
            parent = parent.parentWidget()
        if parent is None:
            return
        from snapmock.ui.context_menus import build_layer_panel_context_menu

        global_pos = self._list.mapToGlobal(pos)
        menu = build_layer_panel_context_menu(parent, self._layer_manager, layer_id)
        menu.exec(global_pos)

    def preferred_height(self, max_rows: int = 10) -> int:
        """Return the ideal panel height to fit the current layers (capped at *max_rows*)."""
        row_count = max(1, min(self._list.count(), max_rows))
        list_h = row_count * ROW_HEIGHT + 2 * self._list.frameWidth()
        # Account for the action bar (~35px) and layout margins/spacing (~20px)
        return list_h + 55
