"""DocumentTabs — tab bar plus stacked views for the open documents."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import QMenu, QStackedWidget, QTabBar, QVBoxLayout, QWidget

from snapmock.core.document import Document
from snapmock.core.document_manager import DocumentManager


class _TabBar(QTabBar):
    """QTabBar that closes on middle-click and reports right-clicks."""

    middle_clicked = pyqtSignal(int)
    right_clicked = pyqtSignal(int, QPoint)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.MiddleButton:
            idx = self.tabAt(event.pos())
            if idx >= 0:
                self.middle_clicked.emit(idx)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.RightButton:
            idx = self.tabAt(event.pos())
            if idx >= 0:
                self.right_clicked.emit(idx, event.globalPosition().toPoint())
                event.accept()
                return
        super().mousePressEvent(event)


class DocumentTabs(QWidget):
    """Central widget: a tab bar above a stack of SnapViews.

    The tab bar is hidden while one or zero documents are open.

    Signals
    -------
    close_requested(object)
        The user asked to close a Document.
    close_others_requested(object)
    close_all_requested()
    close_right_requested(object)
    reveal_in_library_requested(object)
    reveal_in_file_manager_requested(object)
    """

    close_requested = pyqtSignal(object)
    close_others_requested = pyqtSignal(object)
    close_all_requested = pyqtSignal()
    close_right_requested = pyqtSignal(object)
    reveal_in_library_requested = pyqtSignal(object)
    reveal_in_file_manager_requested = pyqtSignal(object)

    def __init__(self, documents: DocumentManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._documents = documents
        self._syncing = False
        self._page: QWidget | None = None

        self._tab_bar = _TabBar(self)
        self._tab_bar.setMovable(True)
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.setAccessibleName("Document tabs")
        self._tab_bar.setAccessibleDescription("One tab per open document.")
        self._tab_bar.hide()

        self._stack = QStackedWidget(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tab_bar)
        layout.addWidget(self._stack, 1)

        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabCloseRequested.connect(self._on_close_clicked)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)
        self._tab_bar.middle_clicked.connect(self._on_close_clicked)
        self._tab_bar.right_clicked.connect(self._on_tab_context_menu)

        documents.document_added.connect(self._on_document_added)
        documents.document_removed.connect(self._on_document_removed)
        documents.active_changed.connect(self._on_active_changed)
        documents.document_title_changed.connect(self._on_title_changed)

        for doc in documents.documents:
            self._on_document_added(doc)
        self._on_active_changed(documents.active)

    # --- accessors ---

    @property
    def tab_bar(self) -> QTabBar:
        return self._tab_bar

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    @property
    def current_page(self) -> QWidget | None:
        """The page shown over the document stack, or None while a document shows."""
        return self._page

    def show_page(self, page: QWidget) -> None:
        """Show *page* (the Welcome panel) in place of the active document's view.

        The tab bar hides while a page shows. Activating another document, or
        :meth:`show_documents`, returns to the views.
        """
        if self._page is page:
            self._stack.setCurrentWidget(page)
            return
        if self._page is not None:
            self._stack.removeWidget(self._page)
        self._page = page
        self._stack.addWidget(page)
        self._stack.setCurrentWidget(page)
        self._update_bar_visibility()

    def show_documents(self) -> None:
        """Drop the page and show the active document's view again."""
        if self._page is None:
            return
        page = self._page
        self._page = None
        self._stack.removeWidget(page)
        page.hide()
        doc = self._documents.active
        if doc is not None:
            self._stack.setCurrentWidget(doc.view)
        self._update_bar_visibility()

    # --- manager -> widget ---

    def _on_document_added(self, doc: Document) -> None:
        self._syncing = True
        try:
            self._stack.addWidget(doc.view)
            idx = self._tab_bar.addTab(doc.tab_title)
            self._tab_bar.setTabData(idx, doc.tab_id)
            self._tab_bar.setTabToolTip(idx, str(doc.file_path) if doc.file_path else "Unsaved")
            self._name_close_button(idx, doc)
        finally:
            self._syncing = False
        self._update_bar_visibility()

    def _on_document_removed(self, doc: Document) -> None:
        idx = self._tab_index_for(doc)
        self._syncing = True
        try:
            if idx >= 0:
                self._tab_bar.removeTab(idx)
            self._stack.removeWidget(doc.view)
        finally:
            self._syncing = False
        self._update_bar_visibility()

    def _on_active_changed(self, doc: Document | None) -> None:
        if doc is None:
            return
        idx = self._tab_index_for(doc)
        if self._page is not None:
            self.show_documents()
        self._syncing = True
        try:
            if idx >= 0 and self._tab_bar.currentIndex() != idx:
                self._tab_bar.setCurrentIndex(idx)
            self._stack.setCurrentWidget(doc.view)
        finally:
            self._syncing = False
        self._refresh_tab_fonts()

    def _on_title_changed(self, doc: Document) -> None:
        idx = self._tab_index_for(doc)
        if idx >= 0:
            self._tab_bar.setTabText(idx, doc.tab_title)
            self._tab_bar.setTabToolTip(idx, str(doc.file_path) if doc.file_path else "Unsaved")
            self._name_close_button(idx, doc)

    # --- widget -> manager ---

    def _on_tab_changed(self, index: int) -> None:
        if self._syncing:
            return
        doc = self._doc_for_tab(index)
        if doc is not None:
            self._documents.set_active(doc)

    def _on_close_clicked(self, index: int) -> None:
        doc = self._doc_for_tab(index)
        if doc is not None:
            self.close_requested.emit(doc)

    def _on_tab_moved(self, from_index: int, to_index: int) -> None:
        if self._syncing:
            return
        self._documents.move(from_index, to_index)

    def _on_tab_context_menu(self, index: int, global_pos: QPoint) -> None:
        doc = self._doc_for_tab(index)
        if doc is None:
            return
        menu = QMenu(self)
        close_a = menu.addAction("Close")
        close_others = menu.addAction("Close Others")
        close_all = menu.addAction("Close All")
        close_right = menu.addAction("Close Tabs to the Right")
        menu.addSeparator()
        reveal_lib = menu.addAction("Reveal in Library")
        reveal_fm = menu.addAction("Reveal in File Manager")
        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen is close_a:
            self.close_requested.emit(doc)
        elif chosen is close_others:
            self.close_others_requested.emit(doc)
        elif chosen is close_all:
            self.close_all_requested.emit()
        elif chosen is close_right:
            self.close_right_requested.emit(doc)
        elif chosen is reveal_lib:
            self.reveal_in_library_requested.emit(doc)
        elif chosen is reveal_fm:
            self.reveal_in_file_manager_requested.emit(doc)

    # --- helpers ---

    def _name_close_button(self, index: int, doc: Document) -> None:
        button = self._tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
        if button is not None:
            button.setAccessibleName(f"Close {doc.display_name}")

    def _tab_index_for(self, doc: Document) -> int:
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == doc.tab_id:
                return i
        return -1

    def _doc_for_tab(self, index: int) -> Document | None:
        tab_id = self._tab_bar.tabData(index)
        for doc in self._documents.documents:
            if doc.tab_id == tab_id:
                return doc
        return None

    def _update_bar_visibility(self) -> None:
        self._tab_bar.setVisible(self._page is None and self._tab_bar.count() > 1)

    def _refresh_tab_fonts(self) -> None:
        current = self._tab_bar.currentIndex()
        for i in range(self._tab_bar.count()):
            font = QFont(self._tab_bar.font())
            font.setBold(i == current)
            self._tab_bar.setTabTextColor(i, self._tab_bar.palette().text().color())
        # QTabBar has no per-tab font API; bold is approximated via stylesheet.
        self._tab_bar.setStyleSheet("QTabBar::tab:selected { font-weight: bold; }")
