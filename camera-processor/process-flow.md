# main.py
- entry point - what you run yourself
- imports server.py, calls its main()
- no logic of its own

# server.py
- triggered by main.py
- ties everything below into one running process
- capture_loop (background thread): calls camera.py -> process.py -> modules.py, on repeat at TARGET_FPS
- probe_loop (background thread): wiring-test mode, lights individual cells/rows/cols on demand
- HTTP handler:
  - GET / and /static/* - serves the debugger UI
  - GET /api/config - layout constants
  - GET /api/state - current grid + settings, for the debugger
  - GET /api/stream - MJPEG preview
  - GET /api/module/{id} - what the ESP32 polls for its frame bytes
  - GET /api/health - status check
  - POST /api/settings - tune bg_threshold, invert, preview_mode
  - POST /api/background/capture - recapture the background reference
  - POST /api/probe - wiring probe controls
- outputs: the HTTP API the ESP32 and the browser debugger both talk to

# camera.py
- called first, each loop, by server.py's capture_loop
- opens the USB webcam (OpenCV / V4L2)
- warms up, optionally locks exposure
- reads one BGR frame at a time
- releases the device on shutdown

# process.py
- called next by capture_loop, with the frame from camera.py
- mirrors and crops it to the install's aspect ratio
- converts to greyscale, blurs
- diffs the frame against a captured background reference
- thresholds the diff into a binary mask
- cleans up the mask (morphology + small-blob filtering)
- downsamples the mask into the install grid (rows x cols of 0/1)
- outputs: binary grid, plus mask/grey/diff for the debugger preview

# modules.py
- called next by capture_loop, with the grid from process.py
- slices the full install grid into one region per module (one ESP32's share of the display)
- calls frame_output.py once per module region

# frame_output.py
- called by modules.py, once per module
- checks the region is the expected size
- calls packer.py to do the actual byte-packing

# packer.py
- called by frame_output.py
- reorders cells to match the physical SPI tile-chain wiring
- packs bits into bytes, MSB-first
- outputs: raw bytes - this is what ends up served at GET /api/module/{id}

# debugger.py
- alias for server.py - same process, separate entry-point name for clarity
- not part of the trigger chain, just another way to start it

# background_subtract.py
- standalone headless alternative to main.py -> server.py, not used in production
- same camera.py -> process.py -> modules.py chain, but no HTTP transport
- useful for local testing without the debugger UI

# config.py
- not triggered by anything - shared constants and layout math
- read by every file above (tile/module/install sizes, thresholds, ports, etc.)
