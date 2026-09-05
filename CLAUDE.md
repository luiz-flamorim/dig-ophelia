# Dig Ophelia — agent context

**Dig Ophelia** (working title, evolved from "Digit Mirror") is an MA/final-project physical computing installation by Luiz Amorim (Goldsmiths): a webcam feed is reduced to a binary silhouette/disturbance mask and rendered on a physical LED tile display, so the audience sees a fragmented, machine-legible reconstruction of themselves rather than a faithful reflection.

Before non-trivial work, read `.claude/NOTES.md` (fuller brief: architecture, vocabulary, current state, open decisions) and `camera-processor/process-flow.md` (Pi-side pipeline in call order). Both are living docs — keep them current when project state shifts.

## Ground rules

- **No git commands — status/diff/log/commit, anything — without asking first, every time.** This is the user's flagship MA project; treat it with care. A prior "yes" does not carry forward to the next git action.
- **Stay inside this `Code/` folder.** Don't act on sibling folders (e.g. `_context/` at the repo root is reference-only, gitignored, never deployed).
- **No large edits, deletions, or renames without checking in first.**
- **Only touch what the user explicitly points at in a session.** Anything wider needs a check-in before acting.
- **Don't propose diagram-generation tools** (Mermaid, Graphviz, D2, Excalidraw, draw.io, etc.) unprompted — the user hand-draws their own diagrams from docs like `process-flow.md`.

## Architecture

```
USB webcam → Raspberry Pi (camera-processor/, Python) → binary mask → packed bytes
    → HTTP API (Pi serves GET /api/module/{id}) → ESP32 (display-controller/, C++/PlatformIO)
    → LED tile matrix (physical display)
```

Vocabulary: **Tile** = 8×16 cells (16 bytes packed), one physical panel slice. **Module** = one ESP32, currently 4×1 tiles. **Install** = full arrangement of modules.

## Repo map

| Path | Status |
|------|--------|
| `camera-processor/` | Active Pi code (Python) — capture, background subtraction, packing, HTTP server, debugger UI |
| `display-controller/` | Active ESP32 firmware (PlatformIO) — open this subfolder directly in an editor for PlatformIO tooling, not the repo root |
| `_context/` | Reference-only, gitignored. **Pending deletion by the user (2026-09-05)** — confirmed safe, see `.claude/NOTES.md`. Once gone, drop this row and the `readme.md` rsync notes that mention it. |
| `readme.md` | Living doc: plan/roadmap, Pi deployment + PlatformIO instructions, and a dated **Journal** log |
| `.claude/NOTES.md` | Fuller agent brief — current state, decisions in progress (e.g. Kinect pipeline exploration) |
| `.claude/process-flow.md` | Pi pipeline call-flow map, in actual trigger order |
| `.claude/agents/project-explainer.md` | Read-only subagent for dissertation-style *functional* explanations of the codebase |
| `.claude/agents/journal-keeper.md` | Subagent that logs dev sessions into readme.md's Journal section only |

## Journal logging

Use the `journal-keeper` subagent to log a dev session (or when the user says something like "log today's session"). It interviews the user, drafts an entry, waits for explicit confirmation, and writes **only** to the `# Journal` section of `readme.md` — never code, never other readme sections. Don't freehand journal edits outside that flow.
