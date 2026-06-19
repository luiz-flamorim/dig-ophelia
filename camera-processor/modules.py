"""Split processed grid into per-module binary payloads for ESP32 polling."""

from __future__ import annotations

import numpy as np

import config
import frame_output


def build_module_payloads(grid: np.ndarray) -> dict[int, bytes]:
    """
    Return latest frame bytes keyed by module ID.

    Phase 1: module 0 is the full 8×16 tile (16 bytes).
    Later phases split the mask into 2×2 tiles per module.
    """
    payloads: dict[int, bytes] = {}
    for module_id in range(config.MODULE_COUNT):
        if module_id == 0:
            payloads[module_id] = frame_output.build_payload(grid)
    return payloads
