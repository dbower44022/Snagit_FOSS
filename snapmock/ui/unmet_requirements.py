"""Never-disabled controls: the shared unmet-requirement message (General UI PRD 1.3).

Controls are never grayed out. When an action's requirements are not met the
action's handler calls :func:`check_requirements`, which shows one message
naming exactly what is missing and returns ``False`` so the handler stops.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QWidget

Requirement = tuple[bool, str]
"""A ``(met, description)`` pair; the description completes "needs …"."""


def unmet_requirements_text(action: str, unmet: list[str]) -> str:
    """The message body for *action* whose *unmet* requirements are listed."""
    if len(unmet) == 1:
        return f"{action} needs {unmet[0]}."
    lines = "\n".join(f"• {u}" for u in unmet)
    return f"{action} needs:\n{lines}"


def show_unmet_requirements(parent: QWidget | None, action: str, unmet: list[str]) -> None:
    """Show the informational message for *action*'s *unmet* requirements."""
    QMessageBox.information(parent, action, unmet_requirements_text(action, unmet))


def check_requirements(
    parent: QWidget | None, action: str, requirements: list[Requirement]
) -> bool:
    """Return True when every requirement is met; otherwise show the message and return False."""
    unmet = [description for met, description in requirements if not met]
    if not unmet:
        return True
    show_unmet_requirements(parent, action, unmet)
    return False


def show_not_available(parent: QWidget | None, action: str, detail: str) -> None:
    """The message for a menu row whose feature is not built yet (a recorded deferral)."""
    QMessageBox.information(parent, action, f"{action} is not available yet. {detail}")
