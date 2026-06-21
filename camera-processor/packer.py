"""Pack binary grid into bytes for ESP32 (MSB-first)."""

from __future__ import annotations

import numpy as np


def pack_grid(grid: np.ndarray) -> bytes:
    """
    Pack row-major matrix into a byte frame.

    Bit 7 of byte 0 = cell (row=0, col=0), matching ESP32 processMessage().
    """
    flat = np.asarray(grid, dtype=np.uint8).reshape(-1)
    total_cells = flat.size
    bytes_count = (total_cells + 7) // 8

    packed = bytearray(bytes_count)
    for i, cell in enumerate(flat):
        if cell:
            byte_index = i // 8
            bit_index = 7 - (i % 8)
            packed[byte_index] |= 1 << bit_index
    return bytes(packed)


def unpack_grid(data: bytes, rows: int, cols: int) -> np.ndarray:
    """Unpack bytes back into a matrix grid (for debugging)."""
    total_cells = rows * cols
    bytes_count = (total_cells + 7) // 8
    if len(data) != bytes_count:
        raise ValueError(f"Expected {bytes_count} bytes, got {len(data)}")

    grid = np.zeros(total_cells, dtype=np.uint8)
    for i in range(total_cells):
        byte_index = i // 8
        bit_index = 7 - (i % 8)
        grid[i] = (data[byte_index] >> bit_index) & 1
    return grid.reshape(rows, cols)
