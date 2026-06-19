#!/usr/bin/env python3
"""Camera processor — live processing, ESP32 API, and debugger UI in one process."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import signal
import socket
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import cv2
import numpy as np

import camera
import config
import modules
from process import ProcessingSettings, capture_background, process_frame

STATIC_DIR = Path(__file__).parent / "debugger_static"
BOUNDARY = b"--frame"
MODULE_PATH = re.compile(r"^/api/module/(\d+)$")


class SharedState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.settings = ProcessingSettings()
        self.background: Optional[np.ndarray] = None
        self.grid = np.zeros((config.MATRIX_ROWS, config.MATRIX_COLS), dtype=np.uint8)
        self.module_payloads: dict[int, bytes] = {}
        self.jpeg: bytes = b""
        self.frame_seq: int = 0
        self.fps: float = 0.0
        self.show_processed: bool = False
        self.capture_background_requested = False
        self.running = True


state = SharedState()


def capture_loop(index, fps: float, warmup_s: int) -> None:
    cap = camera.open_camera(index)
    camera.warmup(cap)

    if warmup_s > 0:
        print(f"Capturing background in {warmup_s}s — keep scene clear...")
        time.sleep(warmup_s)
        with state.lock:
            settings = _copy_settings(state.settings)
        try:
            background = capture_background(cap, settings)
            with state.lock:
                state.background = background
            print("Background captured.")
        except RuntimeError as exc:
            print(f"Initial background capture failed: {exc}")

    frame_interval = 1.0 / max(fps, 1)
    fps_times: list[float] = []

    while state.running:
        loop_start = time.perf_counter()

        with state.lock:
            settings = _copy_settings(state.settings)
            show_processed = state.show_processed
            background = state.background
            if state.capture_background_requested:
                state.capture_background_requested = False
                try:
                    state.background = capture_background(cap, settings)
                    background = state.background
                    print("Background frame captured")
                except RuntimeError as exc:
                    print(f"Background capture failed: {exc}")

        frame = camera.read_frame(cap)
        if frame is None:
            time.sleep(0.05)
            continue

        grid, preview, _ = process_frame(frame, settings, background=background)
        payloads = modules.build_module_payloads(grid)

        jpeg = b""
        if show_processed:
            preview_size = (config.DEBUG_PREVIEW_WIDTH, config.DEBUG_PREVIEW_HEIGHT)
            mask_preview = cv2.resize(preview, preview_size)
            ok, encoded = cv2.imencode(
                ".jpg",
                mask_preview,
                [int(cv2.IMWRITE_JPEG_QUALITY), config.DEBUG_JPEG_QUALITY],
            )
            jpeg = encoded.tobytes() if ok else b""

        elapsed = time.perf_counter() - loop_start
        time.sleep(max(0, frame_interval - elapsed))

        frame_elapsed = time.perf_counter() - loop_start
        fps_times.append(frame_elapsed)
        if len(fps_times) > 30:
            fps_times.pop(0)
        current_fps = len(fps_times) / sum(fps_times) if fps_times else 0.0

        with state.lock:
            state.grid = grid
            state.module_payloads = payloads
            state.fps = current_fps
            if show_processed and jpeg:
                state.jpeg = jpeg
                state.frame_seq += 1
            elif not show_processed:
                state.jpeg = b""

    camera.release(cap)


def _copy_settings(settings: ProcessingSettings) -> ProcessingSettings:
    return ProcessingSettings(
        bg_diff_threshold=settings.bg_diff_threshold,
        invert=settings.invert,
        mirror=settings.mirror,
        blur_kernel=settings.blur_kernel,
        morphology=settings.morphology,
    )


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass

    def _path(self) -> str:
        return urlparse(self.path).path

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self._path()

        if path == "/":
            return self._serve_file(STATIC_DIR / "index.html")

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            return self._serve_file(STATIC_DIR / rel)

        if path == "/api/config":
            return self._send_json(
                {
                    "matrix_rows": config.MATRIX_ROWS,
                    "matrix_cols": config.MATRIX_COLS,
                }
            )

        if path == "/api/state":
            with state.lock:
                payload = {
                    "grid": state.grid.astype(int).tolist(),
                    "fps": state.fps,
                    "bg_threshold": state.settings.bg_diff_threshold,
                    "invert": state.settings.invert,
                    "show_processed": state.show_processed,
                    "has_background": state.background is not None,
                }
            return self._send_json(payload)

        if path == "/api/stream":
            return self._stream_mjpeg()

        if path == "/api/health":
            with state.lock:
                return self._send_json(
                    {
                        "ok": True,
                        "fps": round(state.fps, 2),
                        "frame_seq": state.frame_seq,
                        "module_count": config.MODULE_COUNT,
                        "bytes_per_module": config.BYTES_PER_FRAME,
                        "has_background": state.background is not None,
                    }
                )

        match = MODULE_PATH.match(path)
        if match:
            module_id = int(match.group(1))
            if module_id < 0 or module_id >= config.MODULE_COUNT:
                return self.send_error(HTTPStatus.NOT_FOUND)

            with state.lock:
                payload = state.module_payloads.get(module_id)

            if payload is None:
                return self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)

            return self._send_bytes(payload, "application/octet-stream")

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = self._path()

        if path == "/api/settings":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                return self.send_error(HTTPStatus.BAD_REQUEST)

            with state.lock:
                if "bg_threshold" in data:
                    state.settings.bg_diff_threshold = int(data["bg_threshold"])
                if "invert" in data:
                    state.settings.invert = bool(data["invert"])
                if "show_processed" in data:
                    state.show_processed = bool(data["show_processed"])
                    if not state.show_processed:
                        state.jpeg = b""

            return self._send_json({"ok": True})

        if path == "/api/background/capture":
            with state.lock:
                state.capture_background_requested = True
            return self._send_json({"ok": True})

        self.send_error(HTTPStatus.NOT_FOUND)

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)

        content_type, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self._send_bytes(data, content_type or "application/octet-stream")

    def _stream_mjpeg(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            last_seq = -1
            while True:
                with state.lock:
                    jpeg = state.jpeg
                    seq = state.frame_seq
                if not jpeg:
                    time.sleep(0.05)
                    continue
                if seq == last_seq:
                    time.sleep(0.005)
                    continue

                last_seq = seq
                self.wfile.write(BOUNDARY + b"\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                self.wfile.write(jpeg + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dig Ophelia camera processor")
    parser.add_argument("--host", default=config.SERVER_HOST)
    parser.add_argument("--port", type=int, default=config.SERVER_PORT)
    parser.add_argument("--index", default=config.CAMERA_INDEX)
    parser.add_argument("--fps", type=float, default=config.TARGET_FPS)
    parser.add_argument("--bg-threshold", type=int, default=config.BG_DIFF_THRESHOLD)
    parser.add_argument("--invert", action="store_true", default=config.INVERT_DETECTION)
    parser.add_argument("--warmup", type=int, default=config.BACKGROUND_WARMUP_S)
    parser.add_argument("--morphology", action="store_true", help="Enable mask clean-up (slower)")
    args = parser.parse_args()

    state.settings = ProcessingSettings(
        bg_diff_threshold=args.bg_threshold,
        invert=args.invert,
        morphology=args.morphology,
    )

    def handle_signal(_signum, _frame) -> None:
        state.running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        camera.open_camera(args.index).release()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        camera.print_device_hint()
        return 1

    capture_thread = threading.Thread(
        target=capture_loop,
        args=(args.index, args.fps, args.warmup),
        daemon=True,
    )
    capture_thread.start()

    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    ip = local_ip()
    print(f"Running at http://{ip}:{args.port}")
    print(f"Debugger UI: http://{ip}:{args.port}/")
    print(f"ESP32 poll:  GET /api/module/0  ({config.BYTES_PER_FRAME} bytes)")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        state.running = False
        server.shutdown()
        capture_thread.join(timeout=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
