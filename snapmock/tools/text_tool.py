"""TextTool — click to place a text item, click existing text to edit inline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QPlainTextEdit

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.modify_property import ModifyPropertyCommand
from snapmock.items.callout_item import CalloutItem
from snapmock.items.text_item import TextItem
from snapmock.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager

# Items that support inline text editing
_TextLike = TextItem | CalloutItem


class TextTool(BaseTool):
    """Click on the canvas to place a text item, or click existing text to edit it."""

    def __init__(self) -> None:
        super().__init__()
        self._editing_item: _TextLike | None = None
        self._editor: QPlainTextEdit | None = None
        self._old_text: str = ""

    @property
    def tool_id(self) -> str:
        return "text"

    @property
    def display_name(self) -> str:
        return "Text"

    @property
    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.IBeamCursor

    @property
    def status_hint(self) -> str:
        if self._editing_item is not None:
            return "Type to edit | Escape to finish | Click elsewhere to finish"
        return "Click to place text | Click existing text to edit"

    def activate(self, scene: SnapScene, selection_manager: SelectionManager) -> None:
        super().activate(scene, selection_manager)
        # If activated with a text item already selected (e.g. double-click from select tool),
        # start editing it immediately.
        if self._selection_manager is not None:
            for item in self._selection_manager.items:
                if isinstance(item, (TextItem, CalloutItem)):
                    self._start_editing(item)
                    break

    def deactivate(self) -> None:
        self._finish_editing()
        super().deactivate()

    def cancel(self) -> None:
        self._finish_editing()

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False

        view = self._view
        if view is None:
            return False

        scene_pos = view.mapToScene(event.pos())

        # Check if clicking on an existing text-like item
        clicked_item = self._text_item_at(scene_pos)

        if clicked_item is not None and clicked_item is self._editing_item:
            # Clicking inside the item we're already editing — let the editor handle it
            return False

        # Finish any current editing first
        self._finish_editing()

        if clicked_item is not None:
            # Edit existing text item
            self._start_editing(clicked_item)
        else:
            # Place new text item and start editing it
            item = TextItem(text="Text", pos_x=scene_pos.x(), pos_y=scene_pos.y())
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                self._start_editing(item)
        return True

    def key_press(self, event: QKeyEvent) -> bool:
        if self._editor is not None:
            if event.key() == Qt.Key.Key_Escape:
                self._finish_editing()
                return True
            # Let the editor widget handle all other keys
            return False
        return False

    def _text_item_at(self, scene_pos: QPointF) -> _TextLike | None:
        """Find a TextItem or CalloutItem under the given scene position."""
        if self._scene is None:
            return None
        for gitem in self._scene.items(scene_pos):
            if isinstance(gitem, (TextItem, CalloutItem)):
                layer = self._scene.layer_manager.layer_by_id(gitem.layer_id)
                if layer is not None and (layer.locked or not layer.visible):
                    continue
                return gitem
        return None

    def _start_editing(self, item: _TextLike) -> None:
        """Show a text editor overlay on the item."""
        view = self._view
        if view is None:
            return
        viewport = view.viewport()
        if viewport is None:
            return

        self._editing_item = item
        self._old_text = item.text

        # Hide the item's painted text by making it invisible during editing
        item.setOpacity(0.0)

        # Create the editor as a child of the viewport
        editor = QPlainTextEdit(viewport)
        self._editor = editor

        # Match item font and color
        font = item.font
        color = item.text_color
        editor.setFont(font)
        editor.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  color: {color.name()};"
            f"  background: rgba(255, 255, 255, 200);"
            f"  border: 1px solid #0078d7;"
            f"  padding: 0px;"
            f"}}"
        )

        # Position and size the editor to match the item in viewport coordinates
        self._reposition_editor()

        # Set text and select all
        editor.setPlainText(item.text)
        editor.selectAll()
        editor.show()
        editor.setFocus()

    def _reposition_editor(self) -> None:
        """Position the editor widget over the text item in viewport coordinates."""
        if self._editor is None or self._editing_item is None:
            return
        view = self._view
        if view is None:
            return
        item = self._editing_item

        # Map item bounding rect to viewport coordinates
        scene_rect = item.mapToScene(item.boundingRect())
        view_polygon = view.mapFromScene(scene_rect)
        view_rect = view_polygon.boundingRect()

        # Ensure minimum size for the editor
        min_w = max(int(view_rect.width()), 120)
        min_h = max(int(view_rect.height()) + 10, 40)

        self._editor.setGeometry(
            int(view_rect.x()),
            int(view_rect.y()),
            min_w,
            min_h,
        )

    def _finish_editing(self) -> None:
        """Commit the edited text and remove the editor overlay."""
        if self._editor is None or self._editing_item is None:
            return

        item = self._editing_item
        new_text = self._editor.toPlainText()

        # Remove editor
        self._editor.hide()
        self._editor.setParent(None)
        self._editor.deleteLater()
        self._editor = None

        # Restore item visibility
        item.setOpacity(1.0)

        # Push undo command if text changed
        if new_text != self._old_text and self._scene is not None:
            cmd = ModifyPropertyCommand(item, "text", self._old_text, new_text)
            self._scene.command_stack.push(cmd)

        self._editing_item = None
        self._old_text = ""
