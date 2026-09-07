"""The capture sound (PRD 4.3). Failure to play is silent by design."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QUrl

log = logging.getLogger("snapmock.capture")

SHUTTER_SOUND = Path(__file__).resolve().parent.parent / "resources" / "sounds" / "shutter.wav"

_effect: Any = None


def play_shutter() -> None:
    """Play the shutter sound once. Never raises."""
    global _effect
    if not SHUTTER_SOUND.is_file():
        return
    try:
        if _effect is None:
            from PyQt6.QtMultimedia import QSoundEffect

            _effect = QSoundEffect()
            _effect.setSource(QUrl.fromLocalFile(str(SHUTTER_SOUND)))
            _effect.setVolume(0.6)
        _effect.play()
    except Exception as e:  # noqa: BLE001 - sound is never a reason to fail a capture
        log.debug("Capture sound unavailable: %s", e)
