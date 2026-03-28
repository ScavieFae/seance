# Séance API Server

Central server that collects CSI data from all ESP32 sensors over UDP and exposes everything via REST + WebSocket. Runs on Mattie's laptop, accessible to all machines on Gentle Thrills.

## Quick Start

```bash
cd ~/claude-projects/seance
python3 api.py          # live data from ESP32 sensors
python3 api.py --mock   # mock data, no hardware needed
```

Server starts on `http://0.0.0.0:8000`. From other machines on Gentle Thrills: `http://10.9.0.160:8000`.

## How It Works

```
[ESP32 sensors A/B/C/D]
    ↓ UDP broadcast (port 5500)
[api.py — UDP listener]
    ↓ processes CSI per-path features
    ↓ logs all packets to data/csi_*.jsonl
    ↓ broadcasts to WebSocket clients
    → REST endpoints for candle control + CSI queries
```

The API replaces the need for each machine to run its own UDP listener. One server collects from all 4 sensors, any client can connect.

## Endpoints

### Candles

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/candles` | List all candles with IP, MAC, assigned color |
| `POST` | `/candles/color?bri=51` | Reset all candles to their ID colors |
| `POST` | `/candles/all?r=255&g=0&b=0&bri=128` | Set all candles to same color |
| `POST` | `/candle/{id}/color?r=255&g=0&b=0&bri=128` | Set one candle |
| `POST` | `/candle/{id}/solo` | Light one candle, darken all others |

Candle IDs are `01`–`13` (zero-padded or not — both work).

### Sensors & CSI

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/sensors` | List all sensors with packet stats, candles visible |
| `GET` | `/csi/snapshot` | Current per-path CSI features from all sensors |
| `GET` | `/csi/room/{sensor_ip}` | Per-path features for one sensor |
| `POST` | `/sweep?dwell_ms=3000` | Cycle all candles solo, capture CSI for each |

### WebSocket

Connect to `ws://10.9.0.160:8000/ws` for live streaming. Pushes JSON every ~200ms:

```json
{
  "paths": {
    "aa:bb:cc:dd:ee:ff": {
      "variance_ratio": 4.2,
      "rssi": -55.3,
      "rssi_delta": -2.1,
      "packets": 142,
      "disturbed": true
    }
  },
  "meta": {
    "packets_per_sec": 145,
    "unique_macs": 18,
    "disturbance_count": 3,
    "uptime_s": 120,
    "sensors_active": 4
  },
  "narrative": "Disturbance near Gold 03, Green 05."
}
```

Path keys are MAC addresses. Cross-reference with `/candles` to map MAC → candle name.

### Viz

The 3D visualization is served at `/viz/room.html`. It connects to the same WebSocket.

### Sweep (for sonar calibration)

`POST /sweep?dwell_ms=3000` cycles through all candles:
1. Solos each candle (white, others dark)
2. Dwells for `dwell_ms` milliseconds
3. Captures CSI snapshot from all sensors
4. Returns array of `{candle, name, csi}` per candle
5. Resets all to ID colors when done

## Data Logging

All CSI packets are logged to `data/csi_YYYYMMDD_HHMMSS.jsonl`. Each line:

```json
{"t": 1711612345.123, "sensor": "10.9.0.242", "mac": "c8:c9:a3:39:a9:07", "rssi": -55, "candle": "03"}
```

## Sensors

| IP | Board | Location |
|----|-------|----------|
| 10.9.0.237 | A | Laptop area |
| 10.9.0.199 | B | Laptop area |
| 10.9.0.110 | C | Far side of venue |
| 10.9.0.242 | D | Conference room |

All sensors stream CSI over UDP broadcast on port 5500. The API server collects from all of them.

## Dependencies

All already installed: `fastapi`, `uvicorn`, `requests`, `numpy`, `websockets`.
