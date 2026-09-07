"""First-run onboarding dialogs (PRD Section 9). Shown on the first capture attempt only."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

CONSENT_TEXT = (
    "Your desktop will ask whether SnapMock may take a screenshot. This is the desktop's "
    "own dialog. Some desktops ask once; some ask every time."
)
HOTKEY_TEXT = (
    "Wayland desktops do not let applications register their own keyboard shortcuts. "
    "To capture with PrintScreen, bind a shortcut in your desktop's keyboard settings to "
    "this command:"
)
COMMANDS = (
    ("Region", "snapmock --capture region"),
    ("Active window", "snapmock --capture window"),
    ("Full screen", "snapmock --capture full"),
)
DESKTOP_NOTES = (
    "GNOME: Settings > Keyboard > View and Customize Shortcuts > Custom Shortcuts.",
    "KDE Plasma: System Settings > Shortcuts > Add Command.",
    "The desktop's own PrintScreen binding must be removed or changed first.",
)
MACOS_NOTE = (
    "macOS: the Shortcuts application, with a keyboard shortcut on a Run Shell Script action."
)


def _copy_to_clipboard(text: str) -> None:
    clipboard = QApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


class DesktopShortcutPanel(QGroupBox):
    """Panel two of the Wayland onboarding: the commands to bind (PRD 9.2)."""

    def __init__(self, parent: QWidget | None = None, *, macos: bool = False) -> None:
        super().__init__("Keyboard shortcut", parent)
        layout = QVBoxLayout(self)
        intro = QLabel(HOTKEY_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.fields: dict[str, QLineEdit] = {}
        for label, command in COMMANDS:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label}:"))
            field = QLineEdit(command)
            field.setReadOnly(True)
            row.addWidget(field, 1)
            copy = QPushButton("Copy")
            copy.clicked.connect(lambda _c=False, t=command: _copy_to_clipboard(t))
            row.addWidget(copy)
            layout.addLayout(row)
            self.fields[command] = field
        notes = (MACOS_NOTE,) if macos else DESKTOP_NOTES
        for note in notes:
            line = QLabel(note)
            line.setWordWrap(True)
            layout.addWidget(line)


class WaylandOnboardingDialog(QDialog):
    """Consent and desktop-shortcut guidance before the first Wayland capture (PRD 9.2).

    ``help_only`` shows the shortcut panel with a Close button, for the
    Preferences link.
    """

    def __init__(self, parent: QWidget | None = None, *, help_only: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Up a Desktop Shortcut" if help_only else "Capturing on Wayland")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        if not help_only:
            consent = QGroupBox("Consent")
            consent_layout = QVBoxLayout(consent)
            text = QLabel(CONSENT_TEXT)
            text.setWordWrap(True)
            consent_layout.addWidget(text)
            layout.addWidget(consent)
        self.shortcut_panel = DesktopShortcutPanel(self)
        layout.addWidget(self.shortcut_panel)
        self.dont_show = QCheckBox("Don't show this again")
        self.dont_show.setVisible(not help_only)
        layout.addWidget(self.dont_show)
        if help_only:
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.reject)
            buttons.accepted.connect(self.accept)
        else:
            buttons = QDialogButtonBox()
            cont = buttons.addButton("Continue", QDialogButtonBox.ButtonRole.AcceptRole)
            buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            if cont is not None:
                cont.setDefault(True)
        layout.addWidget(buttons)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
