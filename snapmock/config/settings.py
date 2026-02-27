"""Persistent application settings backed by QSettings."""

from PyQt6.QtCore import QSettings

from snapmock.config.constants import (
    APP_NAME,
    GRID_SIZE_DEFAULT,
    ORG_NAME,
    ZOOM_DEFAULT,
)


class AppSettings:
    """Thin wrapper around QSettings for typed access to application preferences."""

    def __init__(self) -> None:
        self._qs = QSettings(ORG_NAME, APP_NAME)

    # --- window geometry ---

    def save_window_geometry(self, geometry: bytes) -> None:
        self._qs.setValue("window/geometry", geometry)

    def window_geometry(self) -> bytes | None:
        val = self._qs.value("window/geometry")
        if isinstance(val, bytes):
            return val
        return None

    def save_window_state(self, state: bytes) -> None:
        self._qs.setValue("window/state", state)

    def window_state(self) -> bytes | None:
        val = self._qs.value("window/state")
        if isinstance(val, bytes):
            return val
        return None

    # --- recent files ---

    def recent_files(self) -> list[str]:
        val = self._qs.value("files/recent", [])
        if isinstance(val, list):
            return [str(v) for v in val]
        return []

    def set_recent_files(self, paths: list[str]) -> None:
        self._qs.setValue("files/recent", paths)

    # --- view preferences ---

    def grid_size(self) -> int:
        val = self._qs.value("view/gridSize", GRID_SIZE_DEFAULT)
        return int(val)

    def set_grid_size(self, size: int) -> None:
        self._qs.setValue("view/gridSize", size)

    def grid_visible(self) -> bool:
        return bool(self._qs.value("view/gridVisible", False))

    def set_grid_visible(self, visible: bool) -> None:
        self._qs.setValue("view/gridVisible", visible)

    def zoom_level(self) -> int:
        val = self._qs.value("view/zoomLevel", ZOOM_DEFAULT)
        return int(val)

    def set_zoom_level(self, level: int) -> None:
        self._qs.setValue("view/zoomLevel", level)

    def rulers_visible(self) -> bool:
        return bool(self._qs.value("view/rulersVisible", False))

    def set_rulers_visible(self, visible: bool) -> None:
        self._qs.setValue("view/rulersVisible", visible)

    # --- autosave ---

    def autosave_enabled(self) -> bool:
        return bool(self._qs.value("autosave/enabled", True))

    def set_autosave_enabled(self, enabled: bool) -> None:
        self._qs.setValue("autosave/enabled", enabled)
