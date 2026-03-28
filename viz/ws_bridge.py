#!/usr/bin/env python3
"""
Séance — WebSocket Bridge
Reads CSI data from the ESP32 serial port, computes per-path features,
and pushes structured JSON to all connected WebSocket clients (the viz).

Also serves the viz static files on HTTP for convenience.

Usage:
    python ws_bridge.py                          # serial + WebSocket
    python ws_bridge.py --mock                   # mock data (no hardware)
    python ws_bridge.py --port /dev/cu.usbserial-XXXX  # custom serial port

Viz connects to ws://localhost:8765
Open http://localhost:8766 for the viz page.
"""

import argparse
import asyncio
import json
import math
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import threading

try:
    import websockets
except ImportError:
    print("Need websockets: pip install websockets")
    raise

try:
    import serial
except ImportError:
    serial = None

try:
    import numpy as np
except ImportError:
    np = None

# ─── Config ──────────────────────────────────────────────────────────

SERIAL_PORT = "/dev/cu.usbserial-1110"
BAUD_RATE = 921600
WS_PORT = 8765
HTTP_PORT = 8766
CSI_PADDING_PAIRS = 6

ROOM_CANDLES = {
    "4c752594d210": "Red 01",
    "08f9e0611bc7": "Orange 02",
    "c8c9a339a907": "Gold 03",
    "485519ec2f04": "Lime 04",
    "08f9e0690c68": "Green 05",
    "485519ef0a8d": "Mint 06",
    "c8c9a339a779": "White 07",
    "c8c9a338ec00": "Blue 08",
    "485519ee65c7": "Indigo 09",
    "485519ecd18e": "Violet 10",
    "485519ecd242": "Hot Pink 11",
    "08f9e068ea07": "Crimson 12",
    "485519ec2429": "Peach 13",
}

VARIANCE_WINDOW = 20
BASELINE_WINDOW = 50
DISTURBANCE_THRESHOLD = 3.0

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
        # Normalize amplitude length — real CSI packets can vary in subcarrier count
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
        if len(self.amp_buf) < 5 or np is None:
            return
        try:
            arr = np.array(self.amp_buf[-BASELINE_WINDOW:])
        except ValueError:
            return
        self.baseline_mean = np.mean(arr, axis=0)
        self.baseline_var = np.var(arr, axis=0)
        self.baseline_rssi = float(np.mean(self.rssi_buf[-BASELINE_WINDOW:]))
        self.calibrated = True

    def snapshot(self):
        """Return current state as a dict for the viz."""
        if np is None or len(self.amp_buf) < 3:
            return {
                "variance_ratio": 1.0,
                "rssi": self.rssi_buf[-1] if self.rssi_buf else -99,
                "rssi_delta": 0,
                "packets": self.packet_count,
                "disturbed": False,
                "amp_mean": 0,
                "hottest_subcarriers": [],
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
                "amp_mean": 0,
                "hottest_subcarriers": [],
            }
        recent_var = np.var(recent, axis=0)
        recent_rssi = float(np.mean(self.rssi_buf[-VARIANCE_WINDOW:]))

        if self.calibrated and self.baseline_var is not None:
            safe_base = np.where(self.baseline_var > 0.01, self.baseline_var, 0.01)
            ratio = recent_var / safe_base
            max_ratio = float(np.max(ratio))
            rssi_delta = recent_rssi - self.baseline_rssi
            hottest = [int(i) for i in np.argsort(ratio)[-5:][::-1]]
        else:
            max_ratio = float(np.max(recent_var))
            rssi_delta = 0
            hottest = []

        disturbed = max_ratio > DISTURBANCE_THRESHOLD
        if disturbed:
            self.disturbance_count += 1

        return {
            "variance_ratio": round(max_ratio, 2),
            "rssi": round(recent_rssi, 1),
            "rssi_delta": round(rssi_delta, 1),
            "packets": self.packet_count,
            "disturbed": disturbed,
            "amp_mean": round(float(np.mean(recent)), 2),
            "hottest_subcarriers": hottest,
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


# ─── WebSocket Server ─────────────────────────────────────────────────

clients = set()


async def ws_handler(websocket):
    clients.add(websocket)
    try:
        async for _ in websocket:
            pass  # We only push, don't read
    finally:
        clients.discard(websocket)


async def broadcast(data):
    if not clients:
        return
    msg = json.dumps(data)
    dead = set()
    for ws in clients:
        try:
            await ws.send(msg)
        except websockets.ConnectionClosed:
            dead.add(ws)
    clients.difference_update(dead)


# ─── Serial Reader ────────────────────────────────────────────────────

async def serial_reader(port):
    """Read CSI from serial, process, broadcast to viz."""
    if serial is None:
        print("[bridge] pyserial not installed — use --mock")
        return

    print(f"[bridge] Opening {port} @ {BAUD_RATE}...")
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.5)
    except serial.SerialException as e:
        print(f"[bridge] Cannot open serial: {e}")
        print("[bridge] Falling back to mock data.")
        await mock_generator()
        return

    paths = {}
    total_packets = 0
    start_time = time.time()
    calibrated = False
    all_macs = set()

    print("[bridge] Reading CSI data...")

    while True:
        line = await asyncio.to_thread(ser.readline)
        if not line:
            await asyncio.sleep(0.01)
            continue

        try:
            line = line.decode("utf-8", errors="replace").strip()
        except UnicodeDecodeError:
            continue

        result = parse_csi_line(line)
        if result is None:
            continue

        mac, rssi, amps = result
        total_packets += 1
        all_macs.add(mac)

        if mac not in paths:
            paths[mac] = PathState()
            name = ROOM_CANDLES.get(mac, mac[-6:])
            print(f"[bridge] New path: {name} ({mac})")
        paths[mac].add(rssi, amps)

        # Calibrate after 5s
        if not calibrated and time.time() - start_time > 5:
            print("[bridge] Calibrating baseline...")
            for p in paths.values():
                p.calibrate()
            calibrated = True

        # Broadcast every 5 packets (throttle)
        if total_packets % 5 == 0:
            elapsed = time.time() - start_time
            pps = total_packets / elapsed if elapsed > 0 else 0

            path_data = {}
            for m, ps in paths.items():
                path_data[m] = ps.snapshot()

            disturb_count = sum(1 for p in path_data.values() if p["disturbed"])

            # Generate narrative
            disturbed_names = [
                ROOM_CANDLES.get(m, m[-6:])
                for m, p in path_data.items()
                if p["disturbed"] and m in ROOM_CANDLES
            ]

            if disturbed_names:
                narrative = f"Disturbance on {', '.join(disturbed_names)} signal path{'s' if len(disturbed_names) > 1 else ''}."
            elif calibrated:
                narrative = "The electromagnetic field is calm. Ambient signals only."
            else:
                narrative = "Calibrating... learning the room's baseline signature."

            payload = {
                "paths": path_data,
                "meta": {
                    "packets_per_sec": round(pps),
                    "unique_macs": len(all_macs),
                    "disturbance_count": disturb_count,
                    "uptime_s": round(elapsed),
                },
                "narrative": narrative,
            }

            await broadcast(payload)


# ─── Mock Data Generator ─────────────────────────────────────────────

async def mock_generator():
    """Generate fake but realistic-looking CSI data for UI development."""
    print("[bridge] Running in MOCK mode — no hardware needed.")
    t0 = time.time()
    tick = 0

    while True:
        t = time.time() - t0
        paths = {}

        for mac, name in ROOM_CANDLES.items():
            # Organic noise + occasional spikes
            base = 1.0 + math.sin(t * 0.4 + hash(mac) % 10) * 1.2
            spike = (12 + 6 * math.sin(t * 0.1)) if (math.sin(t * 0.15 + hash(mac) % 7) > 0.85) else 0
            ratio = max(0.5, base + spike + (math.sin(t * 2.3 + hash(mac)) * 0.3))

            paths[mac] = {
                "variance_ratio": round(ratio, 2),
                "rssi": round(-45 + math.sin(t * 0.3 + hash(mac) % 5) * 8, 1),
                "rssi_delta": round(math.sin(t * 0.2 + hash(mac)) * 3, 1),
                "packets": tick * 15 + hash(mac) % 100,
                "disturbed": ratio > DISTURBANCE_THRESHOLD,
                "amp_mean": round(10 + math.sin(t * 0.5) * 3, 2),
                "hottest_subcarriers": [14, 22, 33, 41, 8],
            }

        disturb_count = sum(1 for p in paths.values() if p["disturbed"])
        disturbed_names = [
            ROOM_CANDLES[m] for m, p in paths.items() if p["disturbed"]
        ]

        if disturbed_names:
            narrative = f"Disturbance detected near {', '.join(disturbed_names)}. Something moves through the field."
        else:
            narrative = "The candles are quiet. Listening to ambient electromagnetic whispers."

        payload = {
            "paths": paths,
            "meta": {
                "packets_per_sec": 60 + int(math.sin(t) * 20),
                "unique_macs": 3 + int(math.sin(t * 0.1) * 2),
                "disturbance_count": disturb_count,
                "uptime_s": int(t),
            },
            "narrative": narrative,
        }

        await broadcast(payload)
        tick += 1
        await asyncio.sleep(0.2)


# ─── HTTP Server for static files (async) ────────────────────────────

async def run_http_server(port):
    """Serve viz static files using asyncio — no threading needed."""
    viz_dir = str(Path(__file__).parent)

    async def handle_http(reader, writer):
        request_line = await reader.readline()
        # Consume remaining headers
        while True:
            line = await reader.readline()
            if line == b"\r\n" or line == b"\n" or not line:
                break

        path = request_line.decode().split(" ")[1] if request_line else "/"
        if path == "/":
            path = "/room.html"

        file_path = os.path.join(viz_dir, path.lstrip("/"))
        file_path = os.path.normpath(file_path)

        # Security: stay within viz_dir
        if not file_path.startswith(viz_dir):
            writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # Content types
        ext = os.path.splitext(file_path)[1]
        content_types = {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
        }
        ctype = content_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                body = f.read()
            header = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: {ctype}\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"\r\n"
            )
            writer.write(header.encode() + body)
        except FileNotFoundError:
            writer.write(b"HTTP/1.1 404 Not Found\r\n\r\nNot found")

        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle_http, "0.0.0.0", port)
    print(f"[bridge] Viz at http://localhost:{port}")
    await server.serve_forever()


# ─── Main ─────────────────────────────────────────────────────────────

async def main(args):
    # Start HTTP + WebSocket servers concurrently
    print(f"[bridge] WebSocket on ws://localhost:{WS_PORT}")

    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        http_task = asyncio.create_task(run_http_server(HTTP_PORT))

        if args.mock:
            await mock_generator()
        else:
            await serial_reader(args.port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Séance WebSocket Bridge")
    parser.add_argument("--mock", action="store_true", help="Use mock data (no hardware)")
    parser.add_argument("--port", default=SERIAL_PORT, help="Serial port")
    args = parser.parse_args()

    asyncio.run(main(args))
