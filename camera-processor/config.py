"""Shared configuration for the Dig Ophelia camera processor."""

# --- Tile (fixed hardware unit — keep in sync with ESP32 TILE_ROWS / TILE_COLS) ---
TILE_ROWS = 8
TILE_COLS = 16

# --- Tiles per module (one ESP32) — set to match physical wiring ---
MODULE_TILES_X = 2
MODULE_TILES_Y = 1

# --- Module layout in the install ---
INSTALL_MODULES_X = 2
INSTALL_MODULES_Y = 2

# --- Daisy chain (keep in sync with ESP32 TILE_CHAIN_BLOCK_ORDER) ---
# True: stream bytes tile-by-tile (tile 0 rows 0–7, then tile 1, …).
TILE_CHAIN_BLOCK_ORDER = True

# --- Tile order vs camera/debugger grid (keep in sync with ESP32 TILE_MIRROR_X) ---
# True: chain tile 0 is the rightmost column of tiles (your current PCB wiring).
TILE_MIRROR_X = True

# Debugger cell shape (portrait 7-segment digit — keep in sync with debugger_static CSS/JS)
CELL_ASPECT_W = 1
CELL_ASPECT_H = 2

# --- Derived layout (recomputed by recompute_layout()) ---
MODULE_ROWS = 0
MODULE_COLS = 0
MODULE_CELLS = 0
BYTES_PER_MODULE = 0
INSTALL_ROWS = 0
INSTALL_COLS = 0
INSTALL_CELLS = 0
MODULE_COUNT = 0

# Debugger / API aliases (full install grid)
MATRIX_ROWS = 0
MATRIX_COLS = 0

# Processing resolution (recomputed — aspect matches portrait debugger cells)
PROCESS_BASE_WIDTH = 160
PROCESS_WIDTH = 0
PROCESS_HEIGHT = 0
DEBUG_PREVIEW_WIDTH = 0
DEBUG_PREVIEW_HEIGHT = 0


def recompute_layout() -> None:
    """Recompute derived constants after changing tile/module/install knobs."""
    global MODULE_ROWS, MODULE_COLS, MODULE_CELLS, BYTES_PER_MODULE
    global INSTALL_ROWS, INSTALL_COLS, INSTALL_CELLS, MODULE_COUNT
    global MATRIX_ROWS, MATRIX_COLS
    global PROCESS_WIDTH, PROCESS_HEIGHT, DEBUG_PREVIEW_WIDTH, DEBUG_PREVIEW_HEIGHT

    MODULE_ROWS = TILE_ROWS * MODULE_TILES_Y
    MODULE_COLS = TILE_COLS * MODULE_TILES_X
    MODULE_CELLS = MODULE_ROWS * MODULE_COLS
    BYTES_PER_MODULE = (MODULE_CELLS + 7) // 8

    INSTALL_ROWS = MODULE_ROWS * INSTALL_MODULES_Y
    INSTALL_COLS = MODULE_COLS * INSTALL_MODULES_X
    INSTALL_CELLS = INSTALL_ROWS * INSTALL_COLS
    MODULE_COUNT = INSTALL_MODULES_X * INSTALL_MODULES_Y

    MATRIX_ROWS = INSTALL_ROWS
    MATRIX_COLS = INSTALL_COLS

    PROCESS_WIDTH = PROCESS_BASE_WIDTH
    PROCESS_HEIGHT = max(
        1,
        round(
            PROCESS_BASE_WIDTH
            * INSTALL_ROWS
            * CELL_ASPECT_H
            / (INSTALL_COLS * CELL_ASPECT_W)
        ),
    )
    DEBUG_PREVIEW_WIDTH = PROCESS_WIDTH
    DEBUG_PREVIEW_HEIGHT = PROCESS_HEIGHT


recompute_layout()

CAMERA_INDEX = 0
CAMERA_WIDTH = 160
CAMERA_HEIGHT = 120
CAMERA_FPS_REQUEST = 30
CAMERA_WARMUP_FRAMES = 10

# Auto-exposure (AGC) — set False to lock exposure before capturing the background.
# A fixed exposure makes background subtraction far more stable: without it the camera
# silently re-adjusts gain when scene brightness changes (e.g. a person enters, or a
# light turns on), shifting every pixel value and creating false-negative blobs.
# The CAMERA_EXPOSURE value is V4L2 log-scale (typically −13 … 0). Try −6 first;
# lower values = shorter shutter / darker image. Only applied on Linux (V4L2).
CAMERA_AUTO_EXPOSURE = True   # True = let camera manage; False = lock to CAMERA_EXPOSURE
CAMERA_EXPOSURE = -6          # V4L2 exposure value used when CAMERA_AUTO_EXPOSURE is False

TARGET_FPS = 25

BG_DIFF_THRESHOLD = 30
BLUR_KERNEL = (5, 5)
INVERT_DETECTION = False
MIRROR_HORIZONTAL = True

MORPHOLOGY_ENABLED = True
MORPH_KERNEL_SIZE = 3
MORPH_OPEN = False
MORPH_CLOSE = True
MIN_CONTOUR_AREA = 50

BACKGROUND_WARMUP_S = 3

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8080

DEBUG_HOST = "0.0.0.0"
DEBUG_PORT = 8080
DEBUG_MJPEG_FPS = 20
DEBUG_JPEG_QUALITY = 30
