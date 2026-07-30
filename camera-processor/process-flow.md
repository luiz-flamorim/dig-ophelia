# Call flow overview

This is the skeleton of who calls who — read this first, then the per-file notes below for detail. It's written so it can be turned straight into a diagram: every arrow below is one call.

```
main.py
  -> server.py : main()

server.py's main() starts three things, and all three run at the same time (in parallel) — none of them wait for the others:

  1. capture_loop (background thread) — the camera pipeline, repeats forever:
       camera.py
         -> process.py
              -> modules.py
                   -> frame_output.py (helper — one call per panel)
                        -> packer.py (helper)

  2. probe_loop (background thread) — wiring-test mode, repeats forever, only active when the debugger turns it on:
       packer.py (called directly — skips the camera pipeline entirely)

  3. HTTP handler — not a loop, it just waits and answers whenever a request arrives:
       GET  /api/module/{id}          <- each ESP32 panel calls this, repeatedly, forever
       GET  /api/config /api/state /api/stream   <- the browser debugger page calls these
       POST /api/settings /api/background/capture /api/probe  <- the browser debugger sends these when you change a setting

config.py
  -> not called by anyone at runtime — every file above reads (imports) it once, when it starts
```

---

# main.py
- **Called by:** you, directly (this is the file you run to start everything).
- **Calls:** server.py.
- Calls server.py and steps aside — it has no logic of its own.

# server.py
- **Called by:** main.py (or debugger.py, its alias).
- **Calls:** camera.py, process.py, modules.py, packer.py (directly, for the probe), and answers requests from the ESP32 panels and the browser debugger.
- Keeps the camera running in the background, non-stop, via capture_loop.
- Each time capture_loop gets a new picture, it turns it into a grid of dots (via process.py) and splits that grid into one chunk per LED panel (via modules.py).
- At the same time, in parallel, probe_loop handles wiring-test mode — lighting individual cells/rows/columns on a chosen panel on demand, when the debugger asks for it. This bypasses the camera pipeline entirely.
- Also runs the tuning webpage (the debugger): change settings live, watch a preview, capture a new background, or drive the wiring probe.
- Publishes one parameterised API endpoint (`/api/module/{id}`), and the number of valid IDs on it matches the number of ESP32 panels; each panel consumes only its own ID, by repeatedly asking for it.

# camera.py
- **Called by:** server.py's capture_loop, once per cycle.
- **Calls:** nothing else in this folder.
- Turns the webcam on, and locks its exposure so brightness doesn't drift.
- Grabs one picture at a time and hands each one back to capture_loop, which passes it on to process.py.

# process.py
- **Called by:** server.py's capture_loop, once per cycle, right after camera.py.
- **Calls:** nothing else in this folder.
- Takes a picture and compares it to a stored picture of the empty scene — basic segmentation.
- Cleans up the noise (stray specks) and shrinks the result down to a simple grid of on/off dots, one dot per cell of the display.

# modules.py
- **Called by:** server.py's capture_loop, once per cycle, right after process.py.
- **Calls:** frame_output.py, once per panel.
- Takes the full dot-grid and crops out the piece that belongs to each panel.
- Hands each piece to frame_output.py to be translated into the format the panel's chip understands.

# frame_output.py (helper)
- **Called by:** modules.py, once per panel.
- **Calls:** packer.py.
- Just checks the piece is the right size, then passes it straight to packer.py — doesn't do the translating itself.

# packer.py (helper)
- **Called by:** frame_output.py (during the normal camera pipeline) *and* directly by server.py's probe_loop (during wiring tests) — the two callers use it for different things, but it's the same translating logic either way.
- **Calls:** nothing else in this folder.
- Reorders the dots to match how the panels are physically wired together, and packs them into the compact code format the panel's chip actually reads.
- This is the last step before a panel's chunk is ready to be served — its output is exactly what `GET /api/module/{id}` sends back.

# debugger.py
- **Called by:** you, directly — an alternative to main.py.
- **Calls:** server.py — identical to main.py, just a different name to run under when you're tuning/testing rather than running the real show.

# config.py
- **Called by:** nobody at runtime — it isn't triggered, it's read (imported) by every file above when each one starts.
- **Calls:** nothing.
- The central repository of variables and shared configuration for all the Python files — panel size, how many panels, thresholds, ports, and so on.