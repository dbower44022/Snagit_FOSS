"""TextTool — click to place or drag to define a text box, click existing text to edit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPen,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PyQt6.QtWidgets import QGraphicsRectItem, QTextEdit

from snapmock.commands.add_item import AddItemCommand
from snapmock.commands.remove_item import RemoveItemCommand
from snapmock.commands.text_edit_command import TextEditCommand
from snapmock.config.constants import MIN_DRAG_TEXT_BOX
from snapmock.items.callout_item import CalloutItem
from snapmock.items.text_item import TextItem
from snapmock.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from snapmock.core.scene import SnapScene
    from snapmock.core.selection_manager import SelectionManager

# Items that support inline text editing
_TextLike = TextItem | CalloutItem


class _RichTextEditor(QTextEdit):
    """QTextEdit subclass that intercepts formatting shortcuts during editing."""

    editing_finished = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return

        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if key == Qt.Key.Key_Escape:
            self.editing_finished.emit()
            return

        if ctrl and not shift:
            if key == Qt.Key.Key_B:
                self._toggle_bold()
                return
            if key == Qt.Key.Key_I:
                self._toggle_italic()
                return
            if key == Qt.Key.Key_U:
                self._toggle_underline()
                return
            if key == Qt.Key.Key_L:
                self._set_alignment(Qt.AlignmentFlag.AlignLeft)
                return
            if key == Qt.Key.Key_E:
                self._set_alignment(Qt.AlignmentFlag.AlignCenter)
                return
            if key == Qt.Key.Key_R:
                self._set_alignment(Qt.AlignmentFlag.AlignRight)
                return
            if key == Qt.Key.Key_J:
                self._set_alignment(Qt.AlignmentFlag.AlignJustify)
                return

        if ctrl and shift:
            if key == Qt.Key.Key_X:
                self._toggle_strikethrough()
                return
            if key == Qt.Key.Key_Period:
                self._change_font_size(1)
                return
            if key == Qt.Key.Key_Comma:
                self._change_font_size(-1)
                return

        if key == Qt.Key.Key_Tab:
            self.textCursor().insertText("    ")
            return

        # Shift+Enter → soft line break
        if shift and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.textCursor().insertText("\n")
            return

        super().keyPressEvent(event)

    def _toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        cur = self.textCursor().charFormat()
        is_bold = cur.fontWeight() >= QFont.Weight.Bold
        fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
        self.textCursor().mergeCharFormat(fmt)

    def _toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.textCursor().charFormat().fontItalic())
        self.textCursor().mergeCharFormat(fmt)

    def _toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.textCursor().charFormat().fontUnderline())
        self.textCursor().mergeCharFormat(fmt)

    def _toggle_strikethrough(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.textCursor().charFormat().fontStrikeOut())
        self.textCursor().mergeCharFormat(fmt)

    def _set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        self.setAlignment(alignment)

    def _change_font_size(self, delta: int) -> None:
        fmt = QTextCharFormat()
        cur_size = self.textCursor().charFormat().font().pointSize()
        new_size = max(1, cur_size + delta)
        fmt.setFontPointSize(float(new_size))
        self.textCursor().mergeCharFormat(fmt)


class TextTool(BaseTool):
    """Click to place text, drag to define a text box, or click existing text to edit."""

    def __init__(self) -> None:
        super().__init__()
        self._editing_item: _TextLike | None = None
        self._editor: _RichTextEditor | None = None
        self._old_html: str = ""
        # Drag-to-create state
        self._drag_start: QPointF | None = None
        self._drag_preview: QGraphicsRectItem | None = None
        self._is_dragging: bool = False

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
            return (
                "Type to edit | Ctrl+B/I/U: format | Escape to finish | Click elsewhere to finish"
            )
        return "Click to place text | Drag to define text box | Click existing text to edit"

    @property
    def active_editor(self) -> _RichTextEditor | None:
        """The active editor widget, if currently editing. Used by PropertyPanel."""
        return self._editor

    @property
    def editing_item(self) -> _TextLike | None:
        """The item currently being edited, if any."""
        return self._editing_item

    @property
    def is_active_operation(self) -> bool:
        """True when dragging or editing."""
        return self._is_dragging or self._editing_item is not None

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
        self._cleanup_drag()
        self._finish_editing()
        super().deactivate()

    def cancel(self) -> None:
        self._cleanup_drag()
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
            # Start potential drag-to-create
            self._drag_start = scene_pos
            self._is_dragging = False
            # Create a dashed-blue preview rectangle
            preview = QGraphicsRectItem()
            pen = QPen(QColor("#0078d7"), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            preview.setPen(pen)
            preview.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            preview.setRect(QRectF(scene_pos, scene_pos))
            self._scene.addItem(preview)
            self._drag_preview = preview
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        if self._drag_start is None or self._drag_preview is None or self._scene is None:
            return False

        view = self._view
        if view is None:
            return False

        current = view.mapToScene(event.pos())
        rect = QRectF(self._drag_start, current).normalized()
        self._drag_preview.setRect(rect)

        # Set _is_dragging once past threshold
        if not self._is_dragging:
            dx = abs(current.x() - self._drag_start.x())
            dy = abs(current.y() - self._drag_start.y())
            if dx > MIN_DRAG_TEXT_BOX or dy > MIN_DRAG_TEXT_BOX:
                self._is_dragging = True

        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._drag_start is None or self._scene is None:
            return False

        view = self._view
        if view is None:
            self._cleanup_drag()
            return False

        scene_pos = view.mapToScene(event.pos())

        # Remove preview
        self._cleanup_drag_preview()

        if (
            self._is_dragging
            and abs(scene_pos.x() - self._drag_start.x()) >= MIN_DRAG_TEXT_BOX
            and abs(scene_pos.y() - self._drag_start.y()) >= MIN_DRAG_TEXT_BOX
        ):
            # Drag-to-create: fixed-size text box
            rect = QRectF(self._drag_start, scene_pos).normalized()
            item = TextItem(text="", pos_x=rect.x(), pos_y=rect.y())
            item._width = rect.width()
            item._height = rect.height()
            item._auto_size = False
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                self._start_editing(item)
        else:
            # Simple click: place new text item with auto-size
            click_pos = self._drag_start
            item = TextItem(text="Text", pos_x=click_pos.x(), pos_y=click_pos.y())
            layer = self._scene.layer_manager.active_layer
            if layer is not None:
                cmd = AddItemCommand(self._scene, item, layer.layer_id)
                self._scene.command_stack.push(cmd)
                self._start_editing(item)

        # Reset drag state
        self._drag_start = None
        self._is_dragging = False
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

    def _cleanup_drag_preview(self) -> None:
        """Remove the drag preview rect from the scene."""
        if self._drag_preview is not None:
            if self._scene is not None:
                self._scene.removeItem(self._drag_preview)
            self._drag_preview = None

    def _cleanup_drag(self) -> None:
        """Clean up all drag state."""
        self._cleanup_drag_preview()
        self._drag_start = None
        self._is_dragging = False

    def _start_editing(self, item: _TextLike) -> None:
        """Show a rich text editor overlay on the item."""
        view = self._view
        if view is None:
            return
        viewport = view.viewport()
        if viewport is None:
            return

        self._editing_item = item
        self._old_html = item.html()
        item.is_editing = True

        # Hide the item's painted text by making it invisible during editing
        item.setOpacity(0.0)

        # Create the editor as a child of the viewport
        editor = _RichTextEditor(viewport)
        self._editor = editor

        # Share the item's document — edits go directly to the item
        editor.setDocument(item.text_document)

        # Enable document undo for per-keystroke Ctrl+Z during editing
        item.text_document.setUndoRedoEnabled(True)
        item.text_document.clearUndoRedoStacks()

        # Connect contentsChanged for auto-size
        item.text_document.contentsChanged.connect(self._on_document_changed)

        # Style the editor
        editor.setStyleSheet(
            "_RichTextEditor {"
            "  background: rgba(255, 255, 255, 200);"
            "  border: 1px solid #0078d7;"
            "  padding: 0px;"
            "}"
        )

        # Position and size the editor to match the item in viewport coordinates
        self._reposition_editor()

        # Select all text
        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        editor.setTextCursor(cursor)

        editor.editing_finished.connect(self._finish_editing)
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

    def _on_document_changed(self) -> None:
        """Auto-resize the text item when the document content changes."""
        item = self._editing_item
        if item is None:
            return
        if isinstance(item, TextItem) and item.auto_size:
            item.prepareGeometryChange()
            item._height = None
            item.update()
            self._reposition_editor()

    def _finish_editing(self) -> None:
        """Commit the edited text and remove the editor overlay."""
        if self._editor is None or self._editing_item is None:
            return

        item = self._editing_item
        new_html = item.html()

        # Disconnect contentsChanged before detaching editor
        try:
            item.text_document.contentsChanged.disconnect(self._on_document_changed)
        except (TypeError, RuntimeError):
            pass

        # Detach editor from the item's document BEFORE destroying it
        # to prevent Qt from deleting the item's document
        self._editor.setDocument(QTextDocument())

        # Disconnect and remove editor
        try:
            self._editor.editing_finished.disconnect(self._finish_editing)
        except (TypeError, RuntimeError):
            pass
        self._editor.hide()
        self._editor.setParent(None)
        self._editor.deleteLater()
        self._editor = None

        # Disable document undo and clear stacks
        item.text_document.setUndoRedoEnabled(False)
        item.text_document.clearUndoRedoStacks()

        # Restore item visibility and editing state
        item.setOpacity(1.0)
        item.is_editing = False

        if self._scene is not None:
            # If text is empty, remove the item
            if not item.plain_text().strip():
                remove_cmd = RemoveItemCommand(self._scene, item)
                self._scene.command_stack.push(remove_cmd)
            elif new_html != self._old_html:
                # Push undo command for the entire editing session
                # First revert to old state, then let the command's redo() apply new state
                item.set_html(self._old_html)
                edit_cmd = TextEditCommand(item, self._old_html, new_html)
                self._scene.command_stack.push(edit_cmd)

        self._editing_item = None
        self._old_html = ""
