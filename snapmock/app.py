"""QApplication bootstrap, the single-instance channel, and command-line capture (PRD 3.5)."""

from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from snapmock.capture.cli import CaptureCommand, parse_capture_args
from snapmock.capture.single_instance import try_forward
from snapmock.main_window import MainWindow

log = logging.getLogger("snapmock")


def main(argv: list[str] | None = None) -> None:
    """Launch the application, or forward a capture request to the running instance."""
    argv = list(sys.argv if argv is None else argv)
    command = parse_capture_args(argv)
    if command is not None and try_forward(argv):
        sys.exit(0)

    app = QApplication(argv)
    window = MainWindow(restore_session=True)
    manager = window.capture_manager
    manager.listen_for_commands()
    manager.register_hotkeys()

    hide_until_done = command is not None and window.capture_manager.settings.capture_hide_window()
    if not hide_until_done:
        window.show()
        window.report_hotkey_failures()
    if command is not None:
        _capture_as_first_action(window, command, show_after=hide_until_done)
    sys.exit(app.exec())


def _capture_as_first_action(
    window: MainWindow, command: CaptureCommand, *, show_after: bool
) -> None:
    """Run ``--capture`` once the event loop starts; show the window when it is over."""
    manager = window.capture_manager

    def finish() -> None:
        if show_after and not window.isVisible():
            window.show()
            window.report_hotkey_failures()
        for signal in (
            manager.capture_completed,
            manager.capture_failed,
            manager.capture_cancelled,
        ):
            try:
                signal.disconnect(finish)
            except TypeError:
                pass

    if show_after:
        manager.capture_completed.connect(finish)
        manager.capture_failed.connect(finish)
        manager.capture_cancelled.connect(finish)

    def start() -> None:
        if not manager.start_from_command(command):
            finish()

    QTimer.singleShot(0, start)
