"""USB webcam capture via OpenCV / V4L2."""

from __future__ import annotations

import glob
import platform
import sys
from typing import Optional, Union

import cv2
import numpy as np

import config

CameraIndex = Union[int, str]


def list_video_devices() -> list[str]:
    """Return available /dev/video* paths on Linux."""
    return sorted(glob.glob("/dev/video*"))


def open_camera(
    index: CameraIndex = config.CAMERA_INDEX,
    width: int = config.CAMERA_WIDTH,
    height: int = config.CAMERA_HEIGHT,
) -> cv2.VideoCapture:
    """Open USB webcam and request capture resolution."""
    cap = _create_capture(index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera {index!r}. "
            f"Available devices: {list_video_devices() or 'none'}"
        )

    if platform.system() == "Linux":
        # MJPEG reduces USB bandwidth vs raw YUYV — helps sustain 20+ FPS.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS_REQUEST)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def _create_capture(index: CameraIndex) -> cv2.VideoCapture:
    if platform.system() == "Linux":
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        if cap.isOpened():
            return cap
    return cv2.VideoCapture(index)


def warmup(cap: cv2.VideoCapture, frames: int = config.CAMERA_WARMUP_FRAMES) -> None:
    """Discard initial frames while auto-exposure settles."""
    for _ in range(frames):
        cap.read()


def read_frame(cap: cv2.VideoCapture) -> Optional[np.ndarray]:
    """Read one BGR frame. Returns None on failure."""
    ok, frame = cap.read()
    return frame if ok else None


def release(cap: cv2.VideoCapture) -> None:
    cap.release()


def print_device_hint() -> None:
    devices = list_video_devices()
    if devices:
        print("Available video devices:")
        for path in devices:
            print(f"  {path}")
    else:
        print("No /dev/video* devices found.", file=sys.stderr)
