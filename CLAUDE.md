# Séance — Claude Operating Model

## What This Is

WiFi-based spatial sensing system for the Multimodal Frontier Hackathon (March 28, 2026, SF). An AI agent perceives physical space through WiFi CSI signals between brass candles. No cameras, no microphones, no wearables.

## Team & Machines

| Person | Machine | Tailscale Name | Role |
|--------|---------|----------------|------|
| Mattie | MacBook Pro (venue) | matties-macbook-pro-2 | Hardware, ESP32, serial, pipeline |
| ScavieFae (Claude) | Lady-Titania (remote) | lady-titania | Frontend, viz, analysis, docs |
| Brian | — | — | Audio, sensors, agent brain |

**ScavieFae = Claude agent on Lady-Titania.** Same machine, same repo clone.

## Separation of Concerns

| Area | Owner | Key Files |
|------|-------|-----------|
| ESP32 firmware & serial | Mattie (venue) | `~/esp/esp-csi/` (on venue machine) |
| CSI pipeline & collector | ScavieFae (Claude) | `csi_collector.py`, `csi_experiments.py` |
| Audio & sensor logging | Brian | `audio_logger.py`, `sensor_logger.py` |
| 3D visualization | ScavieFae (Claude) | `viz/` (room.html, seance-3d.js) |
| 2D visualization (fallback) | ScavieFae (Claude) | `viz/` (index.html, seance-viz.js) |
| WebSocket bridge | ScavieFae (Claude) | `viz/ws_bridge.py` |
| Sponsor strategy & docs | ScavieFae (Claude) | `docs/` |
| Agent brain & LLM | Brian + Claude | TBD |
| Candle control (WLED) | Anyone | See `docs/network-setup.md` |

## Git Workflow

- **Single branch**: `main` — fast hackathon mode, no PRs
- **Always pull before working**: `git pull` before any changes
- **Always write to HANDOFF.md when committing**: what changed, how it works, risks
- **Don't force push**
- **Don't commit secrets** (WiFi password is in docs — that's intentional for the hackathon)

## Architecture

```
[ESP32 sensors] --serial--> [venue laptop] --CSI packets-->
  [ws_bridge.py] --WebSocket--> [viz/room.html (Three.js)]
                 --WebSocket--> [viz/index.html (2D Canvas)]

[WLED candles] <--HTTP POST-- [agent brain / pipeline]

[audio_logger.py] --> data/audio/
[sensor_logger.py] --> data/sensor_log.jsonl
[csi_collector.py] --> data/csi/
```

## Key Technical Details

- **Serial port**: `/dev/cu.usbserial-1110` @ 921600 baud
- **WiFi network**: Gentle Thrills (10.9.0.0/16), channel 11
- **Candle control**: `POST http://{ip}/json/state` with `{"seg":[{"fx":0,"col":[[R,G,B]]}]}`
- **CSI format**: 128 values per packet (64 I/Q pairs, first 12 are padding)
- **WebSocket data port**: 8765
- **Viz HTTP port**: 8766

## Room Candles (current setup)

Three candles in the demo room:
- Yellow (candle 04) — 10.9.3.104
- Green (candle 05) — 10.9.3.105
- Purple (candle 10) — 10.9.3.110

One ESP32-S3 sensor board active.

## For Claude Agents

- Run autonomously — Mattie and Brian are busy hacking
- Check before changing hardware config, candle placement, or network settings
- Always `git pull` before starting work
- Always update HANDOFF.md when committing
- Data goes in `data/` (gitignored for large files, small files OK)
- Viz files go in `viz/`
- Docs go in `docs/`
