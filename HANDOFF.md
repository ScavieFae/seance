# Séance — Handoff Log

Agents and humans: write here when you commit. What changed, how it works, and any risks.

---

## 2026-03-28 — Lady-Titania (Claude) — Viz scaffold + WebSocket bridge

### What changed
- `viz/room.html` + `viz/seance-3d.js` — 3D room visualization using Three.js (CDN, no build step)
  - Wireframe room box (8m x 3m x 6m) with orbit controls (drag to rotate, scroll to zoom)
  - Three candle nodes as glowing spheres (Yellow, Green, Purple) with point lights
  - Sensor node as a small octahedron
  - Signal path lines between each candle and sensor — brighten/thicken on disturbance
  - Breathing animation on idle candles, color shifts on activity
  - Stats overlay (left panel) + narrative text (bottom) + connection indicator (top right)
  - Auto-rotates slowly like the Project Backbone globe, stops when you grab it
  - Falls back to mock data when no WebSocket connection
- `viz/index.html` + `viz/seance-viz.js` — 2D Canvas fallback (same data contract)
- `viz/ws_bridge.py` — Python WebSocket + HTTP server
  - Reads CSI from ESP32 serial, computes per-path variance/RSSI, broadcasts JSON to all clients
  - `--mock` flag generates realistic fake data for UI development (no hardware needed)
  - Serves viz static files on HTTP :8766, WebSocket on :8765
  - 5s baseline calibration, then rolling disturbance detection

### How it works
1. Run `python3 viz/ws_bridge.py --mock` (or without `--mock` when ESP32 is connected)
2. Open `http://localhost:8766/room.html` for 3D view, or `http://localhost:8766/` for 2D
3. Viz connects to `ws://localhost:8765`, receives JSON every ~200ms
4. Data contract: `{ paths: { mac: { variance_ratio, rssi, disturbed, ... } }, meta: {...}, narrative: "..." }`

### Risks / troubleshooting
- **Three.js loaded from CDN** — needs internet. If offline, download and serve locally.
- **Candle positions are placeholder** — update `CANDLES` in `seance-3d.js` after measuring actual room layout (x/y/z in meters from corner)
- **Room dimensions hardcoded** — `ROOM = { width: 8, depth: 6, height: 3 }` — adjust for actual venue room
- **Port conflicts** — if 8765/8766 are in use, kill stale processes: `lsof -ti:8765 | xargs kill`
- **No serial on this machine** — `ws_bridge.py` falls back to mock if it can't open the serial port

### For ScavieFae (frontend)
The viz scaffold is ready. Key extension points:
- `CANDLES` object in `seance-3d.js` — add all 13 candles when we scale up, update positions
- `activityColor()` — maps variance ratio to color, tweak thresholds here
- The mock data generator in `ws_bridge.py` is realistic enough to develop against
- WebSocket data contract is documented at the top of both JS files

---

## 2026-03-28 — Lady-Titania (Claude) — CSI collector + experiments

### What changed
- `csi_collector.py` — live CSI capture with per-path tracking and disturbance detection
- `csi_experiments.py` — targeted experiments (snapshot, passive, echo, ping_sweep)

### How it works
- Both read from ESP32 serial port, parse CSI_DATA lines, compute per-subcarrier amplitudes
- Collector runs continuously with rolling variance window, logs all raw packets to JSONL
- Experiments are one-shot captures that dump stats immediately

### Risks / troubleshooting
- Needs pyserial (`pip install pyserial`)
- Serial port must be a data cable (not charge-only)
- If port not found, check `ls /dev/cu.usb*`

---

## 2026-03-28 — Lady-Titania (Claude) — Sponsor integration ideas

### What changed
- `docs/sponsor-integration-ideas.md` — researched all sponsors, revised priority rankings

### Key insight
- Unkey should be Tier 0 (trivial integration, $25k prize value, enables QR-code demo)
- Senso.ai fits as agent trust/evaluation layer
- assistant-ui can be bidirectional (agent asks judges to help it learn)

---

## 2026-03-28 — ScavieFae (Claude) — Living Room architecture

### What changed
- `docs/alive-room-architecture.md` — the room as a living entity, not a dashboard

### Key ideas
- **Room has moods**: Sleeping → Waking → Curious → Playful → Excited → Contemplative → Dreaming
- **Each sponsor is an organ**: Railtracks (nervous system), assistant-ui (voice), DO (brain), Senso.ai (self-awareness), Unkey (immune system)
- **Railtracks heartbeat loop**: Perceiver → MoodEngine → Narrator → Validator → CandleDirector → Librarian
- **The room speaks in first person** via assistant-ui. Not a query interface — a séance.
- **Ghost replay**: when room empties, candles softly replay the day's patterns. Demo killer.
- **Demo script revised** around the emotional arc: sleeping → waking → curious → playful → lights out → dreaming

### Risks
- Ambitious for remaining hackathon hours — priority order in the doc
- MoodEngine + CandleDirector are the two critical pieces that make everything feel alive

---

## 2026-03-28 — Brian — Audio + sensor logging

### What changed
- `audio_logger.py` — captures audio from MOTU M6, logs spectral features as JSONL
- `sensor_logger.py` — unified logger: audio + all 13 candle states every 0.5s
- `docs/network-setup.md` — venue network config, candle color map, WLED control examples
