# Plan

Roadmap for scaling the camera processor from proof of concept to the full install. ESP32 grid dimensions must match the Pi (see `display-controller/config.example.h`).

### Vocabulary

| Term | Meaning |
|------|---------|
| **Tile** | One **8×16** slice of the camera mask (128 cells, **16 bytes** packed) |
| **Module** | **2×2 tiles** = one physical panel, **one ESP32** (**64 bytes** per frame) |
| **Install** | How many modules and how they are arranged (side by side, stacked, etc.) |

One module on the display:

```text
        tile 0  │ tile 1
        ────────┼────────
        tile 2  │ tile 3

        → one payload (64 bytes) → one ESP32
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
<summary>Phase 2 — One module, one ESP32 **(In progress)**</summary>

- Pi treats the scene as **2×2 tiles** (32×16 logical grid)
- Split mask → four tile regions → combine into **one module payload** (64 bytes)
- **One ESP32** pulls its message from the Pi API by **module ID** (e.g. `GET /api/module/0`)
- ESP32 constants scale to the full module (e.g. 16 rows × 32 cols) — same `processMessage()` logic, larger buffer
- Optional **2-tile test** before full 2×2 — set `MODULE_TILES_X/Y` to **2×1** (side by side) or **1×2** (stacked) on Pi and ESP32 → **32 bytes**, same pipeline

```text
Module 0 (ESP32 #0)

┌─────┬─────┐
│ t0  │ t1  │
├─────┼─────┤
│ t2  │ t3  │
└─────┴─────┘
```

Config signposts (conceptual):

```python
TILE_ROWS = 8
TILE_COLS = 16
MODULE_TILES_X = 2
MODULE_TILES_Y = 2
INSTALL_MODULES_X = 1
INSTALL_MODULES_Y = 1
```

</details>

<details>
<summary>Phase 3 — Second module below</summary>

- Add a **second module** under the first — same processing code, second ESP32 (`module/1`)
- **8 tiles** total, **2 ESP32s**

```text
Module 0 (ESP32 #0)     Module 1 (ESP32 #1)

┌─────┬─────┐           ┌─────┬─────┐
│ t0  │ t1  │           │ t0  │ t1  │
├─────┼─────┤           ├─────┼─────┤
│ t2  │ t3  │           │ t2  │ t3  │
└─────┴─────┘           └─────┴─────┘
```

Phase 3 config example:

```python
INSTALL_MODULES_X = 1
INSTALL_MODULES_Y = 2
```

**User detection** — idle when no one is present, active when someone steps in. No debugger or manual background capture in the live install. Options to explore (same mask → grid → pack pipeline; only the mask source changes):

- **ML person segmentation** (ML5-style — e.g. MediaPipe selfie segmentation, TFLite BodyPix-class models; target **Pi 5 8 GB**) — no stored background; empty room = idle naturally
- **Presence gate** — keep current background subtraction; blank the grid unless enough mask cells / contour area exceed a threshold
- **Adaptive background** — OpenCV `BackgroundSubtractorMOG2` / KNN; learns the empty scene over time, no fixed snapshot
- **Auto-recapture when idle** — refresh the background snapshot after N seconds with no significant motion
- **Motion trigger** — frame differencing only; idle until movement, then show disturbance (lo-fi, no background model)

</details>

<details>
<summary>Later — more modules</summary>

Scale by changing install layout only — no new processing pipeline:

- One camera → one mask → split into tiles per module → pack per module → API by module ID
- Example: `INSTALL_MODULES_X = 2`, `INSTALL_MODULES_Y = 2` → four modules, four ESP32s

Pi 5 is sufficient for this; the work is mostly config, crop/split math, and the module API.

</details>

<br>
<br>

# Raspberry Pi

The Pi runs the **camera processor** — it captures webcam input, applies background subtraction, and prepares binary frames for the ESP32 display controller. This section holds everything needed to **install, deploy, and maintain** that setup on the device.

**Pi 5**
- home `luizamorim@192.168.1.234`
- opal `luizamorim@192.168.8.107`
- hostname: `pi5`

**Pi Zero 2W**
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
| Debugger   | `python3 debugger.py --index /dev/video0`                    |
| Run        | `python3 main.py --index /dev/video0`                        |

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

Pi Zero 2W wiring:

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

## 4. Production loop

Run the camera processor headless:

```bash
cd ~/camera-processor
python3 main.py --index /dev/video0
```

Useful flags:

```bash
# Tune motion sensitivity (higher = less sensitive)
python3 main.py --index /dev/video0 --bg-threshold 30

# Invert detection if silhouette is backwards
python3 main.py --index /dev/video0 --invert

# Pi 5 default is ~25 FPS (config.TARGET_FPS). Lower only if the Pi struggles:
python3 main.py --index /dev/video0 --fps 5

# Cleaner mask (slower)
python3 main.py --index /dev/video0 --morphology
```

---

## 5. Debugger (development only)

Runs a web UI on the Pi for tuning background subtraction from my Mac browser. Click **Capture background** with an empty scene before expecting a silhouette.

```bash
cd ~/camera-processor
python3 debugger.py --index /dev/video0
```

On my Mac, open: `http://192.168.1.157:8080`


For the installation, run `main.py` headless instead.

---

## 6. Run automatically on boot (optional)

Once everything works manually:

1. Create `/etc/systemd/system/camera-processor.service`
2. Set `ExecStart` to `python3 /home/luizamorim/camera-processor/main.py`
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
- **Pi address** — `PI_HOST` (e.g. `192.168.1.157`), `PI_PORT` (default `8080`)
- **Module identity** — `MODULE_ID` (`0` for the first module; `1` for the second in Phase 3)
- **Tile layout** — `MODULE_TILES_X`, `MODULE_TILES_Y` must match `camera-processor/config.py`

`config.h` is gitignored — credentials stay local.

---

## 2. Build and flash (PlatformIO)

Open **`display-controller/`** as the project root in Cursor (see `platformio.ini`).

- **Build** — PlatformIO build task
- **Upload** — connect ESP32 via USB, then PlatformIO upload
- **Monitor** — Serial @ `115200` to confirm WiFi and frame polling

On boot the board runs a row test (`RUN_ROW_TEST_ON_BOOT`), then polls `GET http://{PI_HOST}:{PI_PORT}/api/module/{MODULE_ID}` every ~100 ms.

---

## 3. Sync with the Pi

Before relying on the display:

1. Pi is running `main.py` (see Raspberry Pi section above)
2. `MODULE_TILES_X/Y` and payload size match on both sides
3. ESP32 and Pi are on the **same WiFi network**
4. Quick check from any machine on the LAN:

```bash
curl -s "http://192.168.1.157:8080/api/health"
curl -s "http://192.168.1.157:8080/api/module/0" | xxd | head
```

Expected byte count must match `BYTES_PER_MODULE` in both `config.h` and Pi `config.py`.

</details>

<br>
<br>



# Journal

Informal log of what happened as the project moved forward — meetings, decisions, hardware mistakes, code experiments, that kind of thing. I'm capturing these entries here to help me formulate my ideas for the writing report later, so when I sit down to write I don't have to reconstruct everything from memory.

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

