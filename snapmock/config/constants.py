"""Application-wide constants."""

from enum import Enum
from pathlib import Path

APP_NAME = "SnapMock"
APP_VERSION = "0.1.0"
# Set by the release process; the About dialog shows it beside the version (PRD 11.6).
APP_BUILD_DATE = "2026-09-08"
APP_LICENSE = "MIT License"
COPYRIGHT = "Copyright (c) 2026 Doug Bower"
ORG_NAME = "SnapMock"
ORG_DOMAIN = "snapmock.org"
REPOSITORY_URL = "https://github.com/dbower44022/Snagit_FOSS"
DOCUMENTATION_URL = f"{REPOSITORY_URL}#readme"
ISSUES_URL = f"{REPOSITORY_URL}/issues"

# Main window (General UI PRD 2.2, 15.1)
MIN_WINDOW_WIDTH = 1024
MIN_WINDOW_HEIGHT = 600
DEFAULT_PANEL_WIDTH = 300

# Canvas defaults
DEFAULT_CANVAS_WIDTH = 1920
DEFAULT_CANVAS_HEIGHT = 1080

# Zoom bounds (percentage)
ZOOM_MIN = 10
ZOOM_MAX = 3200
ZOOM_DEFAULT = 100
ZOOM_PIXEL_GRID_THRESHOLD = 800

# Layer z-value allocation: each layer gets a range of this size
LAYER_Z_RANGE = 10_000

# Undo/redo stack limit
UNDO_LIMIT = 200

# Grid snapping
GRID_SIZE_DEFAULT = 10

# Autosave interval in milliseconds (2 minutes)
AUTOSAVE_INTERVAL_MS = 120_000

# File format
PROJECT_EXTENSION = ".smk"
THUMBNAIL_MAX_SIZE = 256

# Library
DEFAULT_LIBRARY_DIRECTORY = Path.home() / "SnapMock" / "Library"
LIBRARY_THUMBNAIL_MIN = 80
LIBRARY_THUMBNAIL_MAX = 256
LIBRARY_THUMBNAIL_DEFAULT = 128
LIBRARY_PREVIEW_MIN = 48
LIBRARY_PREVIEW_MAX = 128
LIBRARY_PREVIEW_DEFAULT = 64
LIBRARY_WRITE_BACK_DELAY_MS = 300
LIBRARY_PATHS_MIME = "application/x-snapmock-library-paths"
LIBRARY_IMPORT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp")
PROJECT_FORMAT_VERSION = 1
SNAGIT_EXTENSION = ".snagx"
SNAGIT_FORMAT_VERSION = "1.0"

# Default item properties
DEFAULT_STROKE_WIDTH = 2.0
DEFAULT_STROKE_COLOR = "#FF0000"
DEFAULT_FILL_COLOR = "#00000000"
DEFAULT_FONT_FAMILY = "Sans Serif"
DEFAULT_FONT_SIZE = 14

# Text box frame defaults
DEFAULT_TEXT_BG_COLOR = "#00000000"  # transparent
DEFAULT_TEXT_BORDER_COLOR = "#00000000"  # transparent
DEFAULT_TEXT_BORDER_WIDTH = 0.0
DEFAULT_TEXT_BORDER_RADIUS = 0.0
DEFAULT_TEXT_PADDING = 8.0
DEFAULT_TEXT_WIDTH = 200.0
MIN_DRAG_TEXT_BOX = 10.0  # min px to count as drag-to-create
MIN_TEXT_BOX_WIDTH = 20.0
MIN_TEXT_BOX_HEIGHT = 16.0


class VerticalAlign(Enum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


class BubbleShape(Enum):
    ROUNDED_RECT = "rounded_rect"
    RECT = "rect"
    ELLIPSE = "ellipse"
    CLOUD = "cloud"
    STARBURST = "starburst"
    PILL = "pill"


class TailStyle(Enum):
    STRAIGHT = "straight"
    CURVED = "curved"
    ELBOW = "elbow"


class TailBaseEdge(Enum):
    AUTO = "auto"
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"


class BorderStyle(Enum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    DASHDOT = "dashdot"
    DASHDOTDOT = "dashdotdot"


# Zoom step ladder (percentage values)
ZOOM_STEPS = [
    10,
    15,
    20,
    25,
    33,
    50,
    67,
    75,
    100,
    125,
    150,
    200,
    250,
    300,
    400,
    500,
    600,
    800,
    1200,
    1600,
    2400,
    3200,
]

# Minimum pixels of mouse movement before a drag is recognised
DRAG_THRESHOLD = 3

# Canvas chrome. Colours live in the theme files (resources/themes/*.qss) and are
# read through core/theme_manager.py (General UI PRD 13.4).
PASTEBOARD_MARGIN = 2000
CANVAS_SHADOW_OFFSET = 4

# Checkerboard transparency (cell size; Preferences > Appearance can change it)
CHECKERBOARD_CELL_SIZE = 8

# Rulers
RULER_SIZE = 20

# Grid overlay
GRID_MAJOR_MULTIPLE = 10
GRID_MIN_PIXEL_SPACING = 4

# Empty canvas prompt
EMPTY_CANVAS_TEXT = "Drag an image here, paste from clipboard, or use File > Import Image"
EMPTY_CANVAS_FONT_SIZE = 18
