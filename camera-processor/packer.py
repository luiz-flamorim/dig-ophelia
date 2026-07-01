"""Pack binary grid into bytes for ESP32 (MSB-first)."""

from __future__ import annotations

import numpy as np

import config


def cells_per_tile() -> int:
    return config.TILE_ROWS * config.TILE_COLS


def logical_tile_x_to_chain(tile_x: int) -> int:
    """Map debugger/camera tile column to SPI chain tile index."""
    if config.TILE_MIRROR_X:
        return config.MODULE_TILES_X - 1 - tile_x
    return tile_x


def chain_tile_x_to_logical(chain_tile_x: int) -> int:
    """Inverse of logical_tile_x_to_chain()."""
    if config.TILE_MIRROR_X:
        return config.MODULE_TILES_X - 1 - chain_tile_x
    return chain_tile_x


def stream_index(row: int, col: int, cols: int) -> int:
    """Logical row-major index (row 0 top, col 0 left)."""
    return row * cols + col


def software_coords(index: int, cols: int) -> tuple[int, int]:
    """Inverse of stream_index() for logical row-major coords."""
    return index // cols, index % cols


def logical_to_stream_index(row: int, col: int) -> int:
    """
    Map logical module cell to SPI stream index.

    Logical layout: tiles side-by-side (and stacked for 2×2) in the module grid.
    Stream order: each tile is a contiguous block (tile 0 rows 0–7, then tile 1, …).
    TILE_MIRROR_X flips which logical tile maps to which chain block.
    """
    if not config.TILE_CHAIN_BLOCK_ORDER:
        return stream_index(row, col, config.MODULE_COLS)

    tile_x = col // config.TILE_COLS
    tile_y = row // config.TILE_ROWS
    chain_tile_x = logical_tile_x_to_chain(tile_x)
    tile_index = tile_y * config.MODULE_TILES_X + chain_tile_x
    row_in_tile = row % config.TILE_ROWS
    col_in_tile = col % config.TILE_COLS
    in_tile = row_in_tile * config.TILE_COLS + col_in_tile
    return tile_index * cells_per_tile() + in_tile


def stream_to_logical_coords(index: int) -> tuple[int, int]:
    """Inverse of logical_to_stream_index() for debugger / probe highlight."""
    if not config.TILE_CHAIN_BLOCK_ORDER:
        return software_coords(index, config.MODULE_COLS)

    cpt = cells_per_tile()
    tile_index = index // cpt
    in_tile = index % cpt
    row_in_tile = in_tile // config.TILE_COLS
    col_in_tile = in_tile % config.TILE_COLS
    tile_y = tile_index // config.MODULE_TILES_X
    chain_tile_x = tile_index % config.MODULE_TILES_X
    tile_x = chain_tile_x_to_logical(chain_tile_x)
    row = tile_y * config.TILE_ROWS + row_in_tile
    col = tile_x * config.TILE_COLS + col_in_tile
    return row, col


def pack_single_stream_index(index: int, total_cells: int) -> bytes:
    """Pack a frame with exactly one stream index lit (wiring probe)."""
    bytes_count = (total_cells + 7) // 8
    packed = bytearray(bytes_count)
    if 0 <= index < total_cells:
        byte_index = index // 8
        bit_index = 7 - (index % 8)
        packed[byte_index] |= 1 << bit_index
    return bytes(packed)


def _set_stream_bit(packed: bytearray, index: int, total_cells: int) -> None:
    if 0 <= index < total_cells:
        byte_index = index // 8
        bit_index = 7 - (index % 8)
        packed[byte_index] |= 1 << bit_index


def pack_tile_row(tile_index: int, row_in_tile: int, total_cells: int) -> bytes:
    """Pack a frame with one full row (all columns) of one tile lit (wiring probe)."""
    bytes_count = (total_cells + 7) // 8
    packed = bytearray(bytes_count)
    base = tile_index * cells_per_tile() + row_in_tile * config.TILE_COLS
    for col in range(config.TILE_COLS):
        _set_stream_bit(packed, base + col, total_cells)
    return bytes(packed)


def pack_tile_col(tile_index: int, col_in_tile: int, total_cells: int) -> bytes:
    """Pack a frame with one full column (all rows) of one tile lit (wiring probe)."""
    bytes_count = (total_cells + 7) // 8
    packed = bytearray(bytes_count)
    base = tile_index * cells_per_tile() + col_in_tile
    for row in range(config.TILE_ROWS):
        _set_stream_bit(packed, base + row * config.TILE_COLS, total_cells)
    return bytes(packed)


def pack_grid(grid: np.ndarray) -> bytes:
    """
    Pack logical module grid into a byte frame for the ESP32.

    Bit 7 of byte 0 = stream index 0 (first cell on the SPI chain).
    """
    grid = np.asarray(grid, dtype=np.uint8)
    rows, cols = grid.shape
    bytes_count = (rows * cols + 7) // 8
    packed = bytearray(bytes_count)

    for row in range(rows):
        for col in range(cols):
            if grid[row, col]:
                i = logical_to_stream_index(row, col)
                byte_index = i // 8
                bit_index = 7 - (i % 8)
                packed[byte_index] |= 1 << bit_index
    return bytes(packed)


def unpack_grid(data: bytes, rows: int, cols: int) -> np.ndarray:
    """Unpack bytes back into a logical row-major module grid (for debugging)."""
    total_cells = rows * cols
    bytes_count = (total_cells + 7) // 8
    if len(data) != bytes_count:
        raise ValueError(f"Expected {bytes_count} bytes, got {len(data)}")

    grid = np.zeros((rows, cols), dtype=np.uint8)
    for i in range(total_cells):
        byte_index = i // 8
        bit_index = 7 - (i % 8)
        if (data[byte_index] >> bit_index) & 1:
            row, col = stream_to_logical_coords(i)
            grid[row, col] = 1
    return grid
