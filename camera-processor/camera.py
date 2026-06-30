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

    if not config.CAMERA_AUTO_EXPOSURE:
        _lock_exposure(cap)

    return cap


def _lock_exposure(cap: cv2.VideoCapture) -> None:
    """Disable AGC and set a fixed exposure (V4L2 / Linux only).

    V4L2 auto-exposure mode values differ by driver; 1 = manual is the most
    common.  The exposure property uses a log-scale integer (e.g. -6 ≈ 1/64 s).
    Silently skips on non-Linux platforms or cameras that ignore these props.
    """
    if platform.system() != "Linux":
        return
    # 1 = manual, 3 = aperture-priority (auto) on most V4L2 drivers
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, config.CAMERA_EXPOSURE)
    print(
        f"[camera] auto-exposure disabled, exposure={config.CAMERA_EXPOSURE} "
        f"(override CAMERA_AUTO_EXPOSURE/CAMERA_EXPOSURE in config.py)"
    )


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
