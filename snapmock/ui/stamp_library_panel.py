"""Stamp library panel — the popover of PRD Section 3.4, and the custom stamp metadata dialog.

Numbered Steps, Stamps & Emoji PRD Section 3.4: category tabs across the top, a search
field over names and tags, a grid of 48 by 48 thumbnails, and a Custom tab holding the
user's imported stamps with an Import SVG button and a drop target (Section 3.8; kickoff
silence 6: those two are the only import routes). Clicking a stamp chooses it and closes
the panel. The panel is a popup on the colour picker's pattern and is placed beside its
anchor, kept on screen.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from snapmock.core.stamp_library import (
    CUSTOM_CATEGORY,
    StampInfo,
    StampLibrary,
    stamp_library,
)
from snapmock.ui.accessibility import apply_default_names

THUMBNAIL_SIZE = 48
"""The grid's thumbnail side (PRD 3.4)."""
PREVIEW_COLOR = "#CC0000"
"""The primary colour thumbnails are drawn in; the secondary stays white."""
PANEL_WIDTH = 360
GRID_ROWS = 4
EMPTY_CUSTOM_TEXT = "No custom stamps yet. Import an SVG file or drop one here."
NO_RESULTS_TEXT = "No stamps found for “{query}”"
_STAMP_ID_ROLE = Qt.ItemDataRole.UserRole


def stamp_pixmap(
    library: StampLibrary,
    info: StampInfo,
    size: int,
    primary: QColor | None = None,
    secondary: QColor | None = None,
) -> QPixmap:
    """*info*'s stamp rendered into a square *size* pixmap, the aspect kept."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    svg = library.svg_data(info.id)
    renderer = (
        library.renderer(
            svg,
            primary if primary is not None else QColor(PREVIEW_COLOR),
            secondary if secondary is not None else QColor("#FFFFFF"),
            colorizable=info.colorizable,
        )
        if svg
        else library.placeholder_renderer()
    )
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    native = renderer.defaultSize()
    if native.width() > 0 and native.height() > 0:
        scale = min(size / native.width(), size / native.height())
        w, h = native.width() * scale, native.height() * scale
    else:
        w = h = float(size)
    renderer.render(painter, QRectF((size - w) / 2, (size - h) / 2, w, h))
    painter.end()
    return pixmap


class StampMetadataDialog(QDialog):
    """Name, tags, and the colorizable flag of an imported stamp (PRD 3.8)."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Stamp")
        self.setAccessibleName("Import Stamp")
        form = QFormLayout(self)
        self.name_edit = QLineEdit(name)
        form.addRow("Name:", self.name_edit)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Comma-separated search words")
        form.addRow("Tags:", self.tags_edit)
        self.colorizable_check = QCheckBox("Colorizable (uses #FF0000 and #0000FF placeholders)")
        self.colorizable_check.setChecked(True)
        form.addRow("", self.colorizable_check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        apply_default_names(self)

    @property
    def tags(self) -> tuple[str, ...]:
        return tuple(t.strip() for t in self.tags_edit.text().split(",") if t.strip())


class _DropList(QListWidget):
    """The thumbnail grid; on the Custom tab it takes dropped SVG files (PRD 3.8)."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.accepts_files = False

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        mime = event.mimeData()
        if self.accepts_files and mime is not None and mime.hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: object) -> None:  # noqa: N802
        if event is not None and self.accepts_files:
            event.acceptProposedAction()  # type: ignore[attr-defined]

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802
        if event is None:
            return
        mime = event.mimeData()
        if not self.accepts_files or mime is None:
            event.ignore()
            return
        paths = [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]
        svgs = [p for p in paths if p.suffix.lower() == ".svg"]
        if svgs:
            self.files_dropped.emit(svgs)
            event.acceptProposedAction()
        else:
            event.ignore()


class StampLibraryPanel(QWidget):
    """The stamp library popover (PRD 3.4).

    Signals
    -------
    stamp_chosen(str)
        The chosen stamp's id; the panel closes.
    closed()
        The panel hid.
    """

    stamp_chosen = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(
        self,
        library: StampLibrary | None = None,
        parent: QWidget | None = None,
        *,
        popup: bool = True,
    ) -> None:
        flags = Qt.WindowType.Popup if popup else Qt.WindowType.Widget
        super().__init__(parent, flags)
        self._library = library if library is not None else stamp_library()
        self._current_id: str = ""
        self.setAccessibleName("Stamp library")
        self.setFixedWidth(PANEL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search stamps by name or tag")
        self.search_edit.setAccessibleName("Search stamps")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._refresh)
        layout.addWidget(self.search_edit)

        self.tabs = QTabBar()
        self.tabs.setAccessibleName("Stamp categories")
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        for category_id, name in self._library.categories():
            index = self.tabs.addTab(name)
            self.tabs.setTabData(index, category_id)
        self.tabs.currentChanged.connect(self._refresh)
        layout.addWidget(self.tabs)

        self.grid = _DropList()
        self.grid.setAccessibleName("Stamps")
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.grid.setGridSize(QSize(THUMBNAIL_SIZE + 24, THUMBNAIL_SIZE + 28))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setWordWrap(True)
        self.grid.setFixedHeight(GRID_ROWS * (THUMBNAIL_SIZE + 28) + 8)
        self.grid.itemClicked.connect(self._on_item_clicked)
        self.grid.itemActivated.connect(self._on_item_clicked)
        self.grid.files_dropped.connect(self.import_files)
        layout.addWidget(self.grid)

        self.empty_label = QLabel("")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setAccessibleName("Stamp library message")
        layout.addWidget(self.empty_label)

        custom_row = QHBoxLayout()
        self.import_button = QPushButton("Import SVG...")
        self.import_button.setAccessibleName("Import SVG")
        self.import_button.setToolTip("Copy SVG files into your custom stamps")
        self.import_button.clicked.connect(self._on_import_clicked)
        custom_row.addWidget(self.import_button)
        custom_row.addStretch()
        layout.addLayout(custom_row)

        apply_default_names(self)
        self._refresh()

    # --- state ---

    @property
    def library(self) -> StampLibrary:
        return self._library

    @property
    def current_category(self) -> str:
        data = self.tabs.tabData(self.tabs.currentIndex())
        return str(data) if data is not None else ""

    def set_category(self, category_id: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabData(index) == category_id:
                self.tabs.setCurrentIndex(index)
                return

    def set_current(self, stamp_id: str) -> None:
        """Highlight *stamp_id* and open its category (a Change Stamp opens here)."""
        self._current_id = stamp_id
        info = self._library.stamp(stamp_id)
        if info is not None:
            self.set_category(CUSTOM_CATEGORY if info.source == "custom" else info.category)
        self._refresh()

    def visible_ids(self) -> list[str]:
        return [
            str(self.grid.item(i).data(_STAMP_ID_ROLE))  # type: ignore[union-attr]
            for i in range(self.grid.count())
        ]

    # --- the grid ---

    def _refresh(self, *_args: object) -> None:
        query = self.search_edit.text().strip()
        category = self.current_category
        self.grid.accepts_files = category == CUSTOM_CATEGORY and not query
        self.import_button.setVisible(category == CUSTOM_CATEGORY and not query)
        stamps = self._library.search(query) if query else self._library.in_category(category)
        self.grid.clear()
        for info in stamps:
            item = QListWidgetItem(
                QIcon(stamp_pixmap(self._library, info, THUMBNAIL_SIZE)), info.name
            )
            item.setData(_STAMP_ID_ROLE, info.id)
            item.setToolTip(
                f"{info.name} ({', '.join(info.tags[:6])})" if info.tags else info.name
            )
            item.setSizeHint(QSize(THUMBNAIL_SIZE + 24, THUMBNAIL_SIZE + 28))
            self.grid.addItem(item)
            if info.id == self._current_id:
                item.setSelected(True)
                self.grid.setCurrentItem(item)
        if stamps:
            self.empty_label.setVisible(False)
        else:
            self.empty_label.setText(
                NO_RESULTS_TEXT.format(query=query) if query else EMPTY_CUSTOM_TEXT
            )
            self.empty_label.setVisible(True)

    def _on_item_clicked(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        stamp_id = str(item.data(_STAMP_ID_ROLE))
        self._current_id = stamp_id
        self.stamp_chosen.emit(stamp_id)
        self.hide()

    # --- custom stamps (PRD 3.8) ---

    def _on_import_clicked(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import SVG Stamps", "", "SVG files (*.svg);;All files (*)"
        )
        if paths:
            self.import_files([Path(p) for p in paths])

    metadata_dialog: Callable[[str, QWidget | None], StampMetadataDialog] = StampMetadataDialog
    """The dialog class; tests replace it."""

    def import_files(self, paths: list[Path]) -> list[StampInfo]:
        """Import every SVG in *paths*, asking for each one's metadata; the imported stamps."""
        imported: list[StampInfo] = []
        for path in paths:
            dialog = type(self).metadata_dialog(path.stem, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                continue
            try:
                info = self._library.import_svg(
                    path,
                    name=dialog.name_edit.text().strip() or path.stem,
                    tags=dialog.tags,
                    colorizable=dialog.colorizable_check.isChecked(),
                )
            except (OSError, ValueError) as exc:
                QMessageBox.information(self, "Import SVG", f"{path.name} was not imported: {exc}")
                continue
            imported.append(info)
        if imported:
            self.set_category(CUSTOM_CATEGORY)
            self._current_id = imported[-1].id
            self._refresh()
        return imported

    # --- placement ---

    def open_beside(self, anchor: QWidget | None, fallback: QPoint | None = None) -> None:
        """Show below *anchor* (or at *fallback*), kept on the screen; refreshes first."""
        self._refresh()
        self.adjustSize()
        size = self.sizeHint()
        if anchor is not None:
            point = anchor.mapToGlobal(QPoint(0, anchor.height() + 2))
        elif fallback is not None:
            point = QPoint(fallback)
        else:
            point = QPoint(100, 100)
        x, y = point.x(), point.y()
        screen = QApplication.screenAt(point)
        if screen is not None:
            available = screen.availableGeometry()
            if x + size.width() > available.right():
                x = max(available.left(), available.right() - size.width())
            if y + size.height() > available.bottom():
                above = (
                    anchor.mapToGlobal(QPoint(0, 0)).y() - size.height() - 2
                    if anchor is not None
                    else available.bottom() - size.height()
                )
                y = max(available.top(), above)
        self.move(x, y)
        self.show()
        self.search_edit.setFocus()

    def hideEvent(self, event: object) -> None:  # noqa: N802
        super().hideEvent(event)  # type: ignore[arg-type]
        self.closed.emit()
