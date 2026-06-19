#!/usr/bin/env python3
"""Background subtraction loop — produces packed frame payloads (transport TBD)."""

from __future__ import annotations

import argparse
import signal
import sys
import time

import camera
import config
import frame_output
from process import ProcessingSettings, capture_background, process_frame

_running = True


def _handle_signal(_signum, _frame) -> None:
    global _running
    _running = False


def main() -> int:
    parser = argparse.ArgumentParser(description="Background subtraction processor")
    parser.add_argument("--index", default=config.CAMERA_INDEX)
    parser.add_argument("--fps", type=float, default=config.TARGET_FPS)
    parser.add_argument("--bg-threshold", type=int, default=config.BG_DIFF_THRESHOLD)
    parser.add_argument("--invert", action="store_true", default=config.INVERT_DETECTION)
    parser.add_argument("--warmup", type=int, default=config.BACKGROUND_WARMUP_S)
    parser.add_argument("--morphology", action="store_true", help="Enable mask clean-up (slower)")
    args = parser.parse_args()

    settings = ProcessingSettings(
        bg_diff_threshold=args.bg_threshold,
        invert=args.invert,
        morphology=args.morphology,
    )

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        cap = camera.open_camera(args.index)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        camera.print_device_hint()
        return 1

    camera.warmup(cap)
    print(f"Capturing background in {args.warmup}s — keep scene clear...")
    time.sleep(args.warmup)
    background = capture_background(cap, settings)
    print("Background captured.")

    interval = 1.0 / max(args.fps, 1)
    print(f"Running (background subtract, {args.fps} FPS target). Ctrl+C to stop.")

    while _running:
        loop_start = time.perf_counter()
        frame = camera.read_frame(cap)
        if frame is None:
            continue

        grid, _, _ = process_frame(frame, settings, background=background)
        payload = frame_output.build_payload(grid)
        # TODO: send payload to ESP32 over WiFi

        elapsed = time.perf_counter() - loop_start
        time.sleep(max(0, interval - elapsed))

    print("\nShutting down.")
    camera.release(cap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
