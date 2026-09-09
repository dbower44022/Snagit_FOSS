"""Process memory readout for the status bar (General UI PRD Section 9).

Decision 09-08-26 (General UI kickoff decision 2): the resident set size, the
physical memory the operating system currently assigns to this process, is read
through the ``psutil`` package on every platform. The import is guarded so an
installation without ``psutil`` still runs; the status bar then shows no value.
This module is the only place that imports ``psutil``.
"""

from __future__ import annotations

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only where psutil is absent
    psutil = None  # type: ignore[assignment]

MEGABYTE = 1024 * 1024
"""One megabyte as shown in the status bar: 1,048,576 bytes."""

MEMORY_WARNING_BYTES = 500 * MEGABYTE
"""The zone turns the theme's warning colour above this (PRD 9: 500 MB)."""

MEMORY_ERROR_BYTES = 1024 * MEGABYTE
"""The zone turns the theme's error colour above this (PRD 9: 1 GB)."""


def process_memory_bytes() -> int | None:
    """The resident set size of this process in bytes, or None when it cannot be read."""
    if psutil is None:
        return None
    try:
        return int(psutil.Process().memory_info().rss)
    except (psutil.Error, OSError):  # pragma: no cover - platform refusal
        return None


def format_memory(nbytes: int | None) -> str:
    """The zone text: whole megabytes, e.g. ``"128 MB"``; ``"—"`` when unknown.

    The unit stays megabytes above 1 GB (``"1,124 MB"``) so the red threshold of
    the PRD reads against the same scale as the orange one.
    """
    if nbytes is None:
        return "—"
    return f"{nbytes // MEGABYTE:,} MB"


def memory_role(nbytes: int | None) -> str:
    """The QLabel ``role`` property for *nbytes*: ``""``, ``"warning"``, or ``"error"``."""
    if nbytes is None:
        return ""
    if nbytes > MEMORY_ERROR_BYTES:
        return "error"
    if nbytes > MEMORY_WARNING_BYTES:
        return "warning"
    return ""
