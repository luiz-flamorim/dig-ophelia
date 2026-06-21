"""Packed frame payload ready for transport (WiFi TBD)."""

from __future__ import annotations

import numpy as np

import config
import packer


def build_payload(grid: np.ndarray) -> bytes:
    """Pack a module-sized grid into a fixed-size byte frame for the display controller."""
    rows, cols = grid.shape
    if (rows, cols) != (config.MODULE_ROWS, config.MODULE_COLS):
        raise ValueError(
            f"Expected module grid {(config.MODULE_ROWS, config.MODULE_COLS)}, got {(rows, cols)}"
        )

    payload = packer.pack_grid(grid)
    if len(payload) != config.BYTES_PER_MODULE:
        raise ValueError(f"Expected {config.BYTES_PER_MODULE} bytes, got {len(payload)}")
    return payload
