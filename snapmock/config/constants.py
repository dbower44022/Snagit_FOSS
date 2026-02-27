"""Application-wide constants."""

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

# Default item properties
DEFAULT_STROKE_WIDTH = 2.0
DEFAULT_STROKE_COLOR = "#FF0000"
DEFAULT_FILL_COLOR = "#00000000"
DEFAULT_FONT_FAMILY = "Sans Serif"
DEFAULT_FONT_SIZE = 14
