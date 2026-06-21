"""Split processed grid into per-module binary payloads for ESP32 polling."""

from __future__ import annotations

import numpy as np

import config
import frame_output


def module_region(grid: np.ndarray, module_id: int) -> np.ndarray:
    """Extract one module-sized region from the full install grid."""
    expected = (config.INSTALL_ROWS, config.INSTALL_COLS)
    if grid.shape != expected:
        raise ValueError(f"Expected install grid {expected}, got {grid.shape}")

    if module_id < 0 or module_id >= config.MODULE_COUNT:
        raise ValueError(f"Module ID out of range: {module_id}")

    mx = module_id % config.INSTALL_MODULES_X
    my = module_id // config.INSTALL_MODULES_X
    row0 = my * config.MODULE_ROWS
    col0 = mx * config.MODULE_COLS
    return grid[
        row0 : row0 + config.MODULE_ROWS,
        col0 : col0 + config.MODULE_COLS,
    ]


def build_module_payloads(grid: np.ndarray) -> dict[int, bytes]:
    """Return latest frame bytes keyed by module ID."""
    payloads: dict[int, bytes] = {}
    for module_id in range(config.MODULE_COUNT):
        region = module_region(grid, module_id)
        payloads[module_id] = frame_output.build_payload(region)
    return payloads
