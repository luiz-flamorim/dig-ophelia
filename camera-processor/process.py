"""Image processing pipeline: frame to binary grid via background subtraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

import config


@dataclass
class ProcessingSettings:
    bg_diff_threshold: int = config.BG_DIFF_THRESHOLD
    invert: bool = config.INVERT_DETECTION
    mirror: bool = config.MIRROR_HORIZONTAL
    blur_kernel: tuple[int, int] = config.BLUR_KERNEL
    morphology: bool = config.MORPHOLOGY_ENABLED


def mirror_frame(frame: np.ndarray) -> np.ndarray:
    return cv2.flip(frame, 1)


def center_crop_to_install_aspect(frame: np.ndarray) -> np.ndarray:
    """Center-crop to match debugger grid aspect (portrait cells)."""
    height, width = frame.shape[:2]
    if height == 0 or width == 0:
        return frame

    target_aspect = (
        config.INSTALL_COLS * config.CELL_ASPECT_W
    ) / (config.INSTALL_ROWS * config.CELL_ASPECT_H)
    source_aspect = width / height

    if abs(source_aspect - target_aspect) < 1e-6:
        return frame

    if source_aspect > target_aspect:
        new_width = max(1, int(round(height * target_aspect)))
        x0 = (width - new_width) // 2
        return frame[:, x0 : x0 + new_width]

    new_height = max(1, int(round(width / target_aspect)))
    y0 = (height - new_height) // 2
    return frame[y0 : y0 + new_height, :]


def prepare_frame(frame: np.ndarray, settings: ProcessingSettings) -> np.ndarray:
    """Mirror, crop to install aspect, then downscale for processing."""
    working = mirror_frame(frame) if settings.mirror else frame
    working = center_crop_to_install_aspect(working)
    height, width = working.shape[:2]
    if width != config.PROCESS_WIDTH or height != config.PROCESS_HEIGHT:
        working = cv2.resize(
            working,
            (config.PROCESS_WIDTH, config.PROCESS_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )
    return working


def to_grey_blur(frame: np.ndarray, kernel: tuple[int, int]) -> np.ndarray:
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(grey, kernel, 0)


def background_diff(grey: np.ndarray, background: np.ndarray) -> np.ndarray:
    """Return raw per-pixel absolute difference (0–255, not yet thresholded)."""
    return cv2.absdiff(background, grey)


def background_mask(
    grey: np.ndarray,
    background: np.ndarray,
    settings: ProcessingSettings,
) -> np.ndarray:
    diff = background_diff(grey, background)
    _, mask = cv2.threshold(diff, settings.bg_diff_threshold, 255, cv2.THRESH_BINARY)
    return mask


def clean_mask(mask: np.ndarray, settings: ProcessingSettings) -> np.ndarray:
    if not settings.morphology:
        return mask

    k = config.MORPH_KERNEL_SIZE
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    cleaned = mask

    if config.MORPH_OPEN:
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
    if config.MORPH_CLOSE:
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    if config.MIN_CONTOUR_AREA > 0:
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filtered = np.zeros_like(cleaned)
        for contour in contours:
            if cv2.contourArea(contour) >= config.MIN_CONTOUR_AREA:
                cv2.drawContours(filtered, [contour], -1, 255, cv2.FILLED)
        cleaned = filtered

    return cleaned


def grid_from_resize(mask: np.ndarray, invert: bool = False) -> np.ndarray:
    small = cv2.resize(
        mask,
        (config.INSTALL_COLS, config.INSTALL_ROWS),
        interpolation=cv2.INTER_NEAREST,
    )
    grid = (small > 0).astype(np.uint8)
    if invert:
        grid = 1 - grid
    return grid


def process_frame(
    frame: np.ndarray,
    settings: ProcessingSettings,
    background: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """
    Process one BGR frame using background subtraction.

    Returns:
        grid:     uint8 binary matrix (INSTALL_ROWS × INSTALL_COLS)
        mask:     binary mask (0 or 255) before grid down-scaling
        grey:     greyscale blurred current frame (for raw preview)
        diff_raw: per-pixel absdiff before thresholding, or None if no background
    """
    working = prepare_frame(frame, settings)
    grey = to_grey_blur(working, settings.blur_kernel)

    if background is None:
        mask = np.zeros_like(grey)
        diff_raw: Optional[np.ndarray] = None
    else:
        diff_raw = background_diff(grey, background)
        _, binary = cv2.threshold(
            diff_raw, settings.bg_diff_threshold, 255, cv2.THRESH_BINARY
        )
        mask = clean_mask(binary, settings)

    grid = grid_from_resize(mask, invert=settings.invert)
    return grid, mask, grey, diff_raw


def build_preview(
    mask: np.ndarray,
    grey: np.ndarray,
    diff_raw: Optional[np.ndarray],
    background: Optional[np.ndarray],
    mode: str,
    threshold: int = config.BG_DIFF_THRESHOLD,
) -> np.ndarray:
    """Return a BGR image for the MJPEG debugger stream.

    Modes
    -----
    mask       Binary detection mask (white = detected).  Default.
    diff       Raw absdiff scaled so threshold → white.  Reveals areas where
               the signal is genuinely zero vs. just below threshold.
    raw        Greyscale current frame — lets you see what the camera actually
               captures (useful for spotting AGC / lens / sensor problems).
    background The captured background reference frame.
    """
    if mode == "diff":
        if diff_raw is not None:
            scale = 255.0 / max(1, threshold)
            scaled = np.clip(diff_raw.astype(np.float32) * scale, 0, 255).astype(np.uint8)
        else:
            scaled = np.zeros_like(grey)
        return cv2.cvtColor(scaled, cv2.COLOR_GRAY2BGR)

    if mode == "raw":
        return cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)

    if mode == "background":
        src = background if background is not None else np.zeros_like(grey)
        return cv2.cvtColor(src, cv2.COLOR_GRAY2BGR)

    # "mask" (default)
    return cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)


def draw_grid_overlay(frame: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Draw grid cell rectangles on a BGR frame."""
    output = frame.copy()
    height, width = output.shape[:2]
    grid_rows, grid_cols = grid.shape
    cell_w = width // grid_cols
    cell_h = height // grid_rows
    cell_tint = np.full((cell_h, cell_w, 3), (40, 40, 220), dtype=np.uint8)

    for row in range(grid_rows):
        y1 = row * cell_h
        y2 = (row + 1) * cell_h
        for col in range(grid_cols):
            x1 = col * cell_w
            x2 = (col + 1) * cell_w

            if grid[row, col]:
                roi = output[y1:y2, x1:x2]
                cv2.addWeighted(cell_tint, 0.45, roi, 0.55, 0, roi)

            cv2.rectangle(output, (x1, y1), (x2, y2), (200, 200, 200), 1)

    return output


def grid_to_ascii(grid: np.ndarray) -> str:
    lines = []
    grid_rows, grid_cols = grid.shape
    for row in range(grid_rows):
        chars = "".join("#" if grid[row, col] else "." for col in range(grid_cols))
        lines.append(chars)
    return "\n".join(lines)


def capture_background(cap, settings: ProcessingSettings, frames: int = 10) -> np.ndarray:
    """Average greyscale frames for a stable background reference."""
    accum: Optional[np.ndarray] = None
    count = 0

    for _ in range(frames):
        from camera import read_frame

        frame = read_frame(cap)
        if frame is None:
            continue
        working = prepare_frame(frame, settings)
        grey = to_grey_blur(working, settings.blur_kernel).astype(np.float32)
        accum = grey if accum is None else accum + grey
        count += 1

    if accum is None or count == 0:
        raise RuntimeError("Could not capture background frame")

    return (accum / count).astype(np.uint8)
