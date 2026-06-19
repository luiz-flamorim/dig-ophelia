"""Pack binary grid into bytes for ESP32 (MSB-first)."""

from __future__ import annotations

import numpy as np

import config


def pack_grid(grid: np.ndarray) -> bytes:
    """
    Pack row-major matrix into a byte frame.

    Bit 7 of byte 0 = cell (row=0, col=0), matching ESP32 processMessage().
    """
    flat = np.asarray(grid, dtype=np.uint8).reshape(-1)
    if flat.size != config.TOTAL_CELLS:
        raise ValueError(f"Expected {config.TOTAL_CELLS} cells, got {flat.size}")

    packed = bytearray(config.BYTES_PER_FRAME)
    for i, cell in enumerate(flat):
        if cell:
            byte_index = i // 8
            bit_index = 7 - (i % 8)
            packed[byte_index] |= 1 << bit_index
    return bytes(packed)


def unpack_grid(data: bytes) -> np.ndarray:
    """Unpack bytes back into a matrix grid (for debugging)."""
    if len(data) != config.BYTES_PER_FRAME:
        raise ValueError(f"Expected {config.BYTES_PER_FRAME} bytes, got {len(data)}")

    grid = np.zeros(config.TOTAL_CELLS, dtype=np.uint8)
    for i in range(config.TOTAL_CELLS):
        byte_index = i // 8
        bit_index = 7 - (i % 8)
        grid[i] = (data[byte_index] >> bit_index) & 1
    return grid.reshape(config.MATRIX_ROWS, config.MATRIX_COLS)
