# Plan

Roadmap for scaling the camera processor from proof of concept to the full install. ESP32 grid dimensions must match the Pi (see `_context/display-controller_esp32/`).

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
<summary>Phase 1 — Product in progress (now)</summary>

Adapting the code from the browser / p5.js proof of concept into a Pi-based product:

- Background subtraction pipeline (`main.py`, `process.py`)
- Packed binary output for ESP32 (`packer.py`, `frame_output.py`)
- Browser debugger on the Pi (`debugger.py`, `debugger_static/`)
- USB webcam via OpenCV/V4L2
- Single **8×16** tile (matches current ESP32 prototype)

Transport to ESP32 is still TBD (`background_subtract.py` — WiFi / API).

</details>

<details>
<summary>Phase 2 — One module, one ESP32</summary>

- Pi treats the scene as **2×2 tiles** (32×16 logical grid)
- Split mask → four tile regions → combine into **one module payload** (64 bytes)
- **One ESP32** pulls its message from the Pi API by **module ID** (e.g. `GET /api/module/0`)
- ESP32 constants scale to the full module (e.g. 16 rows × 32 cols) — same `processMessage()` logic, larger buffer

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

</details>

<details>
<summary>Later — more modules</summary>

Scale by changing install layout only — no new processing pipeline:

- One camera → one mask → split into tiles per module → pack per module → API by module ID
- Example: `INSTALL_MODULES_X = 2`, `INSTALL_MODULES_Y = 2` → four modules, four ESP32s

Pi 5 (2 GB) is sufficient for this; the work is mostly config, crop/split math, and the module API.

</details>

<br>
<br>

# Raspberry Pi

The Pi runs the **camera processor** — it captures webcam input, applies background subtraction, and prepares binary frames for the ESP32 display controller. This section holds everything needed to **install, deploy, and maintain** that setup on the device.

**Pi:** `luizamorim@192.168.1.157` (hostname: `pizero`)  
**Code on Mac:** `Code/camera-processor/` — copy to the Pi from the Mac terminal, not from inside an SSH session.

| Step        | Command / check                                              |
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
  "/Users/luizamorim/Library/Mobile Documents/com~apple~CloudDocs/Goldsmiths/Projects/_Final Project/Proposal/Code/camera-processor/" \
  luizamorim@192.168.1.157:~/camera-processor/
```

Note: destination is `luizamorim@192.168.1.157:~/camera-processor/` — no extra characters before the colon.

### Option B — scp

```bash
scp -r \
  "/Users/luizamorim/Library/Mobile Documents/com~apple~CloudDocs/Goldsmiths/Projects/_Final Project/Proposal/Code/camera-processor" \
  luizamorim@192.168.1.157:~/
```

Same scope as rsync — only the `camera-processor/` folder, not repo-root `_context/`.

### Verify on the Pi

```bash
ssh luizamorim@192.168.1.157
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

Success looks like a second (or third) device line, e.g. `ARC International Camera`. If only the root hub appears, the camera isn't detected — see Common issues.

Find which `/dev/video*` belongs to the webcam (not Pi internal codec nodes):

```bash
sudo apt install -y v4l-utils
v4l2-ctl --list-devices
```

Note the path under the camera name (e.g. `/dev/video0`). Use that path for `debugger.py`:

```bash
python3 debugger.py --index /dev/video0
```


### Background subtraction — production loop

Useful flags:

```bash
# Tune motion sensitivity (higher = less sensitive)
python3 main.py --bg-threshold 30

# Invert detection if silhouette is backwards
python3 main.py --invert

# Lower FPS if the Pi struggles
python3 main.py --fps 5

# Cleaner mask (slower)
python3 main.py --morphology
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



# Journal

Informal log of what happened as the project moved forward — meetings, decisions, hardware mistakes, code experiments, that kind of thing. I'm capturing these entries here to help me formulate my ideas for the writing report later, so when I sit down to write I don't have to reconstruct everything from memory.

<details>
<summary>2026-06-19 — readme restructure</summary>

- reorganised **readme.md** so the **Plan** (scaling roadmap) comes first — tiles, modules, install phases — instead of being buried below the Pi deployment steps
- folded each **Plan phase** into collapsible `<details>` blocks so the page is easier to scan without losing the detail
- split out a dedicated **Raspberry Pi** section with a short intro on what the Pi actually does in the pipeline, and moved the **quick checklist** to the top of that section for at-a-glance reference
- tucked the full **install instructions** (copy, deps, hardware, debugger, systemd) inside a collapsible block — less wall of text when I'm not deploying
- updated **rsync/scp** notes: `_context/` now lives at the **repo root**, not inside `camera-processor/`, so the copy commands only sync the deploy folder and no longer need `--exclude '_context'`
- dropped the old **mental model** rsync diagram — the Mac-vs-Pi reminder is now a one-liner under the Pi header

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

