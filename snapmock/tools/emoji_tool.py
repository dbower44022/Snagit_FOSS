"""EmojiTool — pick an emoji, click to place it, drag to size it (PRD Section 4).

Numbered Steps, Stamps & Emoji PRD Sections 4.2, 4.3, 4.5, and 4.9: the active emoji shows in
the Tool Options Bar as a 28 px preview with its name; a click places it centred on the click
point at the configured size and a drag fits it inside the drag rectangle; with no emoji
chosen a click opens the picker; the skin tone chosen in the picker or the bar is remembered
for the session and applied to every capable emoji placed after it; the cursor carries a
24 px preview (kickoff silence 8). When no colour emoji font is installed the tool explains
through the Section 1.3 message (decision 4, option B).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QAbstractAnimation, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation
from PyQt6.QtGui import QColor, QCursor, QIcon, QMouseEvent, QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QHBoxLayout, QLabel, QToolBar, QToolButton, QWidget

from snapmock.commands.add_item import AddItemCommand
from snapmock.core.emoji_data import (
    DEFAULT_EMOJI_SIZE,
    EMOJI_SIZE_MAX,
    EMOJI_SIZE_MIN,
    SKIN_TONE_SWATCHES,
    EmojiInfo,
    SkinTone,
    emoji_data,
    skin_tone_of,
    strip_skin_tone,
)
from snapmock.items.emoji_item import EmojiItem, resolved_emoji_family
from snapmock.tools import numbered_step_tool as _steps
from snapmock.tools.base_tool import BaseTool
from snapmock.ui.cursors import preview_cursor
from snapmock.ui.emoji_picker import EmojiPicker, emoji_pixmap
from snapmock.ui.unmet_requirements import check_requirements

MIN_DRAG_DISTANCE = 10.0
PREVIEW_SIZE = 28
"""The Tool Options Bar's active emoji preview (PRD 4.5)."""
CURSOR_PREVIEW_SIZE = 24
PLACEMENT_HINT_MS = 2000
POP_IN_MS = 200
POP_IN_OVERSHOOT = 1.1
NO_EMOJI_HINT = "Select an emoji from the picker, then click to place."
NO_FONT_REQUIREMENT = "a colour emoji font installed"


def animate_pop_in(item: EmojiItem, parent: Any = None) -> QVariantAnimation | None:
    """Scale *item* from 0 through 110 percent to 100 over 200 ms with an ease-out (PRD 4.3);
    None when animations are off (kickoff silence 4)."""
    if not _steps.ANIMATIONS_ENABLED:
        item.setScale(1.0)
        return None
    item.setScale(0.01)
    animation = QVariantAnimation(parent)
    animation.setStartValue(0.01)
    animation.setKeyValueAt(0.7, POP_IN_OVERSHOOT)
    animation.setEndValue(1.0)
    animation.setDuration(POP_IN_MS)
    animation.valueChanged.connect(lambda value: item.setScale(max(0.01, float(value))))
    animation.finished.connect(lambda: item.setScale(1.0))
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


class EmojiTool(BaseTool):
    """Click to place the active emoji; drag to size it; the picker chooses it."""

    # PRD 4.5 in order: the preview and name and the skin-tone swatches ("tool"), size,
    # opacity, the flips, shadow. One opacity: a non-vector item (Technical Architecture 4.3).
    options_controls = (
        "tool",
        "emoji_size",
        "opacity_pct",
        "flip_horizontal",
        "flip_vertical",
        "shadow_enabled",
    )

    def __init__(self) -> None:
        super().__init__()
        self._creation_defaults = {
            "emoji_char": "",
            "emoji_size": DEFAULT_EMOJI_SIZE,
            "skin_tone": SkinTone.DEFAULT,
            "opacity_pct": 100.0,
            "flip_horizontal": False,
            "flip_vertical": False,
            "shadow_enabled": False,
        }
        self._picker: EmojiPicker | None = None
        self._picker_callback: Callable[[str], None] | None = None
        self._drag_start: QPointF | None = None
        self._drag_rect: QRectF | None = None
        self._drag_preview: QGraphicsRectItem | None = None
        self._placed_hint: str | None = None
        self._hint_timer: QTimer | None = None
        self._preview_button: QToolButton | None = None
        self._name_label: QLabel | None = None
        self._tone_row: QWidget | None = None
        self._tone_buttons: dict[SkinTone, QToolButton] = {}

    # ------------------------------------------------------------ identity

    @property
    def tool_id(self) -> str:
        return "emoji"

    @property
    def display_name(self) -> str:
        return "Emoji"

    @property
    def active_emoji(self) -> EmojiInfo | None:
        """The data entry of the emoji the next click places, or None (PRD 4.3)."""
        chars = str(self._creation_defaults.get("emoji_char", ""))
        return emoji_data().lookup(chars) if chars else None

    @property
    def active_char(self) -> str:
        """The sequence the next click places: the active emoji with the session's tone."""
        info = self.active_emoji
        if info is None:
            return ""
        return emoji_data().toned(info.char, self.skin_tone) if info.skin_tones else info.char

    @property
    def skin_tone(self) -> SkinTone:
        """The session's skin tone (PRD 4.2), kept in the creation defaults."""
        tone = self._creation_defaults.get("skin_tone", SkinTone.DEFAULT)
        return tone if isinstance(tone, SkinTone) else SkinTone.DEFAULT

    @property
    def cursor(self) -> Qt.CursorShape | QCursor:
        chars = self.active_char
        if not chars:
            return Qt.CursorShape.CrossCursor
        return preview_cursor(f"emoji:{chars}", emoji_pixmap(chars, CURSOR_PREVIEW_SIZE))

    @property
    def status_hint(self) -> str:
        """PRD 4.9."""
        if self._placed_hint is not None:
            return self._placed_hint
        info = self.active_emoji
        if info is None:
            return NO_EMOJI_HINT
        return f"Click to place {info.name}. Drag to set size."

    @property
    def is_active_operation(self) -> bool:
        return self._drag_start is not None

    # ------------------------------------------------------------ the active emoji

    def set_active_emoji(self, chars: str) -> None:
        """Make *chars* the emoji the next click places; a toned pick sets the session tone."""
        info = emoji_data().lookup(chars)
        base = info.char if info is not None else strip_skin_tone(chars)
        self._creation_defaults["emoji_char"] = base
        if info is not None and info.skin_tones:
            tone = skin_tone_of(chars)
            if tone is not SkinTone.DEFAULT or chars != base:
                self._creation_defaults["skin_tone"] = tone
        self._after_default_change()

    def set_skin_tone(self, tone: SkinTone) -> None:
        """The session's tone (PRD 4.2): applied to every capable emoji placed after it."""
        self._creation_defaults["skin_tone"] = SkinTone(tone)
        self._after_default_change()

    def _after_default_change(self) -> None:
        self._refresh_preview()
        self._push_hint()
        self._apply_cursor()
        manager = self._tool_manager()
        if manager is not None:
            manager.tool_defaults_changed.emit(self.tool_id)

    def _apply_cursor(self) -> None:
        view = self._view
        if view is not None:
            apply = getattr(view, "_apply_tool_cursor", None)
            if callable(apply):
                apply()

    def _tool_manager(self) -> Any:
        window = self._window()
        return getattr(window, "tool_manager", None)

    def _window(self) -> Any:
        view = self._view
        return view.window() if view is not None else None

    def on_option_changed(self, key: str, value: object) -> None:
        if key in ("emoji_char", "skin_tone"):
            self._refresh_preview()
            self._push_hint()
            self._apply_cursor()

    # ------------------------------------------------------------ the picker

    @property
    def picker(self) -> EmojiPicker | None:
        return self._picker

    def choose_emoji(
        self,
        anchor: Any = None,
        callback: Callable[[str], None] | None = None,
        current: str = "",
        fallback: Any = None,
    ) -> EmojiPicker:
        """Open the picker beside *anchor*; *callback* takes the chosen sequence (the tool's
        own default when None)."""
        if self._picker is None:
            self._picker = EmojiPicker()
            self._picker.emoji_chosen.connect(self._on_picker_chosen)
            self._picker.skin_tone_chosen.connect(self.set_skin_tone)
        self._picker_callback = callback
        self._picker.set_skin_tone(self.skin_tone)
        self._picker.set_current(current or self.active_char)
        self._picker.open_beside(anchor, fallback)
        return self._picker

    def _on_picker_chosen(self, chars: str) -> None:
        callback = self._picker_callback
        self._picker_callback = None
        if callback is not None:
            callback(chars)
        else:
            self.set_active_emoji(chars)

    # ------------------------------------------------------------ the bar

    def build_options_widgets(self, toolbar: QToolBar) -> None:
        """The 28 px preview (click opens the picker), the name, and the six skin-tone
        swatches, shown for a capable emoji only (PRD 4.5)."""
        self._preview_button = QToolButton()
        self._preview_button.setFixedSize(PREVIEW_SIZE + 6, PREVIEW_SIZE + 6)
        self._preview_button.setIconSize(QSize(PREVIEW_SIZE, PREVIEW_SIZE))
        self._preview_button.setAccessibleName("Active emoji")
        self._preview_button.setToolTip("The active emoji; click to open the picker")
        self._preview_button.clicked.connect(lambda: self.choose_emoji(self._preview_button))
        toolbar.addWidget(self._preview_button)
        self._name_label = QLabel("")
        self._name_label.setMinimumWidth(100)
        self._name_label.setAccessibleName("Emoji name")
        toolbar.addWidget(self._name_label)
        self._tone_row = QWidget()
        row = QHBoxLayout(self._tone_row)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(2)
        self._tone_buttons = {}
        for tone in SkinTone:
            button = QToolButton()
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setFixedSize(18, 18)
            label = tone.value.replace("_", " ").title()
            button.setToolTip(f"Skin tone: {label}")
            button.setAccessibleName(f"Skin tone {label}")
            button.setStyleSheet(
                f"QToolButton {{ background: {SKIN_TONE_SWATCHES[tone]}; border: 1px solid #888;"
                " border-radius: 9px; }"
                " QToolButton:checked { border: 2px solid #1a73e8; }"
            )
            button.clicked.connect(lambda _checked=False, t=tone: self.set_skin_tone(t))
            row.addWidget(button)
            self._tone_buttons[tone] = button
        toolbar.addWidget(self._tone_row)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        info = self.active_emoji
        chars = self.active_char
        try:
            if self._preview_button is not None:
                self._preview_button.setIcon(QIcon(emoji_pixmap(chars, PREVIEW_SIZE)))
                self._preview_button.setText("" if chars else "?")
            if self._name_label is not None:
                self._name_label.setText(info.name if info is not None else "No emoji selected")
            if self._tone_row is not None:
                self._tone_row.setVisible(info is not None and info.skin_tones)
                current = self.skin_tone
                for tone, button in self._tone_buttons.items():
                    button.setChecked(tone is current)
        except RuntimeError:
            self._preview_button = None
            self._name_label = None
            self._tone_row = None
            self._tone_buttons = {}

    # ------------------------------------------------------------ lifecycle

    def deactivate(self) -> None:
        self._cleanup_drag()
        self._clear_placed_hint()
        self._preview_button = None
        self._name_label = None
        self._tone_row = None
        self._tone_buttons = {}
        super().deactivate()

    def cancel(self) -> None:
        self._cleanup_drag()

    # ------------------------------------------------------------ placing

    def _can_place(self) -> bool:
        """The font (decision 4) and the layer (PRD 8.4) through the Section 1.3 message."""
        if self._scene is None:
            return False
        layer = self._scene.layer_manager.active_layer
        if layer is None:
            return False
        return check_requirements(
            self._window(),
            "Emoji",
            [
                (resolved_emoji_family() is not None, NO_FONT_REQUIREMENT),
                (not layer.locked, "an unlocked active layer"),
                (layer.visible, "a visible active layer"),
            ],
        )

    def _emoji_at(self, scene_pos: QPointF) -> EmojiItem | None:
        if self._scene is None:
            return None
        for gitem in self._scene.items(scene_pos):
            if isinstance(gitem, EmojiItem) and gitem.parentItem() is None:
                layer = self._scene.layer_manager.layer_by_id(gitem.layer_id)
                if layer is not None and (layer.locked or not layer.visible):
                    continue
                return gitem
        return None

    def mouse_press(self, event: QMouseEvent) -> bool:
        if self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        view = self._view
        if view is None:
            return False
        scene_pos = view.mapToScene(event.pos())
        existing = self._emoji_at(scene_pos)
        if existing is not None:
            if self._selection_manager is not None:
                self._selection_manager.select(existing)
            return True
        if self.active_emoji is None:
            # No emoji selected: the picker opens (PRD 4.3)
            self.choose_emoji(
                self._preview_button,
                fallback=view.viewport().mapToGlobal(event.pos()),  # type: ignore[union-attr]
            )
            return True
        if not self._can_place():
            return True
        self._drag_start = self._snap_pos(scene_pos)
        self._drag_rect = None
        return True

    def mouse_move(self, event: QMouseEvent) -> bool:
        view = self._view
        if view is None or self._scene is None or self._drag_start is None:
            return False
        current = view.mapToScene(event.pos())
        dx = current.x() - self._drag_start.x()
        dy = current.y() - self._drag_start.y()
        if abs(dx) < MIN_DRAG_DISTANCE and abs(dy) < MIN_DRAG_DISTANCE:
            self._drag_rect = None
            self._cleanup_drag_preview()
            return True
        self._drag_rect = QRectF(self._drag_start, current).normalized()
        if self._drag_preview is None:
            preview = QGraphicsRectItem()
            pen = QPen(QColor("#0078d7"), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            preview.setPen(pen)
            preview.setZValue(1e9)
            self._scene.addItem(preview)
            self._drag_preview = preview
        self._drag_preview.setRect(self._drag_rect)
        return True

    def mouse_release(self, event: QMouseEvent) -> bool:
        if self._scene is None or self._drag_start is None:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        start, rect = self._drag_start, self._drag_rect
        self._cleanup_drag()
        if rect is None:
            self.place(start)
        else:
            self.place(rect.center(), min(rect.width(), rect.height()))
        return True

    def mouse_double_click(self, event: QMouseEvent) -> bool:
        """A double-click on an emoji opens the picker to replace it (PRD 4.6)."""
        view = self._view
        if view is None or self._scene is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        item = self._emoji_at(view.mapToScene(event.pos()))
        if item is None:
            return False
        self._cleanup_drag()
        open_editor = getattr(self._window(), "open_marker_editor", None)
        if callable(open_editor):
            open_editor(item)
        return True

    def place(self, center: QPointF, size: float | None = None) -> EmojiItem | None:
        """Place the active emoji centred on *center* at *size* or the default."""
        scene = self._scene
        info = self.active_emoji
        if scene is None or info is None:
            return None
        layer = scene.layer_manager.active_layer
        if layer is None:
            return None
        item = EmojiItem(self.active_char, emoji_name=info.name)
        d = self._creation_defaults
        item.emoji_size = float(d.get("emoji_size", DEFAULT_EMOJI_SIZE))
        if size is not None:
            item.emoji_size = max(EMOJI_SIZE_MIN, min(EMOJI_SIZE_MAX, size))
        item.opacity_pct = float(d.get("opacity_pct", 100.0))
        item.flip_horizontal = bool(d.get("flip_horizontal", False))
        item.flip_vertical = bool(d.get("flip_vertical", False))
        item.shadow_enabled = bool(d.get("shadow_enabled", False))
        item.setPos(center)
        scene.command_stack.push(AddItemCommand(scene, item, layer.layer_id))
        animate_pop_in(item, scene)
        picker = self._picker
        if picker is not None:
            picker.note_used(item.emoji_char)
        self._show_placed_hint(info.name)
        return item

    # ------------------------------------------------------------ hints

    def _show_placed_hint(self, name: str) -> None:
        self._placed_hint = f"Placed {name}. Click to place another."
        self._push_hint()
        if self._hint_timer is None:
            self._hint_timer = QTimer()
            self._hint_timer.setSingleShot(True)
            self._hint_timer.timeout.connect(self._show_idle_hint)
        self._hint_timer.start(PLACEMENT_HINT_MS)

    def _show_idle_hint(self) -> None:
        self._clear_placed_hint()
        self._push_hint()

    def _clear_placed_hint(self) -> None:
        self._placed_hint = None
        if self._hint_timer is not None and self._hint_timer.isActive():
            self._hint_timer.stop()

    def _push_hint(self) -> None:
        window = self._window()
        show = getattr(window, "show_status_hint", None)
        manager = self._tool_manager()
        active = getattr(manager, "active_tool", None) if manager is not None else None
        if callable(show) and self._scene is not None and active is self:
            show(self.status_hint)

    # ------------------------------------------------------------ drag cleanup

    def _cleanup_drag_preview(self) -> None:
        if self._drag_preview is not None:
            if self._scene is not None and self._drag_preview.scene() is self._scene:
                self._scene.removeItem(self._drag_preview)
            self._drag_preview = None

    def _cleanup_drag(self) -> None:
        self._cleanup_drag_preview()
        self._drag_start = None
        self._drag_rect = None
