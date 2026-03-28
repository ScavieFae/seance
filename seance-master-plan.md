# Seance — Hackathon Master Plan

## Event: Multimodal Frontier Hackathon
**Date:** Saturday March 28, 2026, 9:30 AM – 7:30 PM
**Location:** 660 Market St, Floor 3, San Francisco
**Team:** Mattie & Brian
**Time budget:** ~10 hours (8 hours building, 1.5 hours demo/judging, 0.5 hours buffer)

---

## The Concept

An AI agent that perceives a room through WiFi signals bouncing between 13 brass candles. It starts blind, learns what a person looks like in radio waves over the course of the day, and makes its perception visible through the candles themselves. The room is both the sensor and the display.

**Pitch line:** "We scattered candles around the room and taught an AI to see through walls using the WiFi signals between them. No cameras. No wearables. Kill the lights — and watch the room see you back."

---

## Hardware Kit

### Bring from home
- [ ] 13× PartyPi candles (charged overnight)
- [ ] GL-AXT1800 router "Gentle Thrills" (fallback if venue WiFi uncooperative)
- [ ] Laptop + charger
- [ ] Power strip
- [ ] Velcro strips / painter's tape (for mounting ESP32s)
- [ ] Phone (WiFi analyzer app for channel checking)
- [ ] Micro-USB data cables (confirmed working: 1× with serial `113340`, need 2+ more)

### Hardware on hand
- [x] 4× ESP32-S3-DevKitC boards (micro-USB, not USB-C)
- [x] USB power banks for remote sensor placement

### Pre-installed on laptop (done Friday night)
- [x] ESP-IDF v5.4 toolchain (`~/esp/esp-idf`)
- [x] esp-csi repo cloned (`~/esp/esp-csi`)
- [x] `csi_recv` firmware built and tested for ESP32-S3
- [x] `csi_send` firmware built for ESP32-S3
- [x] Modified `csi_recv`: MAC filter removed, gain compensation disabled, promiscuous mode
- [x] Python environment: pyserial, numpy, scipy, scikit-learn, requests
- [x] Serial CSI reader validated at 921600 baud

---

## Friday Night Validation Results

### What was validated
1. **ESP-IDF install + build**: Clean compile for ESP32-S3 target
2. **Flash + serial comms**: Board flashes via micro-USB, serial output at 921600 baud
3. **Promiscuous CSI capture**: 9 unique MACs captured in 5 seconds on home WiFi
4. **Candle CSI**: ~80 packets/5s from a candle when pinged, ambient traffic also captured
5. **Motion detection**: Per-subcarrier variance shows 19x SNR for hand motion on candle path
6. **Proximity tracking**: RSSI drop from baseline correctly identifies nearest candle, drives real-time color changes
7. **WLED control**: `POST /json/state` with `fx:0` for solid color override

### Firmware modifications (in `~/esp/esp-csi/examples/get-started/csi_recv/main/app_main.c`)
- Line 144: MAC filter removed (was filtering to paired sender only)
- Line 201-204: Gain compensation disabled (raw `int8_t` CSI values instead of compensated)
- Promiscuous mode was already enabled in stock firmware

### Flashing command
```bash
export IDF_PATH=~/esp/esp-idf && source $IDF_PATH/export.sh
cd ~/esp/esp-csi/examples/get-started/csi_recv
idf.py -p /dev/cu.usbserial-XXXXXX flash
```

---

## Saturday Timeline

### 9:30–10:15 — Setup (45 min)

**First 10 min: Scout RF environment**
- Get venue WiFi SSID and password
- Check which 2.4GHz channel is active: `system_profiler SPAirPortDataType | grep -A5 "Current Network"`
- Decide: venue WiFi (preferred) or "Gentle Thrills" (fallback)
- If venue channel ≠ 11, update `CONFIG_LESS_INTERFERENCE_CHANNEL` in firmware and rebuild

**Next 30 min: Deploy candles**
- If using venue WiFi: reconfigure candles one at a time via WLED AP mode
  - Power on candle → creates WLED-AP-XXXX if can't find known network
  - Connect phone to WLED-AP-XXXX → browse 4.3.2.1 → WiFi Settings → enter venue credentials → save & reboot
  - Note IP address (check ARP table or scan: `curl http://{ip}/json/info`)
  - Repeat ×13, parallelize (configure one while previous reboots)
- If using Gentle Thrills: just power on candles, they auto-join
- Place candles around room — spread for maximum spatial coverage, avoid metal surfaces
- Record all candle IPs and MACs

**Last 5 min: Deploy ESP32 sensors**
- Flash boards if channel changed, otherwise already built
- Position sensors in corners / strategic locations
- Plug into laptop (nearby) and power banks (remote)
- Verify CSI flowing: `python3 -c "import serial; ..."`  (see onepager for reader code)

### 10:15–12:00 — Core Pipeline (1 hr 45 min)

**Serial CSI reader + per-path extraction**
- Read CSI from all connected ESP32s
- Identify candle MAC addresses in CSI source data
- Compute per-path features: per-subcarrier variance (top-5 mean), RSSI vs baseline
- Store in rolling time windows

**Candle HTTP control**
- Verify control of all 13 candles via WLED API
- `POST /json/state` with `{"seg":[{"fx":0,"col":[[R,G,B]],"bri":N}]}`
- Map CSI metrics → candle visual state

**Baseline calibration**
- Capture 5 seconds of CSI with room still (or known state)
- Store per-candle baseline RSSI and per-subcarrier CSI fingerprint

### 12:00–1:30 — Agent Brain (1 hr 30 min)

**Perception fusion**
- Aggregate per-path CSI features into zone-level spatial model
- Structure as JSON perception payload
- Two metrics proven: per-subcarrier variance (motion), RSSI delta (proximity)

**LLM integration**
- Agent receives perception JSON as context
- Can answer questions: "What's happening near candle 7?"
- Can issue commands: decide which candles to update based on perception

**Candle response loop**
- Agent perception → candle visual update cycle
- Idle candles glow warm amber
- Active zones brighten and shift color

### 1:30–3:00 — Learning System (1 hr 30 min) — STRETCH

**Seed calibration** → **Similarity matching** → **Cross-modal self-supervision** → **Growing library**

See `seance-learning-system.md` for full spec.

### 3:00–4:30 — Visualization & Polish (1 hr 30 min)

**Abstract map view (PRIMARY)**
See `seance-visualization.md` for full design spec.

**Sponsor integrations / chat interface**

**End-to-end test**
- Full loop: person walks → CSI changes → agent perceives → candles react → viz updates

### 4:30–5:30 — Demo Prep (1 hr)

### 5:30–6:00 — Buffer

### 6:00–7:30 — Demos & Judging

**Demo script:**

1. **Context** (30 sec): "Most agents only process text and images. We asked: what if an agent could perceive the invisible electromagnetic spectrum?"

2. **The candles** (30 sec): "We scattered 13 candles around the room. Each is a WiFi transmitter. Our agent uses the signals bouncing between them to sense this space — no cameras."

3. **Live perception** (1 min): Have someone walk across the room. Candles respond. Show CSI data changing.

4. **Through-wall trick** (30 sec): Candle behind a partition. Agent detects presence before the person is visible.

5. **The reveal** (30 sec): "Can you kill the overhead lights?" Room goes dark. Candles respond to people. The room sees them back.

6. **Vision** (30 sec): "Every WiFi router is already a sensor. The 802.11bf standard published last year formalizes this. We built the agent that makes it useful."

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| ESP32 boards DOA or won't flash | Have 4 boards, only need 2. One validated Friday. |
| Venue WiFi is 5GHz only | Bring GL-AXT1800 "Gentle Thrills" as fallback |
| Venue WiFi on different channel | Rebuild firmware with correct channel (~2 min rebuild) |
| Candle reconfiguration too slow | Parallelize. Worst case: use Gentle Thrills, skip reconfiguration |
| Micro-USB cables are charge-only | Confirmed 1 data cable. Test remaining cables before leaving |
| CSI too noisy for fine-grained sensing | Lean into aggregate signals. RSSI proximity works even when CSI is noisy |
| Metal surfaces near candles | Keep candles clear of metal. Learned: toaster oven killed C13's signal |
| Learning system too ambitious | Marked stretch. Core demo works with raw CSI variance → candle response |
| Demo room has no partition | Use distance instead — candle far across room |

---

## Success Criteria

### Minimum Viable Demo
- [x] CSI data flowing from ESP32s, reacting to candle transmissions *(validated Friday)*
- [x] Candles visually responding to CSI-detected activity *(validated Friday — proximity tracking)*
- [ ] Agent can narrate what it perceives
- [ ] Through-wall or through-distance sensing demonstrated

### Full Demo
- [ ] Chat interface where judges can query the agent
- [ ] Learning system showing growth over time
- [ ] The lights-out candle reveal moment
- [ ] Visualization showing signal paths and activity

### Dream Demo
- [ ] Per-path spatial resolution on dashboard
- [ ] Agent autonomously discovering activity categories
- [ ] The judges genuinely forget there are no cameras in the room

---

## Sponsor Integrations

Ranked by natural fit to the project and prize value. See `docs/hackathon-sponsors-prizes.md` for full prize details.

### Tier 1 — Strong Fit (integrate these)

**assistant-ui — Chat interface ($800)**
The judge-facing chat interface where people ask the agent what it perceives. "What's happening near candle 7?" / "How many people are in the room?" This is the exact use case assistant-ui is built for — ChatGPT-grade conversational UX wired to our agent's perception loop. Replaces building a chat UI from scratch.

**Railtracks — Agent framework ($1,300)**
Frame the Seance agent's perception→reasoning→action loop using Railtracks' agentic framework. CSI data flows in as sensor input, the agent reasons about spatial state, and outputs candle control commands + natural language narration. The agent architecture maps directly to their builder model.

**DigitalOcean — Inference cloud ($1,000 cash + credits)**
Run LLM inference on DigitalOcean's GPU cloud instead of locally. Keeps the laptop free for serial connections to ESP32 sensors. Also makes the architecture more credible — the sensing pipeline runs at the edge, inference runs in the cloud, control commands flow back down.

**Augment Code — AI coding agent ($3,500 — largest cash prize)**
Use Augment Code during development to build the pipeline. Biggest cash prize of any sponsor. Integration is usage-based (show that Augment helped write the codebase), not architectural. Worth pursuing for the prize alone.

### Tier 2 — Workable Fit (integrate if time allows)

**Nexla — Data pipeline ($900 cash + credits)**
Frame the CSI data flow as a real-time data integration problem: raw serial streams from 4 ESP32s → parsed CSI packets → per-path feature extraction → structured perception JSON → agent consumption. Nexla's data pipeline tools could manage the transformation and routing.

**Unkey — API infrastructure (enterprise license worth up to $25k)**
If we expose the agent's perception as an API (`/api/perception`, `/api/candles/control`), use Unkey for API key management. Quick integration, and the prize (1 year enterprise license at any scale) is potentially the most valuable non-cash prize.

### Tier 3 — Skip Unless Required

**Senso.ai** — Not enough info on their product to assess fit.

**WorkOS** — Enterprise auth/directory sync. Doesn't map to a hackathon demo with no user accounts.

**Google DeepMind** — Not a sponsor with a prize category, but reference AM-FM and frontier perception research in the pitch. DeepMind judges would appreciate the research framing.
