#!/usr/bin/env python3
"""Camera processor — live processing, ESP32 API, and debugger UI in one process."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
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
import packer
from process import ProcessingSettings, build_preview, capture_background, process_frame

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
        # "off" | "mask" | "diff" | "raw" | "background"
        self.preview_mode: str = "off"
        self.capture_background_requested = False
        self.running = True
        self.probe_enabled = False
        self.probe_auto = False
        self.probe_index = 0
        self.probe_interval_s = 0.15
        self.probe_last_advance = 0.0
        # "cell" | "row" | "col" — row/col light a whole row/column within one tile.
        self.probe_mode = "cell"
        self.probe_module_id = 0
        self.probe_tile_index = 0


state = SharedState()


def _probe_tiles_per_module() -> int:
    return config.MODULE_CELLS // (config.TILE_ROWS * config.TILE_COLS)


def _probe_total_steps() -> int:
    """Number of positions the probe index can take in the current mode."""
    if state.probe_mode == "row":
        return _probe_tiles_per_module() * config.TILE_ROWS
    if state.probe_mode == "col":
        return _probe_tiles_per_module() * config.TILE_COLS
    return config.MODULE_CELLS


def _apply_probe() -> None:
    """Update grid + module payloads for the current probe position."""
    idx = state.probe_index
    module_id = state.probe_module_id % max(config.MODULE_COUNT, 1)

    if state.probe_mode == "row":
        tile_index = idx // config.TILE_ROWS
        row_in_tile = idx % config.TILE_ROWS
        payload = packer.pack_tile_row(tile_index, row_in_tile, config.MODULE_CELLS)
    elif state.probe_mode == "col":
        tile_index = idx // config.TILE_COLS
        col_in_tile = idx % config.TILE_COLS
        payload = packer.pack_tile_col(tile_index, col_in_tile, config.MODULE_CELLS)
    else:
        tile_index = idx // (config.TILE_ROWS * config.TILE_COLS)
        payload = packer.pack_single_stream_index(idx, config.MODULE_CELLS)

    # Place the probed module's payload into the full-install debugger grid.
    grid = np.zeros((config.INSTALL_ROWS, config.INSTALL_COLS), dtype=np.uint8)
    module_grid = packer.unpack_grid(payload, config.MODULE_ROWS, config.MODULE_COLS)
    mx = module_id % config.INSTALL_MODULES_X
    my = module_id // config.INSTALL_MODULES_X
    row0 = my * config.MODULE_ROWS
    col0 = mx * config.MODULE_COLS
    grid[row0 : row0 + config.MODULE_ROWS, col0 : col0 + config.MODULE_COLS] = module_grid

    payloads: dict[int, bytes] = {}
    for mid in range(config.MODULE_COUNT):
        if mid == module_id:
            payloads[mid] = payload
        else:
            payloads[mid] = packer.pack_single_stream_index(-1, config.MODULE_CELLS)

    state.grid = grid
    state.module_payloads = payloads
    state.probe_tile_index = tile_index
    state.jpeg = b""


def probe_loop() -> None:
    while state.running:
        time.sleep(0.05)
        with state.lock:
            if not state.probe_enabled or not state.probe_auto:
                continue
            now = time.monotonic()
            if now - state.probe_last_advance < state.probe_interval_s:
                continue
            state.probe_index = (state.probe_index + 1) % _probe_total_steps()
            state.probe_last_advance = now
            _apply_probe()


def capture_loop(index, fps: float, warmup_s: int) -> None:
    cap = camera.open_camera(index)
    camera.warmup(cap)

    if warmup_s > 0:
        print(f"Capturing background in {warmup_s}s — keep scene clear...")
        deadline = time.monotonic() + warmup_s
        while state.running and time.monotonic() < deadline:
            time.sleep(min(0.1, deadline - time.monotonic()))
        if not state.running:
            camera.release(cap)
            return
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
        probe_active = False
        capture_requested = False

        with state.lock:
            if state.probe_enabled:
                probe_active = True
            else:
                probe_active = False
                settings = _copy_settings(state.settings)
                preview_mode = state.preview_mode
                background = state.background
                if state.capture_background_requested:
                    state.capture_background_requested = False
                    capture_requested = True
                else:
                    capture_requested = False

        if probe_active:
            time.sleep(0.05)
            continue

        if capture_requested:
            try:
                background = capture_background(cap, settings)
                with state.lock:
                    state.background = background
                print("Background frame captured")
            except RuntimeError as exc:
                print(f"Background capture failed: {exc}")
                with state.lock:
                    background = state.background

        frame = camera.read_frame(cap)
        if frame is None:
            time.sleep(0.05)
            continue

        grid, mask, grey, diff_raw = process_frame(frame, settings, background=background)
        payloads = modules.build_module_payloads(grid)

        jpeg = b""
        if preview_mode != "off":
            preview_img = build_preview(
                mask, grey, diff_raw, background,
                mode=preview_mode,
                threshold=settings.bg_diff_threshold,
            )
            preview_size = (config.DEBUG_PREVIEW_WIDTH, config.DEBUG_PREVIEW_HEIGHT)
            preview_resized = cv2.resize(preview_img, preview_size)
            ok, encoded = cv2.imencode(
                ".jpg",
                preview_resized,
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
            if preview_mode != "off" and jpeg:
                state.jpeg = jpeg
                state.frame_seq += 1
            elif preview_mode == "off":
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
                    "matrix_rows": config.INSTALL_ROWS,
                    "matrix_cols": config.INSTALL_COLS,
                    "tile_rows": config.TILE_ROWS,
                    "tile_cols": config.TILE_COLS,
                    "module_tiles_x": config.MODULE_TILES_X,
                    "module_tiles_y": config.MODULE_TILES_Y,
                    "tile_mirror_x": config.TILE_MIRROR_X,
                    "module_rows": config.MODULE_ROWS,
                    "module_cols": config.MODULE_COLS,
                    "install_modules_x": config.INSTALL_MODULES_X,
                    "install_modules_y": config.INSTALL_MODULES_Y,
                    "module_count": config.MODULE_COUNT,
                    "bytes_per_module": config.BYTES_PER_MODULE,
                    "process_width": config.PROCESS_WIDTH,
                    "process_height": config.PROCESS_HEIGHT,
                    "cell_aspect_w": config.CELL_ASPECT_W,
                    "cell_aspect_h": config.CELL_ASPECT_H,
                    "module_cells": config.MODULE_CELLS,
                }
            )

        if path == "/api/state":
            with state.lock:
                payload = {
                    "grid": state.grid.astype(int).tolist(),
                    "fps": state.fps,
                    "bg_threshold": state.settings.bg_diff_threshold,
                    "invert": state.settings.invert,
                    "preview_mode": state.preview_mode,
                    "show_processed": state.preview_mode != "off",  # legacy compat
                    "has_background": state.background is not None,
                    "probe_enabled": state.probe_enabled,
                    "probe_auto": state.probe_auto,
                    "probe_mode": state.probe_mode,
                    "probe_module_id": state.probe_module_id,
                    "probe_index": state.probe_index,
                    "probe_max": _probe_total_steps() - 1,
                    "probe_tile": state.probe_tile_index,
                    "probe_module": state.probe_module_id,
                    "module_count": config.MODULE_COUNT,
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
                        "bytes_per_module": config.BYTES_PER_MODULE,
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
                if "preview_mode" in data:
                    mode = str(data["preview_mode"])
                    if mode in ("off", "mask", "diff", "raw", "background"):
                        state.preview_mode = mode
                        if mode == "off":
                            state.jpeg = b""
                elif "show_processed" in data:
                    # legacy boolean fallback
                    state.preview_mode = "mask" if bool(data["show_processed"]) else "off"
                    if state.preview_mode == "off":
                        state.jpeg = b""

            return self._send_json({"ok": True})

        if path == "/api/background/capture":
            with state.lock:
                if state.probe_enabled:
                    return self._send_json({"ok": False, "error": "probe active"}, HTTPStatus.CONFLICT)
                state.capture_background_requested = True
            return self._send_json({"ok": True})

        if path == "/api/probe":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError:
                return self.send_error(HTTPStatus.BAD_REQUEST)

            with state.lock:
                if "enabled" in data:
                    state.probe_enabled = bool(data["enabled"])
                    if state.probe_enabled:
                        state.preview_mode = "off"
                        state.jpeg = b""
                        state.probe_last_advance = time.monotonic()
                        _apply_probe()
                    else:
                        state.probe_auto = False
                        state.grid = np.zeros(
                            (config.INSTALL_ROWS, config.INSTALL_COLS), dtype=np.uint8
                        )
                        state.module_payloads = {
                            module_id: packer.pack_single_stream_index(-1, config.MODULE_CELLS)
                            for module_id in range(config.MODULE_COUNT)
                        }

                if "auto" in data:
                    state.probe_auto = bool(data["auto"])
                    state.probe_last_advance = time.monotonic()

                if "mode" in data and data["mode"] in ("cell", "row", "col"):
                    if data["mode"] != state.probe_mode:
                        state.probe_mode = data["mode"]
                        state.probe_index = 0

                if "module_id" in data:
                    module_id = int(data["module_id"]) % max(config.MODULE_COUNT, 1)
                    if module_id != state.probe_module_id:
                        state.probe_module_id = module_id

                if state.probe_enabled:
                    total_steps = _probe_total_steps()
                    if data.get("step") == "next":
                        state.probe_index = (state.probe_index + 1) % total_steps
                    elif data.get("step") == "prev":
                        state.probe_index = (state.probe_index - 1) % total_steps
                    elif "index" in data:
                        state.probe_index = int(data["index"]) % total_steps
                    state.probe_last_advance = time.monotonic()
                    _apply_probe()

                payload = {
                    "ok": True,
                    "probe_enabled": state.probe_enabled,
                    "probe_auto": state.probe_auto,
                    "probe_mode": state.probe_mode,
                    "probe_module_id": state.probe_module_id,
                    "probe_index": state.probe_index,
                    "probe_max": _probe_total_steps() - 1,
                    "probe_tile": state.probe_tile_index,
                }
            return self._send_json(payload)

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
            while state.running:
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
        except (BrokenPipeError, ConnectionResetError, OSError):
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

    probe_thread = threading.Thread(target=probe_loop, daemon=True)
    probe_thread.start()

    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    stopping = False

    def handle_signal(_signum, _frame) -> None:
        nonlocal stopping
        if stopping:
            print("\nForce exit.")
            os._exit(1)
        stopping = True
        print("\nStopping...")
        state.running = False
        # shutdown() must run off the main thread — serve_forever() blocks there.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    ip = local_ip()
    print(f"Running at http://{ip}:{args.port}")
    print(f"Target FPS: {args.fps}")
    print(f"Debugger UI: http://{ip}:{args.port}/")
    print(f"Install grid: {config.INSTALL_COLS}×{config.INSTALL_ROWS}  "
          f"({config.MODULE_COUNT} module(s), {config.BYTES_PER_MODULE} bytes each)")
    print(f"Process crop: {config.PROCESS_WIDTH}×{config.PROCESS_HEIGHT}  "
          f"(portrait cells {config.CELL_ASPECT_W}:{config.CELL_ASPECT_H})")
    print(f"ESP32 poll:  GET /api/module/{{id}}  (0–{config.MODULE_COUNT - 1})")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    finally:
        state.running = False
        server.shutdown()
        server.server_close()
        capture_thread.join(timeout=3)
        probe_thread.join(timeout=1)
        print("Stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
