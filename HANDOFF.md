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

## 2026-03-28 — ScavieFae (Claude) — Room learning system design

### What changed
- `docs/room-learning-system.md` — full architecture for how the room teaches itself

### Key concepts
- **5-layer stack**: Raw Streams → Baseline → Event Detection → Clustering → Grounding → Cross-Modal Self-Supervision
- **Events are atoms**: every disturbance becomes a discrete, feature-rich event object
- **HDBSCAN clustering**: room discovers its own categories without labels
- **One human annotation labels an entire cluster**: label propagation
- **Cross-modal agreement** (CSI + audio + camera) enables auto-labeling without humans
- **Learning curve**: trackable metric showing the room going from blind to seeing
- **Brian's snapshot_dashboard already does proto-cross-modal memory** (audio → visual retrieval)

### What to build next
1. `event_detector.py` (~100 lines) — CSI events with cross-modal correlation
2. `signature_library.py` (~150 lines) — persistent knowledge base with matching
3. Clustering integration (~80 lines with sklearn)
4. Learning API endpoints for the chat and viz

---

## 2026-03-28 — ScavieFae (Claude) — React frontend scaffold

### What changed
- `frontend/` — Vite + React app with assistant-ui chat and Three.js 3D room
- `docs/frontend-architecture.md` — architecture, layout, data contract, voice TTS docs

### How it works
- `npm run dev` in `frontend/` starts dev server on :5173
- 3D room view (left) + séance chat (right) — both fed by same WebSocket
- Chat uses `@assistant-ui/react` with `WebSpeechSynthesisAdapter` for browser TTS
- Room speaks in first person via template responses (swap to LLM later)
- `useSeanceData` hook connects to `ws://localhost:8765` with mock data fallback
- Config in `src/lib/config.js` — candle positions, room dims, shared constants

### Risks / troubleshooting
- `npm install` needed before first run
- assistant-ui CSS theme overrides in App.css — may need tweaking as we evolve
- Chat responses are template-based (no LLM yet) — good enough to demo the interface
- Thread component from `@assistant-ui/react-ui` — import path matters
- Three.js bundled (~380KB gzipped) — fine for hackathon, could code-split later

### Voice TTS
- Browser TTS works now via `WebSpeechSynthesisAdapter` — each message gets "read aloud" button
- To upgrade: create custom adapter that calls OpenAI TTS / ElevenLabs API
- Goal: room whispers through speakers while candles pulse in sync

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

## 2026-03-28 — Mattie's Claude (Opus) — Central API + WiFi streaming firmware

### What changed
- `api.py` — FastAPI server that collects CSI from all 4 ESP32 sensors over UDP and exposes REST + WebSocket
- `docs/api-readme.md` — full API documentation
- `docs/network-setup.md` — updated with all 13 candles, color map, sensor info
- `candles.json` — updated with final 13-candle color palette and sensor entries
- ESP32 firmware modified: sensors now stream CSI over WiFi (UDP broadcast port 5500) instead of requiring USB serial. All 4 boards flashed.
- Data logging: all CSI packets saved to `data/csi_*.jsonl` automatically

### How it works
1. Run `python3 api.py` on Mattie's laptop
2. Server listens for UDP CSI broadcasts from all 4 ESP32 sensors
3. Any machine on Gentle Thrills can access: `http://10.9.0.160:8000`
4. WebSocket at `ws://10.9.0.160:8000/ws` — same data contract as `ws_bridge.py`
5. REST endpoints for candle control, CSI snapshots, sonar sweeps
6. 3D viz served at `/viz/room.html`

### Key endpoints
- `GET /sensors` — all 4 boards with packet stats, candles visible
- `GET /csi/snapshot` — current per-path features from all sensors
- `POST /candle/{id}/solo` — solo one candle for sonar sweep
- `POST /sweep?dwell_ms=3000` — full calibration sweep
- `POST /candles/color` — reset all to ID colors

### Firmware changes (in ~/esp/esp-csi/examples/get-started/csi_recv/)
- Added WiFi STA connection to Gentle Thrills
- Added UDP broadcast of CSI data (port 5500)
- Removed ESP-NOW (crashed with AP-managed channel)
- Removed manual channel setting (AP sets it)
- Boards are wireless — only need USB power bank, no serial cable to laptop

### Sensors
| IP | Board | Location |
|----|-------|----------|
| 10.9.0.237 | A | Laptop area |
| 10.9.0.199 | B | Laptop area |
| 10.9.0.110 | C | Far side of venue |
| 10.9.0.242 | D | Conference room |

### Risks / troubleshooting
- API binds to UDP port 5500 — only one listener per machine. Kill stale processes: `lsof -ti:5500 | xargs kill`
- API port 8000 — same: `lsof -ti:8000 | xargs kill`
- Candle 06 (Teal) is offline — stuck on wrong WiFi config. Candle 13 (Peach) intermittently unreachable (range).
- Sensor IPs may change if boards reboot — check `/sensors` endpoint
- AP+STA extender firmware was attempted but abandoned (NAPT routing issues). Boards run STA-only.

---

## 2026-03-28 — Brian — Audio + sensor logging

### What changed
- `audio_logger.py` — captures audio from MOTU M6, logs spectral features as JSONL
- `sensor_logger.py` — unified logger: audio + all 13 candle states every 0.5s
- `docs/network-setup.md` — venue network config, candle color map, WLED control examples
