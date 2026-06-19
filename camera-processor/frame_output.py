"""Packed frame payload ready for transport (WiFi TBD)."""

from __future__ import annotations

import numpy as np

import config
import packer


def build_payload(grid: np.ndarray) -> bytes:
    """Pack a grid into a fixed-size byte frame for the display controller."""
    payload = packer.pack_grid(grid)
    if len(payload) != config.BYTES_PER_FRAME:
        raise ValueError(f"Expected {config.BYTES_PER_FRAME} bytes, got {len(payload)}")
    return payload
