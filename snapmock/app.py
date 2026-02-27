"""QApplication bootstrap."""

import sys

from PyQt6.QtWidgets import QApplication

from snapmock.main_window import MainWindow


def main() -> None:
    """Launch the application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
