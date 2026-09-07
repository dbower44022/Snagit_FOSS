"""DocumentManager — ordered set of open documents and the active one."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from snapmock.core.document import Document


class DocumentManager(QObject):
    """Tracks open documents (tabs) and which one is active.

    Signals
    -------
    document_added(object)
        A Document was appended.
    document_removed(object)
        A Document was removed (already detached; caller disposes it).
    active_changed(object)
        The active Document changed (may be None when the last tab closes).
    document_title_changed(object)
        A Document's title text changed.
    documents_reordered()
        Tab order changed.
    """

    document_added = pyqtSignal(object)
    document_removed = pyqtSignal(object)
    active_changed = pyqtSignal(object)
    document_title_changed = pyqtSignal(object)
    documents_reordered = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._documents: list[Document] = []
        self._active: Document | None = None

    # --- queries ---

    @property
    def documents(self) -> list[Document]:
        return list(self._documents)

    @property
    def count(self) -> int:
        return len(self._documents)

    @property
    def active(self) -> Document | None:
        return self._active

    @property
    def active_index(self) -> int:
        if self._active is None:
            return -1
        return self._documents.index(self._active)

    def index_of(self, doc: Document) -> int:
        try:
            return self._documents.index(doc)
        except ValueError:
            return -1

    def at(self, index: int) -> Document | None:
        if 0 <= index < len(self._documents):
            return self._documents[index]
        return None

    def find_by_path(self, path: Path) -> Document | None:
        target = _norm(path)
        for doc in self._documents:
            if doc.file_path is not None and _norm(doc.file_path) == target:
                return doc
        return None

    # --- mutation ---

    def add(self, doc: Document, *, activate: bool = True) -> None:
        if doc in self._documents:
            if activate:
                self.set_active(doc)
            return
        self._documents.append(doc)
        doc.title_changed.connect(lambda d=doc: self.document_title_changed.emit(d))
        self.document_added.emit(doc)
        if activate or self._active is None:
            self.set_active(doc)

    def remove(self, doc: Document) -> None:
        if doc not in self._documents:
            return
        idx = self._documents.index(doc)
        self._documents.remove(doc)
        self.document_removed.emit(doc)
        if self._active is doc:
            replacement = self.at(min(idx, len(self._documents) - 1))
            self.set_active(replacement)

    def set_active(self, doc: Document | None) -> None:
        if doc is not None and doc not in self._documents:
            return
        if doc is self._active:
            return
        self._active = doc
        self.active_changed.emit(doc)

    def set_active_index(self, index: int) -> None:
        self.set_active(self.at(index))

    def move(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        if not (0 <= from_index < len(self._documents)):
            return
        doc = self._documents.pop(from_index)
        to_index = max(0, min(to_index, len(self._documents)))
        self._documents.insert(to_index, doc)
        self.documents_reordered.emit()

    def activate_next(self) -> None:
        if not self._documents:
            return
        self.set_active_index((self.active_index + 1) % len(self._documents))

    def activate_previous(self) -> None:
        if not self._documents:
            return
        self.set_active_index((self.active_index - 1) % len(self._documents))


def _norm(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)
