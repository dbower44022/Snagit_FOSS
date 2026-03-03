"""Application-wide constants."""

from enum import Enum

APP_NAME = "SnapMock"
APP_VERSION = "0.1.0"
ORG_NAME = "SnapMock"
ORG_DOMAIN = "snapmock.org"

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

# Pasteboard (gray area around canvas)
PASTEBOARD_COLOR = "#505050"
PASTEBOARD_MARGIN = 2000
CANVAS_SHADOW_OFFSET = 4
CANVAS_SHADOW_COLOR = "#66000000"

# Checkerboard transparency
CHECKERBOARD_CELL_SIZE = 8
CHECKERBOARD_COLOR_A = "#FFFFFF"
CHECKERBOARD_COLOR_B = "#CCCCCC"

# Rulers
RULER_SIZE = 20
RULER_BG_COLOR = "#F0F0F0"
RULER_TEXT_COLOR = "#333333"
RULER_TICK_COLOR = "#999999"
RULER_CURSOR_COLOR = "#FF0000"

# Grid overlay
GRID_COLOR = "#33000000"
GRID_COLOR_MAJOR = "#55000000"
GRID_MAJOR_MULTIPLE = 10
GRID_MIN_PIXEL_SPACING = 4

# Empty canvas prompt
EMPTY_CANVAS_TEXT = "Drag an image here, paste from clipboard, or use File > Import Image"
EMPTY_CANVAS_TEXT_COLOR = "#AAAAAA"
EMPTY_CANVAS_FONT_SIZE = 18
