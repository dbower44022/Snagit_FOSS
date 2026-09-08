"""Persistent application settings backed by QSettings."""

from pathlib import Path

from PyQt6.QtCore import QSettings

from snapmock.config.constants import (
    APP_NAME,
    DEFAULT_LIBRARY_DIRECTORY,
    GRID_SIZE_DEFAULT,
    LIBRARY_PREVIEW_DEFAULT,
    LIBRARY_THUMBNAIL_DEFAULT,
    ORG_NAME,
    ZOOM_DEFAULT,
)

# Global hotkey settings: action -> (settings key, default portable key sequence).
CAPTURE_HOTKEY_KEYS: dict[str, tuple[str, str]] = {
    "capture.region": ("capture/hotkeyRegion", "Print"),
    "capture.window": ("capture/hotkeyWindow", "Alt+Print"),
    "capture.full_screen": ("capture/hotkeyFullScreen", "Ctrl+Print"),
}


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

    def snap_to_grid(self) -> bool:
        return bool(self._qs.value("view/snapToGrid", False))

    def set_snap_to_grid(self, enabled: bool) -> None:
        self._qs.setValue("view/snapToGrid", enabled)

    def status_bar_visible(self) -> bool:
        return _as_bool(self._qs.value("view/statusBarVisible", True))

    def set_status_bar_visible(self, visible: bool) -> None:
        self._qs.setValue("view/statusBarVisible", visible)

    # --- autosave ---

    def autosave_enabled(self) -> bool:
        return bool(self._qs.value("autosave/enabled", True))

    def set_autosave_enabled(self, enabled: bool) -> None:
        self._qs.setValue("autosave/enabled", enabled)

    def autosave_interval_minutes(self) -> int:
        val = self._qs.value("autosave/interval", 2)
        return int(val)

    def set_autosave_interval_minutes(self, minutes: int) -> None:
        self._qs.setValue("autosave/interval", minutes)

    # --- library ---

    def library_directory(self) -> Path:
        val = self._qs.value("library/directory", "")
        if isinstance(val, str) and val:
            return Path(val)
        return DEFAULT_LIBRARY_DIRECTORY

    def set_library_directory(self, path: Path) -> None:
        self._qs.setValue("library/directory", str(path))

    def library_auto_open(self) -> bool:
        return _as_bool(self._qs.value("library/autoOpenCaptures", True))

    def set_library_auto_open(self, enabled: bool) -> None:
        self._qs.setValue("library/autoOpenCaptures", enabled)

    def library_toast_enabled(self) -> bool:
        return _as_bool(self._qs.value("library/toastNotifications", True))

    def set_library_toast_enabled(self, enabled: bool) -> None:
        self._qs.setValue("library/toastNotifications", enabled)

    def library_default_view_mode(self) -> str:
        val = self._qs.value("library/defaultViewMode", "grid")
        return "list" if str(val) == "list" else "grid"

    def set_library_default_view_mode(self, mode: str) -> None:
        self._qs.setValue("library/defaultViewMode", mode)

    def library_default_thumbnail_size(self) -> int:
        return int(self._qs.value("library/defaultThumbnailSize", LIBRARY_THUMBNAIL_DEFAULT))

    def set_library_default_thumbnail_size(self, size: int) -> None:
        self._qs.setValue("library/defaultThumbnailSize", size)

    def library_default_sort(self) -> str:
        return str(self._qs.value("library/defaultSort", "date_modified_desc"))

    def set_library_default_sort(self, sort_id: str) -> None:
        self._qs.setValue("library/defaultSort", sort_id)

    # panel state (current session values, restored on launch)

    def library_view_mode(self) -> str:
        val = self._qs.value("library/viewMode", self.library_default_view_mode())
        return "list" if str(val) == "list" else "grid"

    def set_library_view_mode(self, mode: str) -> None:
        self._qs.setValue("library/viewMode", mode)

    def library_thumbnail_size(self) -> int:
        return int(self._qs.value("library/thumbnailSize", self.library_default_thumbnail_size()))

    def set_library_thumbnail_size(self, size: int) -> None:
        self._qs.setValue("library/thumbnailSize", size)

    def library_preview_size(self) -> int:
        return int(self._qs.value("library/previewSize", LIBRARY_PREVIEW_DEFAULT))

    def set_library_preview_size(self, size: int) -> None:
        self._qs.setValue("library/previewSize", size)

    def library_sort(self) -> str:
        return str(self._qs.value("library/sort", self.library_default_sort()))

    def set_library_sort(self, sort_id: str) -> None:
        self._qs.setValue("library/sort", sort_id)

    # --- capture (Screen Capture PRD 8.1, 12.2) ---

    def capture_default_mode(self) -> str:
        return str(self._qs.value("capture/defaultMode", "region"))

    def set_capture_default_mode(self, mode: str) -> None:
        self._qs.setValue("capture/defaultMode", mode)

    def capture_hotkey(self, action: str) -> str:
        """Portable-text key sequence for ``capture.region`` / ``.window`` / ``.full_screen``."""
        key, default = CAPTURE_HOTKEY_KEYS[action]
        return str(self._qs.value(key, default))

    def set_capture_hotkey(self, action: str, key_sequence: str) -> None:
        key, _default = CAPTURE_HOTKEY_KEYS[action]
        self._qs.setValue(key, key_sequence)

    def capture_delay_seconds(self) -> int:
        return max(0, min(60, int(self._qs.value("capture/delaySeconds", 0))))

    def set_capture_delay_seconds(self, seconds: int) -> None:
        self._qs.setValue("capture/delaySeconds", max(0, min(60, seconds)))

    def capture_include_cursor(self) -> bool:
        return _as_bool(self._qs.value("capture/includeCursor", False))

    def set_capture_include_cursor(self, enabled: bool) -> None:
        self._qs.setValue("capture/includeCursor", enabled)

    def capture_play_sound(self) -> bool:
        return _as_bool(self._qs.value("capture/playSound", False))

    def set_capture_play_sound(self, enabled: bool) -> None:
        self._qs.setValue("capture/playSound", enabled)

    def capture_hide_window(self) -> bool:
        return _as_bool(self._qs.value("capture/hideWindow", True))

    def set_capture_hide_window(self, enabled: bool) -> None:
        self._qs.setValue("capture/hideWindow", enabled)

    def capture_copy_to_clipboard(self) -> bool:
        return _as_bool(self._qs.value("capture/copyToClipboard", False))

    def set_capture_copy_to_clipboard(self, enabled: bool) -> None:
        self._qs.setValue("capture/copyToClipboard", enabled)

    def capture_full_screen_scope(self) -> str:
        val = str(self._qs.value("capture/fullScreenScope", "monitor_under_cursor"))
        return "all_monitors" if val == "all_monitors" else "monitor_under_cursor"

    def set_capture_full_screen_scope(self, scope: str) -> None:
        self._qs.setValue("capture/fullScreenScope", scope)

    def capture_show_magnifier(self) -> bool:
        return _as_bool(self._qs.value("capture/showMagnifier", True))

    def set_capture_show_magnifier(self, enabled: bool) -> None:
        self._qs.setValue("capture/showMagnifier", enabled)

    def capture_tray_enabled(self) -> bool:
        return _as_bool(self._qs.value("capture/trayEnabled", True))

    def set_capture_tray_enabled(self, enabled: bool) -> None:
        self._qs.setValue("capture/trayEnabled", enabled)

    def capture_keep_running_in_tray(self) -> bool:
        return _as_bool(self._qs.value("capture/keepRunningInTray", False))

    def set_capture_keep_running_in_tray(self, enabled: bool) -> None:
        self._qs.setValue("capture/keepRunningInTray", enabled)

    def capture_onboarding_shown(self) -> bool:
        return _as_bool(self._qs.value("capture/onboardingShown", False))

    def set_capture_onboarding_shown(self, shown: bool) -> None:
        self._qs.setValue("capture/onboardingShown", shown)

    def capture_last_mode(self) -> str:
        return str(self._qs.value("capture/lastMode", self.capture_default_mode()))

    def set_capture_last_mode(self, mode: str) -> None:
        self._qs.setValue("capture/lastMode", mode)

    # --- session (open tabs) ---

    def session_open_files(self) -> list[str]:
        val = self._qs.value("session/openFiles", [])
        if isinstance(val, list):
            return [str(v) for v in val]
        if isinstance(val, str) and val:
            return [val]
        return []

    def set_session_open_files(self, paths: list[str]) -> None:
        self._qs.setValue("session/openFiles", paths)

    def session_active_index(self) -> int:
        return int(self._qs.value("session/activeIndex", 0))

    def set_session_active_index(self, index: int) -> None:
        self._qs.setValue("session/activeIndex", index)


def _as_bool(val: object) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val)
