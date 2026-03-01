"""CollapsibleSection — reusable collapsible section widget for panels."""

from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QPushButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """A section with a flat toggle button header and collapsible content area.

    The content area uses a QFormLayout accessible via :meth:`add_row`.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle_btn = QPushButton(f"\u25be {title}")
        self._toggle_btn.setFlat(True)
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

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        prefix = "\u25be" if self._expanded else "\u25b8"
        self._toggle_btn.setText(f"{prefix} {self._title}")

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Override to hide the entire section including the header."""
        super().setVisible(visible)
