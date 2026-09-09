"""CollapsibleSection — reusable collapsible section widget for panels."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFormLayout, QPushButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """A section with a flat toggle button header and collapsible content area.

    The content area uses a QFormLayout accessible via :meth:`add_row`.

    Signals
    -------
    toggled(bool)
        Emitted with the new expanded state when the header is clicked.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle_btn = QPushButton(f"\u25be {title}")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setAccessibleName(f"{title} section")
        self._toggle_btn.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; padding: 4px; }"
        )
        self._toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self._toggle_btn)

        self._content = QWidget()
        self._form = QFormLayout(self._content)
        self._form.setContentsMargins(8, 4, 8, 4)
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.addWidget(self._content)

        self._title = title

    @property
    def form_layout(self) -> QFormLayout:
        return self._form

    def add_row(self, label: str, widget: QWidget) -> None:
        """Add a label + widget row to the content form layout."""
        self._form.addRow(label, widget)

    @property
    def title(self) -> str:
        return self._title

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Expand or collapse without emitting :attr:`toggled` (restoring saved state)."""
        self._expanded = expanded
        self._content.setVisible(expanded)
        prefix = "\u25be" if expanded else "\u25b8"
        self._toggle_btn.setText(f"{prefix} {self._title}")

    def _toggle(self) -> None:
        self.set_expanded(not self._expanded)
        self.toggled.emit(self._expanded)

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Override to hide the entire section including the header."""
        super().setVisible(visible)
