"""RTF utilities for Snagit .snagx text fields.

Snagit stores text as base64-encoded RTF in ``RTFEncodedText`` fields.
This module provides lightweight extraction and generation of that RTF
for round-trip fidelity without an external dependency.
"""

from __future__ import annotations

import base64
import re

from PyQt6.QtGui import QColor


def extract_text_from_rtf(base64_rtf: str) -> str:
    """Decode base64 RTF and return the plain-text content."""
    rtf = _decode_base64_rtf(base64_rtf)
    return _strip_rtf(rtf)


def extract_font_from_rtf(
    base64_rtf: str,
) -> tuple[str, int, QColor]:
    """Parse font family, size (pt), and colour from base64 RTF.

    Returns ``(font_family, font_size_pt, color)``.
    Falls back to sensible defaults when fields are missing.
    """
    rtf = _decode_base64_rtf(base64_rtf)

    # Font family – first entry in \\fonttbl
    family = "Sans Serif"
    m = re.search(r"\\fonttbl\{[^}]*\\f0[^}]*\s+([^;}]+);", rtf)
    if m:
        family = m.group(1).strip()

    # Font size – \\fsNN (half-points)
    size_pt = 14
    m = re.search(r"\\fs(\d+)", rtf)
    if m:
        size_pt = int(m.group(1)) // 2

    # Colour – first custom entry in \\colortbl
    color = QColor(0, 0, 0)
    m = re.search(
        r"\\colortbl\s*;\\red(\d+)\\green(\d+)\\blue(\d+);",
        rtf,
    )
    if m:
        color = QColor(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return family, size_pt, color


def text_to_rtf_base64(
    text: str,
    font_family: str = "Sans Serif",
    font_size: int = 14,
    color: QColor | None = None,
) -> str:
    """Generate minimal RTF from plain text + formatting, return base64."""
    if color is None:
        color = QColor(0, 0, 0)

    fs = font_size * 2  # RTF uses half-points

    # Escape RTF special characters in the text payload
    escaped = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    # Convert paragraphs
    escaped = escaped.replace("\n", "\\par\n")

    rtf = (
        "{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033"
        "{\\fonttbl{\\f0\\fswiss\\fprq2\\fcharset0 " + font_family + ";}}\n"
        "{\\colortbl ;\\red" + str(color.red()) + "\\green" + str(color.green())
        + "\\blue" + str(color.blue()) + ";}\n"
        "\\viewkind4\\uc1\\pard\\tx720\\cf1\\f0\\fs" + str(fs) + " "
        + escaped + "\\par\n}\n"
    )
    return base64.b64encode(rtf.encode("ascii", errors="replace")).decode("ascii")


# ---- internal helpers ----


def _decode_base64_rtf(b64: str) -> str:
    """Base64-decode an RTF string, tolerating padding issues."""
    # Add padding if needed
    missing = len(b64) % 4
    if missing:
        b64 += "=" * (4 - missing)
    raw = base64.b64decode(b64)
    return raw.decode("ascii", errors="replace")


def _strip_rtf(rtf: str) -> str:
    """Strip RTF control words and groups, returning plain text."""
    # Remove header groups: {\fonttbl ...}, {\colortbl ...}, etc.
    text = re.sub(r"\{\\fonttbl[^}]*\}", "", rtf)
    text = re.sub(r"\{\\colortbl[^}]*\}", "", text)
    text = re.sub(r"\{\\stylesheet[^}]*\}", "", text)
    text = re.sub(r"\{\\info[^}]*\}", "", text)
    # Remove {\rtf1 ... header control words up to first space after last header control
    text = re.sub(r"\{\\rtf1[^{}]*(?=[\s])", "", text)

    # Replace paragraph markers with newlines
    text = text.replace("\\par", "\n")
    # Remove remaining control words (backslash + word + optional number + space)
    text = re.sub(r"\\[a-z]+\d*\s?", "", text)
    # Remove escaped special chars
    text = text.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    # Remove remaining braces
    text = text.replace("{", "").replace("}", "")
    # Clean up whitespace
    text = text.strip()
    # Collapse multiple trailing newlines
    text = re.sub(r"\n+$", "", text)
    return text
