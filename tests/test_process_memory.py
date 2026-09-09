"""The process memory readout behind the status bar's memory zone (General UI PRD 9)."""

from __future__ import annotations

import pytest

from snapmock.core import process_memory
from snapmock.core.process_memory import (
    MEGABYTE,
    format_memory,
    memory_role,
    process_memory_bytes,
)


def test_reads_a_positive_resident_set_size() -> None:
    value = process_memory_bytes()
    assert value is not None
    assert value > 0


def test_returns_none_without_psutil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_memory, "psutil", None)
    assert process_memory_bytes() is None


def test_format_is_whole_megabytes_with_thousands_separator() -> None:
    assert format_memory(128 * MEGABYTE) == "128 MB"
    assert format_memory(128 * MEGABYTE + 1) == "128 MB"
    assert format_memory(1124 * MEGABYTE) == "1,124 MB"
    assert format_memory(None) == "—"


def test_role_thresholds_follow_the_prd() -> None:
    assert memory_role(None) == ""
    assert memory_role(500 * MEGABYTE) == ""
    assert memory_role(500 * MEGABYTE + 1) == "warning"
    assert memory_role(1024 * MEGABYTE) == "warning"
    assert memory_role(1024 * MEGABYTE + 1) == "error"
