# Plan

Roadmap for scaling the camera processor from proof of concept to the full install. ESP32 grid dimensions must match the Pi (see `display-controller/config.example.h`).

### Vocabulary

| Term | Meaning |
|------|---------|
| **Tile** | One **8×16** slice of the camera mask (128 cells, **16 bytes** packed) |
| **Module** | One physical panel, **one ESP32** — **current test: 2×1 tiles** (**8×32** cells, **32 bytes**); **full PCB target: 4×1** (**8×64**, **64 bytes**) |
| **Install** | How many modules and how they are arranged (side by side, stacked, etc.) |

One module on the display (current 2-tile test; full row is 4 tiles):

```text
    tile 1  │  tile 0
                     ↑ chain start (module 0)

    → one payload (32 bytes) → one ESP32
```


<details>
<summary>Phase 1 — One tile, one ESP32 **(Complete)**</summary>

Adapting the code from the browser / p5.js proof of concept into a Pi-based product:

- Background subtraction pipeline (`main.py`, `process.py`)
- Packed binary output for ESP32 (`packer.py`, `frame_output.py`)
- Browser debugger on the Pi (`debugger.py`, `debugger_static/`)
- USB webcam via OpenCV/V4L2
- Single **8×16** tile (matches current ESP32 prototype)
- HTTP server on the Pi — ESP32 polls `GET /api/module/{id}` (`server.py`)

</details>

<details>
<summary>Phase 2 — One module, two tiles **(Complete)**</summary>

- Pi treats the scene as **2×1 tiles** (**8×32** logical grid per module)
- Split mask → two tile regions → combine into **one module payload** (**32 bytes**)
- **One ESP32** pulls its message from the Pi API by **module ID** (`GET /api/module/0`)
- ESP32 constants scale to the module grid (**8 rows × 32 cols**) — same bit-packing logic, larger buffer than Phase 1
- **`TILE_MIRROR_X = True`** on Pi and ESP32 — chain tile 0 is the **rightmost** column (matches PCB wiring)
- Full **4×1** row on one module is the next hardware step on the same PCB — bump `MODULE_TILES_X` to **4** → **64 bytes**, same pipeline

```text
Module 0 (ESP32 #0)

       ┌─> chain start
┌─────┬─────┐
│ t1  │ t0  │
└─────┴─────┘
```

Config signposts (conceptual):

```python
TILE_ROWS = 8
TILE_COLS = 16
MODULE_TILES_X = 2
MODULE_TILES_Y = 1
INSTALL_MODULES_X = 1
INSTALL_MODULES_Y = 1
```

</details>

<details>
<summary>Phase 3 — Second module, one row **(Complete)**</summary>

- Add a **second module** beside the first — same processing code, second ESP32 (`GET /api/module/1`)
- **4 tiles** total (**2 per module**), **2 ESP32s**, install grid **8×64**

```text
       ┌─> chain start  
┌─────┬─────┐ ┌─────┬─────┐
│ t1  │ t0  │ │ t1  │ t0  │
└─────┴─────┘ └─────┴─────┘
| Module #0 | | Module #1 |

```

Phase 3 config example:

```python
MODULE_TILES_X = 2
MODULE_TILES_Y = 1
INSTALL_MODULES_X = 2
INSTALL_MODULES_Y = 1
```

Each board needs its own **`MODULE_ID`** (`0` and `1`) in `display-controller/config.h`.

</details>

<details>
<summary>Phase 4 — More rows</summary>

- Stack **additional modules below** — same processing code, one ESP32 per module
- Target: **6 rows × 2 modules** → **24 tiles**, **12 ESP32s** (`MODULE_ID` **0–11**)

```text
       ┌─> chain start  
┌─────┬─────┐ ┌─────┬─────┐
│ t1  │ t0  │ │ t1  │ t0  │
└─────┴─────┘ └─────┴─────┘
 Module #0     Module #1

┌─────┬─────┐ ┌─────┬─────┐
│ t1  │ t0  │ │ t1  │ t0  │
└─────┴─────┘ └─────┴─────┘
 Module #2     Module #3

┌─────┬─────┐ ┌─────┬─────┐
│ t1  │ t0  │ │ t1  │ t0  │
└─────┴─────┘ └─────┴─────┘
 Module #4     Module #5

┌─────┬─────┐ ┌─────┬─────┐
│ t1  │ t0  │ │ t1  │ t0  │
└─────┴─────┘ └─────┴─────┘
 Module #6     Module #7

┌─────┬─────┐ ┌─────┬─────┐
│ t1  │ t0  │ │ t1  │ t0  │
└─────┴─────┘ └─────┴─────┘
 Module #8     Module #9

┌─────┬─────┐ ┌─────┬─────┐
│ t1  │ t0  │ │ t1  │ t0  │
└─────┴─────┘ └─────┴─────┘
 Module #10    Module #11
```

Phase 4 config example (2 modules wide × 6 rows):

```python
MODULE_TILES_X = 2
MODULE_TILES_Y = 1
INSTALL_MODULES_X = 2
INSTALL_MODULES_Y = 6
```

Install grid: **48×64** cells (8 rows per module × 6 module-rows; 32 cols per module × 2 modules wide).

</details>

<details>
<summary>Later — more modules **(to review)**</summary>

Scale by changing install layout only — no new processing pipeline:

- One camera → one mask → split into tiles per module → pack per module → API by module ID
- Example: `INSTALL_MODULES_X = 2`, `INSTALL_MODULES_Y = 2` → four modules, four ESP32s
- **User detection** — idle when no one is present, active when someone steps in. No debugger or manual background capture in the live install. Options to explore (same mask → grid → pack pipeline; only the mask source changes):

- **ML person segmentation** (ML5-style — e.g. MediaPipe selfie segmentation, TFLite BodyPix-class models; target **Pi 5**) — no stored background; empty room = idle naturally
- **Presence gate** — keep current background subtraction; blank the grid unless enough mask cells / contour area exceed a threshold
- **Adaptive background** — OpenCV `BackgroundSubtractorMOG2` / KNN; learns the empty scene over time, no fixed snapshot
- **Auto-recapture when idle** — refresh the background snapshot after N seconds with no significant motion
- **Motion trigger** — frame differencing only; idle until movement, then show disturbance (lo-fi, no background model)

Pi 5 is sufficient for this; the work is mostly config, crop/split math, and the module API.

</details>

<br>
<br>

# Raspberry Pi

The Pi runs the **camera processor** — it captures webcam input, applies background subtraction, and prepares binary frames for the ESP32 display controller. This section holds everything needed to **install, deploy, and maintain** that setup on the device.

**Pi 5** (primary — dev and install)
- home `luizamorim@192.168.1.234`
- opal `luizamorim@192.168.8.107`
- hostname: `pi5`

**Pi Zero 2W** (spare)
- home `luizamorim@192.168.1.157`
- opal `luizamorim@192.168.8.117`
- hostname: `pizero`

(Opal IPs are DHCP — check the router client list or `hostname -I` on the Pi if SSH fails.)

**Code on Mac:** `Code/camera-processor/` — copy to the Pi from the Mac terminal, not from inside an SSH session.

| Step        | Command / check                                             |
|------------|--------------------------------------------------------------|
| Copy code  | `rsync` or `scp` **from Mac**                                |
| Deps       | `sudo apt install python3-opencv python3-numpy v4l-utils`    |
| USB camera | `lsusb` shows camera device                                  |
| Video dev  | `v4l2-ctl --list-devices` → note `/dev/video*` for webcam    |
| Run (dev)  | `python3 debugger.py --index /dev/video0` → browser `:8080` |
| Run (install) | `python3 main.py --index /dev/video0`                    |

<details>
<summary>Install Instructions</summary>

## 1. Copy the code to the Pi

Run these on my **Mac terminal** (not inside the Pi SSH session).

### Option A — rsync (recommended)

Syncs only `camera-processor/` — `_context/` lives at the repo root and stays on the Mac:

```bash
rsync -av \
  "/Users/luizamorim/Library/Mobile Documents/com~apple~CloudDocs/Goldsmiths/Projects/_Final Project/Code/camera-processor/" \
  luizamorim@192.168.8.107:~/camera-processor/
```

Note: destination is `luizamorim@192.168.8.107:~/camera-processor/` — no extra characters before the colon.

### Option B — scp

```bash
scp -r \
  "/Users/luizamorim/Library/Mobile Documents/com~apple~CloudDocs/Goldsmiths/Projects/_Final Project/Code/camera-processor" \
  luizamorim@192.168.8.107:~/
```

Same scope as rsync — only the `camera-processor/` folder, not repo-root `_context/`.

### Verify on the Pi

```bash
ssh luizamorim@192.168.8.107
ls ~/camera-processor
```

Should see `main.py`, `camera.py`, `config.py`, `debugger.py`, etc.

---

## 2. Install dependencies on the Pi

SSH into the Pi, then:

```bash
sudo apt update
sudo apt install -y python3-opencv python3-numpy v4l-utils
```

Verify:

```bash
python3 -c "import cv2, numpy; print('OK')"
```

The code uses a **USB webcam** via OpenCV/V4L2 — not Picamera2.

---

## 3. Plug in hardware and check devices

**Pi 5:** plug the USB webcam into any USB port.

**Pi Zero 2W** (spare — needs OTG on the data port):

```text
[ PWR port ]  ← dedicated power adapter for the Pi
[ USB port ]  ← OTG/data port → OTG adapter → USB hub → webcam
```

Confirm the Pi sees the webcam:

```bash
lsusb
```

Success looks like a second (or third) device line, e.g. `ARC International Camera`. If only the root hub appears, the camera isn't detected.

Find which `/dev/video*` belongs to the webcam (not Pi internal codec nodes):

```bash
sudo apt install -y v4l-utils
v4l2-ctl --list-devices
```

Note the path under the camera name (e.g. `/dev/video0`). Use this path in the steps below.

---

## 4. Production loop (install)

For the live install, run headless — no browser tuning. Set threshold, invert, and morphology in `config.py` or via the flags below.

```bash
cd ~/camera-processor
python3 main.py --index /dev/video0 --morphology
```

Headless-only flags (the **debugger** UI covers threshold and invert live — see §5):

```bash
# Starting threshold before locking config (higher = less sensitive)
python3 main.py --index /dev/video0 --bg-threshold 30

# Invert detection if silhouette is backwards
python3 main.py --index /dev/video0 --invert

# Pi 5 default is ~25 FPS (config.TARGET_FPS). Lower only if the Pi struggles:
python3 main.py --index /dev/video0 --fps 5

# Morphology is off at startup unless you pass this flag (even though config.py defaults to on)
python3 main.py --index /dev/video0 --morphology
```

---

## 5. Debugger (development)

Web UI on the Pi for tuning from a Mac or phone browser. **`debugger.py` and `main.py` run the same server** — use `debugger.py` while developing.

- **Threshold** slider and **Invert** — no CLI flags needed
- **Capture background** — empty scene first, then step in for a silhouette
- **Preview** — cycles mask / diff / raw / background (overlay matched to grid aspect)
- **Wiring probe** — step through **cell**, **row**, or **col** on any module; pick module ID when multiple ESP32s are connected; manual prev/next or auto-advance

```bash
cd ~/camera-processor
python3 debugger.py --index /dev/video0
```

In the browser (use the Pi IP on your network — Opal example):

`http://192.168.8.107:8080`

For the installation, run `main.py` headless instead (§4).

---

## 6. Run automatically on boot (optional)

Once everything works manually:

1. Create `/etc/systemd/system/camera-processor.service`
2. Set `ExecStart` to `/usr/bin/python3 /home/luizamorim/camera-processor/main.py --index /dev/video0 --morphology`
3. Enable and start:

```bash
sudo systemctl enable --now camera-processor
```

</details>

<br>
<br>

# ESP32

The **display controller** firmware lives in `display-controller/` at the repo root — build and flash from the Mac (PlatformIO), not from the Pi. Each module gets one ESP32; grid dimensions must match `camera-processor/config.py`.

| Step       | Command / check                                              |
|-----------|--------------------------------------------------------------|
| Config    | Copy `config.example.h` → `config.h` (gitignored)            |
| Layout    | `MODULE_TILES_X/Y` match Pi; set `MODULE_ID` per board       |
| SPI       | `SPI_CLOCK_HZ` in `config.h` — lower (e.g. `250000`) if digits drop out on longer chains |
| Network   | `WIFI_SSID`, `WIFI_PASS`, `PI_HOST` (Pi IP on same WiFi)    |
| Build     | Open `display-controller/` in Cursor with PlatformIO         |
| Flash     | Upload via PlatformIO (USB to ESP32)                         |
| Verify    | Serial monitor @ 115200 — WiFi connect, row test, polling    |

<details>
<summary>Install Instructions</summary>

## 1. Create config.h

From the `display-controller/` folder:

```bash
cp config.example.h config.h
```

Edit `config.h`:

- **WiFi** — `WIFI_SSID`, `WIFI_PASS`
- **Pi address** — `PI_HOST` (e.g. `192.168.8.107` on Opal), `PI_PORT` (default `8080`)
- **Module identity** — `MODULE_ID` unique per board when `INSTALL_MODULES_X` or `INSTALL_MODULES_Y` > 1 (e.g. `0` and `1` for Phase 3)
- **Tile layout** — `MODULE_TILES_X`, `MODULE_TILES_Y`, `TILE_MIRROR_X` must match `camera-processor/config.py`
- **SPI clock** — `SPI_CLOCK_HZ` (default `500000`); reduce if the daisy chain loses digits as you add tiles or modules

`config.h` is gitignored — credentials stay local.

---

## 2. Build and flash (PlatformIO)

Open **`display-controller/`** as the project root in Cursor (see `platformio.ini`).

- **Build** — PlatformIO build task
- **Upload** — connect ESP32 via USB, then PlatformIO upload
- **Monitor** — Serial @ `115200` to confirm WiFi and frame polling

On boot the board runs a row test (`RUN_ROW_TEST_ON_BOOT`), then polls `GET http://{PI_HOST}:{PI_PORT}/api/module/{MODULE_ID}` every ~120 ms. HTTP connections are opened fresh each poll — the Pi serves HTTP/1.0 and closes the socket after every response. WiFi TX power is set to maximum in firmware to reduce packet loss from RF noise near the SPI/LED chain.

---

## 3. Sync with the Pi

Before relying on the display:

1. Pi is running `main.py` (see Raspberry Pi section above)
2. `MODULE_TILES_X/Y`, `TILE_MIRROR_X`, payload size, and **`MODULE_ID` per board** match on both sides
3. ESP32 and Pi are on the **same WiFi network**
4. Quick check from any machine on the LAN:

```bash
curl -s "http://192.168.8.107:8080/api/health"
curl -s "http://192.168.8.107:8080/api/module/0" | xxd | head
```

Replace the IP with your Pi address. Expected byte count must match `BYTES_PER_MODULE` in both `config.h` and Pi `config.py`.

</details>

<br>
<br>



# Journal

Informal log of what happened as the project moved forward — meetings, decisions, hardware mistakes, code experiments, that kind of thing. I'm capturing these entries here to help me formulate my ideas for the writing report later, so when I sit down to write I don't have to reconstruct everything from memory.

<details>
<summary>2026-07-01 — missing digits, WiFi interference, two tiles per ESP32</summary>

- digging into the **ESP32 side** — one module working, planning five more rows, but **digits going missing** on the physical display, worst on the **last tile in the row**
- ruled out **wiring and power** first — already had a redundant 5V line across the boards
- the **signal speed** was too fast for how long the tile chain had gotten — dropped from 1 MHz to **500 kHz**, then **250 kHz** when the last tile was still dropping digits; better each time, but not perfect
- new symptoms: occasional **freezes**, and sometimes the whole panel would **flash fully on** for a frame then go dark
- used **Claude Code heavily** to debug — added temporary logging on **Pi and ESP32**, ruled out a **memory leak** (heap stayed steady)
- found the ESP32 was **reusing its network connection** in a way the Pi server didn't support — fixed by opening a **fresh connection** each time
- freeze still happening — **ping test** showed the Pi rock solid, the **ESP32 dropping packets**
- fixed the **WiFi channel** on the router (was on auto) — helped general stability but not the ESP-specific problem
- theory: the ESP32 sits right next to the **fast-switching LED wiring**, interfering with its own WiFi — **tin foil shield + grounding** helped a lot; also **boosted WiFi transmit power** in software
- hit a real limit with **4 tiles on one ESP32** — chain too long, too much interference to fully solve — **decided to scale down to 2 tiles per ESP32** going forward instead of chasing it further
- wired up a **second ESP32** for the next pair of tiles — looked broken at first, but it was just a **Pi settings file** that hadn't been updated; fixed once re-copied
- once stable, **cleaned out the debug logging**, bumped signal speed back to **500 kHz** on the shorter chains, and fixed the **boot test** so each board clearly shows **module + tile ID** across the whole tile
- improved the **wiring-test tool** in the debugger — clearer readout, faster auto-scan, whole rows/columns, works for the **second board** too
- fixed a small bug where clicking through **camera preview views** too fast could freeze the debugger tab — didn't affect the mirror, just the tuning tool

</details>

<details>
<summary>2026-06-30 — display stability, debugger, fourth tile</summary>

- displays were **laggy and unreliable** — pushing for max speed made them **freeze**; rewrote the ESP32 to refresh **row by row**, stepped back for **stability**, reset each frame so stuck-bright tiles recover — **much better now**
- used **AI heavily** (Sonnet 4.6, Cursor) to work through the frame-rate and processing side of that
- after adding the **4th tile in a row**, checked the whole setup — debugger and physical panels still didn't quite match, especially when I **stood still**; more **AI-assisted** tweaks on the ESP32
- **ESP32**: WiFi stays awake, reuses its connection to the Pi, displays **reset periodically** so they don't stay stuck until reboot
- turned **brightness down to 1** — helped; learned the **debugger refresh rate** and **ESP32 polling** don't need to be the same number — different jobs
- **debugger**: cleaned up **look and feel**, added options to inspect **camera rendering / thresholding**
- matched the **camera preview to the grid** — threshold, mask, diff views were still the old wide shape and didn't line up with the boxes on screen

</details>

<details>
<summary>2026-06-29 — second tile, fixing the display mapping</summary>

- wired up a **second tile** side by side with the first — two tiles on one module now
- adding a tile meant changing the code — the display was stretching into extra **rows** instead of staying **8 rows wide**
- changed the **boot test** so each tile shows its own ID (**00**, **01**) instead of the old 0–9 / A–F pattern
- both tiles were showing a **muddy mix** of patterns — figured out the wiring runs **tile by tile**, but the code was reading it as **one long row**
- fixed the **ESP32** first; boot test looked right on the hardware
- the **live camera feed** was still wrong — fixed the **Pi** and **debugger** to send data in the same order as the physical chain
- **camera → display working really well** now; scaling up should mostly be a config change when I add more tiles

</details>

<details>
<summary>2026-06-25 — Pi 5 setup, mobile debugger</summary>

- got the **Pi 5 4GB** — install machine going forward; **Zero 2W** stays as spare
- set it up on the **Opal travel router** (same WiFi faff as before, but quicker second time around); updated **readme** and **ESP32** to point at the Pi 5
- camera and **debugger** running on the Pi 5, **FPS** tuned — feels good on the new hardware
- refactored the **debugger** so I can open it from my **phone**
- fixed **Ctrl+C** — it actually stops the server now instead of hanging
- running the whole thing from my phone with **Termius** — SSH in, start the debugger, tune from the browser on mobile

</details>

<details>
<summary>2026-06-24 — blueprint, field test, exhibit prep</summary>

- drew up the **blueprint** for the install — wiring, connections, power supply, and how the pieces fit together; a lot of this is going straight into the **tech form**
- took the setup **away from home** and ran it on the **Opal portable network** — worked well, reassuring for the live exhibit
- went through **health & safety** with the **tech team**
- looked at **parts for the frame and support** — figuring out what I can use to hold the mirror

</details>

<details>
<summary>2026-06-23 — portable router for the live exhibit</summary>

- moved the **Pi and ESP32 off home WiFi** onto a dedicated router so the install can run on its own at the exhibit
- first tried an **iPhone hotspot** — the Pi wouldn't connect, so I bought and set up a **GL.iNet travel router** instead
- the Pi's built-in WiFi setup tool (**raspi-config**) kept erroring; had to configure WiFi a different way on the current Pi OS
- lots of faff getting the Pi to see and join the new network — router had to be on and in range before the saved profile would show up
- when the Pi switched networks my **SSH session dropped**, and I briefly tried connecting to the **router** thinking it was the Pi
- my Mac was on a **different WiFi band** than the Pi and ESP32, which made debugging slower and more confusing
- had to turn off a **client isolation** setting on the router — otherwise the Pi and ESP32 couldn't talk to each other even when everything looked connected
- updated the **ESP32 WiFi settings** to match the new network; **end-to-end working** in the end — camera, Pi, display

</details>

<details>
<summary>2026-06-21 — tile/module config refactor, Phase 3 prep</summary>

- refactored the Pi pipeline around a proper **tile → module → install** layout in **`config.py`** — `TILE_ROWS/COLS`, `MODULE_TILES_X/Y`, `INSTALL_MODULES_X/Y`, with **`recompute_layout()`** deriving grid size, byte count, and module count
- **`modules.py`** now splits the full install mask into per-module regions by ID — ready for **Phase 3** (second module below) without rewriting the processing loop
- made **`packer.py`** size-agnostic so it packs any grid shape; **`frame_output.py`** validates module-sized payloads
- **`process.py`** resizes to the full install grid; debugger overlay follows actual grid dimensions
- **`server.py`** exposes the layout knobs on **`/api/config`** and clearer startup logging for ESP32 polling
- aligned **`display-controller/config.example.h`** with the same vocabulary — notes for stepping through **2×1 / 1×2** tile wiring before the full **2×2** module
- fixed **rsync/scp paths** in the readme (was still pointing at the old Proposal folder)
- still running **1×1 tile / 1 module** in config for now — next step is wiring up more tiles on the PCB and bumping the knobs to match

</details>

<details>
<summary>2026-06-20 — displays arrived, PCB solder + tile tests</summary>

- received **65 displays** and soldered them into the PCB
- tested each one individually as a **single tile** — all good, happy with the results
- hardware side of **Phase 2** feels real now: one tile working on the board matches where the code already is
- ordered **700+ displays** for assembling the final tiles

</details>

<details>
<summary>2026-06-19 — readme restructure + ESP32 pipeline</summary>

- reorganised **readme.md** — Plan first, collapsible Pi deploy sections, updated rsync notes for repo-root `_context/`
- built Pi **HTTP API** (`GET /api/module/{id}`) serving raw **16-byte** frames for Phase 1 (one 8×16 tile); tested with `curl | xxd` before touching the ESP32
- created **`display-controller/`** at repo root — promoted firmware from `_context`, split into **`api_client`**, **`display_renderer`**, and a thin `.ino` glue file
- ESP32 **polls WiFi** (~100 ms) instead of Serial — same **MSB-first `processMessage()`** bit packing as the Pi (`packer.py`)
- **config-driven** tile/module dimensions in `config.h` — Phase 2 is just `MODULE_TILES_X/Y = 2` (64 bytes, 32×16 grid); each board only needs its **`MODULE_ID`**
- kept **`FIX_REVERSED_LAST_TWO_ROWS`** workaround from the old firmware for the faulty display PCB
- set up **PlatformIO / PioArduino** in Cursor (`platformio.ini`) so I can build and flash without moving files into `src/`
- **`config.h`** gitignored for WiFi credentials; `config.example.h` committed as the template
- **end-to-end working** — camera on Pi, debugger in browser, ESP32 driving the matrix from the API
- Pi Zero **froze under load** once; after a hard kill `/dev/video0` vanished — reboot, find the webcam with `v4l2-ctl`, run with `--fps 5`
- Moved to **Phase 2**

</details>

<details>
<summary>2026-06-16 — server / API launch attempt</summary>

- had a quick go during the day at getting a **server** running and launching the **API** so the ESP32 can pull frames from the Pi — didn't get it working
- left it there for now; planning to keep trying over the rest of the week

</details>

<details>
<summary>2026-06-11 — debugger UI, scaling plan, Pi 5</summary>

- spent a session tightening the **debugger static site** (`debugger_static/`) — cleaned unused CSS, merged the processed view and matrix grid into one layered panel, added a **Processed view** toggle (off by default so the Pi skips JPEG encode when I'm only tuning the grid)
- fixed the **difference threshold** slider — it was snapping back because the UI polled server state faster than it saved changes
- fixed **FPS** reporting so the status bar matches what you see (no duplicate MJPEG frames); still around **8.5 FPS** on the Pi Zero 2W — enough for tuning, not the install target
- looked at **Pi 5 2 GB** for the real install — RAM is fine for this job; the Zero is the bottleneck, not the payload size
- mapped out how **ESP32 modules** will work: one **module** = 2×2 tiles (8×16 each), **one ESP32** per module, API by module ID; wrote this up as a **Plan** section in the readme (Phase 1 = product in progress now, Phase 2 = one module, Phase 3 = second module below)
- fixed a **404 on the MJPEG stream** when the browser added a cache-busting query string to `/api/stream`

</details>

<details>
<summary>2026-06-10 — 7-segment displays (wrong type) + Pi prototype</summary>

- got the pack with the 7-segment displays today
- soldered them up, then realised I was supposed to use **common cathode** but I'd bought **common anode**… which basically short circuits the board.
- made a new order for the right ones — waiting a few more days now
- decided to prototype the code on my **Raspberry Pi Zero 2W** in the meantime, as a potential device for the install
- used the old [camera processor repo](https://github.com/luiz-flamorim/7-digit-display-and-camera) as a starting point and tried to match the thresholding behaviour in python
- didn't really like the result — felt too crude / not what I wanted visually
- used AI to explore the **background snapshot** approach instead — much happier with that
- also used AI to help me spin up a **python debugger server** so I can tune things from the browser without rebuilding every time
- used the AI to help me organise the readme.md

</details>

<details>
<summary>2026-05-31 — ordered PCB boards + parts</summary>

- placed the request for the PCB boards and other electronic parts

</details>

<details>
<summary>2026-05-28 — supplier chat + project direction sessions</summary>

- spoke to Rober Hall about a possible supplier for the PCB board — he agreed with my initial thought that sending to china would be much more cost effective, and faster
- had a 1:1 with Rebecca Aston to talk about possible projects — got the impression the **digital mirror** was much more in line, and I started adding the concept of **Ophelia**
- had a 1:1 with Rachel Falconer (supervisor) — we also agreed the digital mirror was much more robust to use

</details>

<details>
<summary>2026-05-22 — proposal draft in Germany</summary>

- on my trip to Germany, used the time off to put together my real proposal around using the digital mirror as a metaphor / critique view
- The project originated from Digit Mirror, a physical computing experiment that reconstructed the body using low-resolution 7-segment displays. Initially, my interest was focused on the technical challenge of translating camera data into a simplified visual representation.
- As the project evolved, my attention shifted away from the mirror itself and towards the relationship between humans and computational systems. The work became less about reflection and more about interpretation.
- I am increasingly interested in how contemporary society adapts itself to technological systems. Social media, algorithms, recommendation engines, and digital platforms continuously shape how people present themselves, behave, and seek visibility.
The project questions whether we are designing systems around human complexity, or whether humans are simplifying themselves in order to remain visible and legible within computational systems.
- Jean Baudrillard's concept of simulation became relevant to the work. The mirror does not show reality; it shows a reconstruction. The audience recognises themselves within a representation generated by a machine, despite that representation being incomplete and heavily reduced.
- The title Dig Ophelia emerged later in the development process. "Dig" refers both to digital systems and to the act of excavation. The work can therefore be understood as an excavation of contemporary computational perception.
- Ophelia became an important metaphor. In Hamlet, she dissolves into the river and disappears beneath the surface. In Dig Ophelia, the audience similarly dissolves into computational processes, transformed into data, segmentation, and abstraction.
- Rather than reflecting the audience faithfully, the installation demonstrates how a machine sees them. The work is not asking whether this representation is accurate, but why people are increasingly willing to recognise themselves through machinic representations.
- I am not interested in producing a dystopian critique of technology. The project acknowledges that people may experience the work in different ways: as a playful mirror, a technological curiosity, a ghostly presence, or a reflection on contemporary computational culture.
- The project ultimately explores a tension between visibility and reduction. To become visible within computational systems, something must first become simplified, categorised, measured, and transformed into data.

</details>

