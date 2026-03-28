#!/usr/bin/env python3
"""
Séance — Central API Server

Collects CSI data from all ESP32 sensors over UDP, processes it,
and exposes everything via REST + WebSocket. Any computer on the
network can connect.

    python api.py                # start server
    python api.py --mock         # mock data, no hardware

REST:
    GET  /candles                 list all candles + status
    POST /candles/color           set all candles to ID colors
    POST /candle/{id}/color       set one candle's color
    POST /candle/{id}/solo        light one, darken others
    POST /candles/all             set all candles to same color
    GET  /sensors                 list sensors + packet stats
    GET  /csi/snapshot            5-second CSI capture from all boards
    GET  /csi/room/{sensor_ip}    per-path features for one sensor

WebSocket:
    ws://host:8000/ws             live CSI perception stream (same format as ws_bridge)
"""

import argparse
import asyncio
import json
import math
import os
import socket
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import requests as http_requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ─── Config ──────────────────────────────────────────────────────────

UDP_CSI_PORT = 5500
API_PORT = 8000
CSI_PADDING_PAIRS = 6
VARIANCE_WINDOW = 20
BASELINE_WINDOW = 50
DISTURBANCE_THRESHOLD = 3.0

# Load candle config
CANDLES_JSON = Path(__file__).parent / "candles.json"
with open(CANDLES_JSON) as f:
    CANDLE_CONFIG = json.load(f)

CANDLE_MACS = {}  # "aa:bb:cc:dd:ee:ff" -> {"id": "03", "name": "Gold", ...}
for key, c in CANDLE_CONFIG["candles"].items():
    mac = ":".join(c["mac"][i:i+2] for i in range(0, 12, 2))
    CANDLE_MACS[mac] = {
        "id": key.replace("candle_", ""),
        "name": c["color_name"],
        "ip": c["ip"],
        "color": c["color"],
        "mac_raw": c["mac"],
    }

# Reverse: mac_raw -> colon mac
MAC_RAW_TO_COLON = {v["mac_raw"]: k for k, v in CANDLE_MACS.items()}

SENSOR_LABELS = {
    "10.9.0.237": "A (laptop)",
    "10.9.0.199": "B (laptop)",
    "10.9.0.110": "C (far side)",
    "10.9.0.242": "D (conf room)",
}

# ─── CSI Processing ──────────────────────────────────────────────────

class PathState:
    """Rolling state for one transmitter->sensor signal path."""

    def __init__(self):
        self.rssi_buf = []
        self.amp_buf = []
        self.packet_count = 0
        self.baseline_mean = None
        self.baseline_var = None
        self.baseline_rssi = None
        self.calibrated = False
        self.disturbance_count = 0

    def add(self, rssi, amplitudes):
        self.packet_count += 1
        self.rssi_buf.append(rssi)
        if self.amp_buf and len(amplitudes) != len(self.amp_buf[-1]):
            target_len = len(self.amp_buf[-1])
            if len(amplitudes) > target_len:
                amplitudes = amplitudes[:target_len]
            else:
                amplitudes = amplitudes + [0.0] * (target_len - len(amplitudes))
        self.amp_buf.append(amplitudes)
        if len(self.amp_buf) > VARIANCE_WINDOW * 3:
            self.amp_buf = self.amp_buf[-VARIANCE_WINDOW * 2:]
            self.rssi_buf = self.rssi_buf[-VARIANCE_WINDOW * 2:]

    def calibrate(self):
        if len(self.amp_buf) < 5:
            return
        import numpy as np
        try:
            arr = np.array(self.amp_buf[-BASELINE_WINDOW:])
        except ValueError:
            return
        self.baseline_mean = np.mean(arr, axis=0)
        self.baseline_var = np.var(arr, axis=0)
        self.baseline_rssi = float(np.mean(self.rssi_buf[-BASELINE_WINDOW:]))
        self.calibrated = True

    def snapshot(self):
        import numpy as np
        if len(self.amp_buf) < 3:
            return {
                "variance_ratio": 1.0,
                "rssi": self.rssi_buf[-1] if self.rssi_buf else -99,
                "rssi_delta": 0,
                "packets": self.packet_count,
                "disturbed": False,
            }
        try:
            recent = np.array(self.amp_buf[-VARIANCE_WINDOW:])
        except ValueError:
            return {
                "variance_ratio": 1.0,
                "rssi": self.rssi_buf[-1] if self.rssi_buf else -99,
                "rssi_delta": 0,
                "packets": self.packet_count,
                "disturbed": False,
            }
        recent_var = np.var(recent, axis=0)
        recent_rssi = float(np.mean(self.rssi_buf[-VARIANCE_WINDOW:]))

        if self.calibrated and self.baseline_var is not None:
            safe_base = np.where(self.baseline_var > 0.01, self.baseline_var, 0.01)
            ratio = recent_var / safe_base
            max_ratio = float(np.max(ratio))
            rssi_delta = recent_rssi - self.baseline_rssi
        else:
            max_ratio = float(np.max(recent_var))
            rssi_delta = 0

        disturbed = max_ratio > DISTURBANCE_THRESHOLD
        if disturbed:
            self.disturbance_count += 1

        return {
            "variance_ratio": round(max_ratio, 2),
            "rssi": round(recent_rssi, 1),
            "rssi_delta": round(rssi_delta, 1),
            "packets": self.packet_count,
            "disturbed": disturbed,
        }


def parse_csi_line(line):
    """Parse one CSI_DATA line. Returns (mac, rssi, amplitudes) or None."""
    if not line.startswith("CSI_DATA"):
        return None
    try:
        bracket_start = line.index("[")
        bracket_end = line.rindex("]") + 1
        csi_raw = json.loads(line[bracket_start:bracket_end])
        header = line[:bracket_start].rstrip(',"').split(",")
        mac = header[2].strip().lower()
        rssi = int(header[3])

        amplitudes = []
        for i in range(CSI_PADDING_PAIRS * 2, len(csi_raw) - 1, 2):
            amp = math.sqrt(csi_raw[i] ** 2 + csi_raw[i + 1] ** 2)
            amplitudes.append(amp)

        return mac, rssi, amplitudes
    except Exception:
        return None


# ─── Global State ─────────────────────────────────────────────────────

# sensor_ip -> mac -> PathState
sensor_paths = defaultdict(lambda: defaultdict(PathState))
# sensor_ip -> {packets, first_seen, last_seen}
sensor_stats = defaultdict(lambda: {"packets": 0, "first_seen": None, "last_seen": None})
# All unique MACs seen
all_macs = set()
# Start time
start_time = time.time()
# WebSocket clients
ws_clients = set()
# Data log file
data_log = None


# ─── UDP Listener ─────────────────────────────────────────────────────

async def udp_listener(mock=False):
    """Listen for CSI packets from all sensors over UDP broadcast."""
    global data_log

    if mock:
        print("[api] Mock mode — generating fake data")
        await mock_generator()
        return

    # Open log file
    log_path = Path(__file__).parent / "data" / f"csi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    log_path.parent.mkdir(exist_ok=True)
    data_log = open(log_path, "a")
    print(f"[api] Logging CSI data to {log_path}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", UDP_CSI_PORT))
    sock.setblocking(False)

    print(f"[api] Listening for CSI on UDP port {UDP_CSI_PORT}")

    loop = asyncio.get_event_loop()
    calibrated_sensors = set()
    broadcast_counter = 0

    while True:
        try:
            data, addr = await loop.run_in_executor(None, lambda: sock.recvfrom(2048))
        except BlockingIOError:
            await asyncio.sleep(0.01)
            continue
        except Exception:
            await asyncio.sleep(0.01)
            continue

        sensor_ip = addr[0]
        line = data.decode(errors="ignore").strip()

        result = parse_csi_line(line)
        if result is None:
            continue

        mac, rssi, amps = result
        all_macs.add(mac)

        # Update sensor stats
        now = time.time()
        stats = sensor_stats[sensor_ip]
        stats["packets"] += 1
        if stats["first_seen"] is None:
            stats["first_seen"] = now
            label = SENSOR_LABELS.get(sensor_ip, "unknown")
            print(f"[api] New sensor: {sensor_ip} ({label})")
        stats["last_seen"] = now

        # Update path state
        sensor_paths[sensor_ip][mac].add(rssi, amps)

        # Calibrate after 5s per sensor
        if sensor_ip not in calibrated_sensors and now - stats["first_seen"] > 5:
            print(f"[api] Calibrating sensor {sensor_ip}")
            for p in sensor_paths[sensor_ip].values():
                p.calibrate()
            calibrated_sensors.add(sensor_ip)

        # Log to disk (every packet)
        if data_log:
            candle_info = CANDLE_MACS.get(mac)
            log_entry = {
                "t": round(now, 3),
                "sensor": sensor_ip,
                "mac": mac,
                "rssi": rssi,
                "candle": candle_info["id"] if candle_info else None,
            }
            data_log.write(json.dumps(log_entry) + "\n")

        # Broadcast to WebSocket clients every 5 packets
        broadcast_counter += 1
        if broadcast_counter % 5 == 0:
            await ws_broadcast()


async def ws_broadcast():
    """Push current state to all WebSocket clients."""
    if not ws_clients:
        return

    elapsed = time.time() - start_time
    total_pkts = sum(s["packets"] for s in sensor_stats.values())
    pps = total_pkts / elapsed if elapsed > 0 else 0

    # Build per-candle-MAC path data (aggregate across sensors)
    path_data = {}
    for sensor_ip, paths in sensor_paths.items():
        for mac, ps in paths.items():
            if mac in CANDLE_MACS:
                snap = ps.snapshot()
                key = mac
                if key not in path_data or snap["variance_ratio"] > path_data[key]["variance_ratio"]:
                    path_data[key] = snap

    disturb_count = sum(1 for p in path_data.values() if p.get("disturbed"))
    disturbed_names = [
        CANDLE_MACS[m]["name"] + " " + CANDLE_MACS[m]["id"]
        for m in path_data if path_data[m].get("disturbed") and m in CANDLE_MACS
    ]

    if disturbed_names:
        narrative = f"Disturbance near {', '.join(disturbed_names)}."
    else:
        narrative = "The electromagnetic field is calm."

    payload = {
        "paths": path_data,
        "meta": {
            "packets_per_sec": round(pps),
            "unique_macs": len(all_macs),
            "disturbance_count": disturb_count,
            "uptime_s": round(elapsed),
            "sensors_active": len(sensor_stats),
        },
        "narrative": narrative,
    }

    msg = json.dumps(payload)
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


# ─── Mock Data ────────────────────────────────────────────────────────

async def mock_generator():
    t0 = time.time()
    while True:
        t = time.time() - t0
        for mac, info in CANDLE_MACS.items():
            for sensor_ip in ["10.9.0.237", "10.9.0.242"]:
                base = 1.0 + math.sin(t * 0.4 + hash(mac) % 10) * 1.2
                spike = 10 * (math.sin(t * 0.15 + hash(mac) % 7) > 0.85)
                ratio = max(0.5, base + spike)
                rssi = -45 + math.sin(t * 0.3 + hash(mac) % 5) * 8
                ps = sensor_paths[sensor_ip][mac]
                ps.rssi_buf.append(rssi)
                ps.packet_count += 1
                all_macs.add(mac)
                sensor_stats[sensor_ip]["packets"] += 1
                sensor_stats[sensor_ip]["last_seen"] = time.time()
                if sensor_stats[sensor_ip]["first_seen"] is None:
                    sensor_stats[sensor_ip]["first_seen"] = time.time()
        await ws_broadcast()
        await asyncio.sleep(0.2)


# ─── Candle Control Helpers ───────────────────────────────────────────

def hex_to_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i+2], 16) for i in (0, 2, 4)]


def set_candle(candle_id, color_rgb=None, bri=51):
    """Set a candle's color. Returns success bool."""
    key = f"candle_{candle_id.zfill(2)}"
    candle = CANDLE_CONFIG["candles"].get(key)
    if not candle:
        return False
    if color_rgb is None:
        color_rgb = hex_to_rgb(candle["color"])
    try:
        r = http_requests.post(
            f"http://{candle['ip']}/json/state",
            json={"seg": [{"fx": 0, "col": [color_rgb]}], "bri": bri},
            timeout=3,
        )
        return r.status_code == 200
    except Exception:
        return False


# ─── FastAPI App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(udp_listener(mock=app.state.mock))
    yield
    task.cancel()

app = FastAPI(title="Séance API", lifespan=lifespan)
app.state.mock = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── WebSocket ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)


# ─── REST: Sensors ────────────────────────────────────────────────────

@app.get("/sensors")
def get_sensors():
    result = {}
    now = time.time()
    for ip, stats in sensor_stats.items():
        elapsed = now - stats["first_seen"] if stats["first_seen"] else 0
        pps = stats["packets"] / elapsed if elapsed > 0 else 0
        candles_seen = [
            CANDLE_MACS[mac]["name"] + " (" + CANDLE_MACS[mac]["id"] + ")"
            for mac in sensor_paths[ip] if mac in CANDLE_MACS
        ]
        result[ip] = {
            "label": SENSOR_LABELS.get(ip, "unknown"),
            "packets": stats["packets"],
            "pps": round(pps, 1),
            "last_seen_ago": round(now - stats["last_seen"], 1) if stats["last_seen"] else None,
            "candles_visible": candles_seen,
        }
    return result


# ─── REST: Candles ────────────────────────────────────────────────────

@app.get("/candles")
def get_candles():
    result = {}
    for key, c in CANDLE_CONFIG["candles"].items():
        cid = key.replace("candle_", "")
        result[cid] = {
            "name": c["color_name"],
            "ip": c["ip"],
            "mac": c["mac"],
            "color": c["color"],
        }
    return result


@app.post("/candles/color")
def reset_all_colors(bri: int = 51):
    """Set all candles to their assigned ID colors."""
    results = {}
    for key, c in CANDLE_CONFIG["candles"].items():
        cid = key.replace("candle_", "")
        ok = set_candle(cid, bri=bri)
        results[cid] = "ok" if ok else "unreachable"
    return results


@app.post("/candles/all")
def set_all_candles(r: int = 255, g: int = 255, b: int = 255, bri: int = 51):
    """Set all candles to the same color."""
    results = {}
    for key, c in CANDLE_CONFIG["candles"].items():
        cid = key.replace("candle_", "")
        ok = set_candle(cid, color_rgb=[r, g, b], bri=bri)
        results[cid] = "ok" if ok else "unreachable"
    return results


@app.post("/candle/{candle_id}/color")
def set_one_candle(candle_id: str, r: int = 255, g: int = 255, b: int = 255, bri: int = 51):
    """Set one candle's color."""
    ok = set_candle(candle_id, color_rgb=[r, g, b], bri=bri)
    return {"candle": candle_id, "status": "ok" if ok else "unreachable"}


@app.post("/candle/{candle_id}/solo")
def solo_candle(candle_id: str, r: int = 255, g: int = 255, b: int = 255, bri: int = 128):
    """Light one candle, darken all others."""
    results = {}
    for key, c in CANDLE_CONFIG["candles"].items():
        cid = key.replace("candle_", "")
        if cid == candle_id.zfill(2):
            ok = set_candle(cid, color_rgb=[r, g, b], bri=bri)
        else:
            ok = set_candle(cid, color_rgb=[0, 0, 0], bri=0)
        results[cid] = "ok" if ok else "unreachable"
    return results


# ─── REST: CSI ────────────────────────────────────────────────────────

@app.get("/csi/snapshot")
def csi_snapshot():
    """Current CSI state from all sensors."""
    result = {}
    for sensor_ip, paths in sensor_paths.items():
        label = SENSOR_LABELS.get(sensor_ip, sensor_ip)
        candle_paths = {}
        for mac, ps in paths.items():
            if mac in CANDLE_MACS:
                info = CANDLE_MACS[mac]
                candle_paths[f"{info['name']} ({info['id']})"] = ps.snapshot()
        result[label] = candle_paths
    return result


@app.get("/csi/room/{sensor_ip}")
def csi_room(sensor_ip: str):
    """Per-path features for one sensor."""
    if sensor_ip not in sensor_paths:
        return {"error": "sensor not found", "available": list(sensor_stats.keys())}
    paths = sensor_paths[sensor_ip]
    result = {}
    for mac, ps in paths.items():
        label = CANDLE_MACS[mac]["name"] + " (" + CANDLE_MACS[mac]["id"] + ")" if mac in CANDLE_MACS else mac
        result[label] = ps.snapshot()
    return result


# ─── REST: Sweep ──────────────────────────────────────────────────────

@app.post("/sweep")
async def sweep(dwell_ms: int = 3000, bri: int = 128):
    """Cycle through all candles one by one. Solo each, capture CSI."""
    results = []
    for key, c in sorted(CANDLE_CONFIG["candles"].items()):
        cid = key.replace("candle_", "")
        # Solo this candle
        for k2, c2 in CANDLE_CONFIG["candles"].items():
            cid2 = k2.replace("candle_", "")
            if cid2 == cid:
                set_candle(cid2, color_rgb=[255, 255, 255], bri=bri)
            else:
                set_candle(cid2, color_rgb=[0, 0, 0], bri=0)
        # Dwell
        await asyncio.sleep(dwell_ms / 1000.0)
        # Snapshot
        snap = {}
        for sensor_ip, paths in sensor_paths.items():
            mac_colon = ":".join(c["mac"][i:i+2] for i in range(0, 12, 2))
            if mac_colon in paths:
                snap[SENSOR_LABELS.get(sensor_ip, sensor_ip)] = paths[mac_colon].snapshot()
        results.append({"candle": cid, "name": c["color_name"], "csi": snap})

    # Reset all to ID colors
    for key, c in CANDLE_CONFIG["candles"].items():
        cid = key.replace("candle_", "")
        set_candle(cid, bri=51)

    return results


# ─── Static files (viz) ──────────────────────────────────────────────

viz_dir = Path(__file__).parent / "viz"
if viz_dir.exists():
    app.mount("/viz", StaticFiles(directory=str(viz_dir), html=True), name="viz")


@app.get("/")
def root():
    return {
        "name": "Séance API",
        "endpoints": [
            "GET  /candles",
            "POST /candles/color",
            "POST /candles/all?r=&g=&b=&bri=",
            "POST /candle/{id}/color?r=&g=&b=&bri=",
            "POST /candle/{id}/solo",
            "GET  /sensors",
            "GET  /csi/snapshot",
            "GET  /csi/room/{sensor_ip}",
            "POST /sweep?dwell_ms=3000",
            "WS   /ws",
            "GET  /viz/room.html",
        ],
        "sensors_active": len(sensor_stats),
        "uptime_s": round(time.time() - start_time),
    }


# ─── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Séance API Server")
    parser.add_argument("--mock", action="store_true", help="Mock data, no hardware")
    parser.add_argument("--port", type=int, default=API_PORT, help="API port")
    args = parser.parse_args()

    app.state.mock = args.mock
    print(f"[api] Starting on http://0.0.0.0:{args.port}")
    print(f"[api] Brian can connect at http://10.9.0.160:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
