#!/usr/bin/env python3
"""
Seance — CSI Collector & Live Disturbance Detector
Promiscuous capture of all CSI data from ESP32-S3 sensor.
Logs everything raw, computes per-path features, flags disturbances.

Usage:
    python csi_collector.py                    # capture + live analysis
    python csi_collector.py --baseline 10      # collect 10s baseline first
    python csi_collector.py --ping             # actively ping candles for CSI
    python csi_collector.py --dump latest      # dump stats from last capture
"""

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import serial
import requests

# --- Config ---
SERIAL_PORT = "/dev/cu.usbserial-1110"
BAUD_RATE = 921600
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csi")

# The three candles in the room + any other MACs we see
KNOWN_MACS = {
    "485519ec2f04": {"name": "Yellow",  "candle": "04", "ip": "10.9.3.104"},
    "08f9e0690c68": {"name": "Green",   "candle": "05", "ip": "10.9.3.105"},
    "485519ecd18e": {"name": "Purple",  "candle": "10", "ip": "10.9.3.110"},
    # Other candles (not in room but might see their traffic)
    "4c752594d210": {"name": "Red",     "candle": "01", "ip": "10.9.3.101"},
    "08f9e0611bc7": {"name": "Orange",  "candle": "02", "ip": "10.9.3.102"},
    "c8c9a339a907": {"name": "Gold",    "candle": "03", "ip": "10.9.3.103"},
    "485519ef0a8d": {"name": "Teal",    "candle": "06", "ip": "10.9.3.106"},
    "c8c9a339a779": {"name": "Cyan",    "candle": "07", "ip": "10.9.3.107"},
    "c8c9a338ec00": {"name": "Sky Blue","candle": "08", "ip": "10.9.3.108"},
    "485519ee65c7": {"name": "Blue",    "candle": "09", "ip": "10.9.3.109"},
    "485519ecd242": {"name": "Magenta", "candle": "11", "ip": "10.9.3.111"},
    "08f9e068ea07": {"name": "Rose",    "candle": "12", "ip": "10.9.3.112"},
    "485519ec2429": {"name": "Warm Wht","candle": "13", "ip": "10.9.3.113"},
}

# CSI parsing: 128 values = 64 I/Q pairs, first 6 pairs (12 values) are padding
CSI_PADDING_PAIRS = 6
NUM_SUBCARRIERS = 52  # 64 total - 6 padding - some nulls, but we'll use 52 active

# Analysis windows
VARIANCE_WINDOW = 20       # packets to compute rolling variance over
BASELINE_WINDOW = 50       # packets for baseline calibration
DISTURBANCE_THRESHOLD = 3  # multiplier over baseline variance to flag disturbance


def _apply_overrides(port=None, threshold=None):
    global SERIAL_PORT, DISTURBANCE_THRESHOLD
    if port:
        SERIAL_PORT = port
    if threshold:
        DISTURBANCE_THRESHOLD = threshold


def parse_csi_line(line):
    """Parse a CSI_DATA line from serial into structured dict."""
    if not line.startswith("CSI_DATA"):
        return None
    try:
        # Split the CSV but handle the quoted CSI array at the end
        # Format: CSI_DATA,id,mac,rssi,rate,sig_mode,mcs,bw,smoothing,
        #         not_sounding,aggregation,stbc,fec,sgi,noise_floor,
        #         ampdu_cnt,channel,sec_channel,timestamp,ant,sig_len,
        #         rx_state,len,first_word,"[csi_values]"
        bracket_start = line.index("[")
        bracket_end = line.rindex("]") + 1
        csi_str = line[bracket_start:bracket_end]
        header = line[:bracket_start].rstrip(',"').split(",")

        csi_raw = json.loads(csi_str)
        mac = header[2].strip().lower()
        rssi = int(header[3])
        noise_floor = int(header[14]) if len(header) > 14 else -90
        channel = int(header[16]) if len(header) > 16 else 11
        timestamp_esp = int(header[18]) if len(header) > 18 else 0

        # Convert interleaved I/Q to complex amplitudes, skip padding
        amplitudes = []
        phases = []
        for i in range(CSI_PADDING_PAIRS * 2, len(csi_raw) - 1, 2):
            imag = csi_raw[i]
            real = csi_raw[i + 1]
            amp = math.sqrt(imag ** 2 + real ** 2)
            phase = math.atan2(imag, real)
            amplitudes.append(amp)
            phases.append(phase)

        return {
            "mac": mac,
            "rssi": rssi,
            "noise_floor": noise_floor,
            "channel": channel,
            "timestamp_esp": timestamp_esp,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "amplitudes": amplitudes,
            "phases": phases,
            "csi_raw": csi_raw,
            "n_subcarriers": len(amplitudes),
        }
    except (ValueError, IndexError, json.JSONDecodeError) as e:
        return None


def mac_label(mac):
    """Human-readable label for a MAC."""
    info = KNOWN_MACS.get(mac)
    if info:
        return f"{info['name']} (candle {info['candle']})"
    return f"unknown:{mac[-6:]}"


class PathTracker:
    """Tracks CSI statistics for a single transmitter->sensor path."""

    def __init__(self, mac):
        self.mac = mac
        self.label = mac_label(mac)
        self.packet_count = 0
        self.rssi_history = []
        self.amplitude_history = []  # list of amplitude arrays
        self.baseline_mean = None    # per-subcarrier mean amplitude
        self.baseline_var = None     # per-subcarrier variance
        self.baseline_rssi = None
        self.last_disturbance = 0
        self.disturbance_count = 0

    def add_packet(self, parsed):
        self.packet_count += 1
        self.rssi_history.append(parsed["rssi"])
        self.amplitude_history.append(parsed["amplitudes"])

        # Keep rolling window
        if len(self.amplitude_history) > VARIANCE_WINDOW * 3:
            self.amplitude_history = self.amplitude_history[-VARIANCE_WINDOW * 2:]
            self.rssi_history = self.rssi_history[-VARIANCE_WINDOW * 2:]

    def compute_baseline(self):
        """Compute baseline from accumulated data."""
        if len(self.amplitude_history) < 5:
            return
        arr = np.array(self.amplitude_history[-BASELINE_WINDOW:])
        self.baseline_mean = np.mean(arr, axis=0)
        self.baseline_var = np.var(arr, axis=0)
        self.baseline_rssi = np.mean(self.rssi_history[-BASELINE_WINDOW:])

    def detect_disturbance(self):
        """Check recent packets for disturbance vs baseline."""
        if self.baseline_var is None or len(self.amplitude_history) < VARIANCE_WINDOW:
            return None

        recent = np.array(self.amplitude_history[-VARIANCE_WINDOW:])
        recent_var = np.var(recent, axis=0)

        # Compare per-subcarrier variance to baseline
        # Avoid division by zero
        safe_baseline = np.where(self.baseline_var > 0.01, self.baseline_var, 0.01)
        ratio = recent_var / safe_baseline
        max_ratio = float(np.max(ratio))
        mean_ratio = float(np.mean(ratio))

        # RSSI shift
        recent_rssi = np.mean(self.rssi_history[-VARIANCE_WINDOW:])
        rssi_delta = recent_rssi - self.baseline_rssi if self.baseline_rssi else 0

        # Amplitude shift from baseline
        recent_mean = np.mean(recent, axis=0)
        amp_delta = np.mean(np.abs(recent_mean - self.baseline_mean))

        is_disturbed = max_ratio > DISTURBANCE_THRESHOLD

        if is_disturbed:
            self.disturbance_count += 1
            self.last_disturbance = time.time()

        return {
            "path": self.label,
            "mac": self.mac,
            "disturbed": is_disturbed,
            "max_variance_ratio": round(max_ratio, 2),
            "mean_variance_ratio": round(mean_ratio, 2),
            "rssi_now": round(recent_rssi, 1),
            "rssi_delta": round(rssi_delta, 1),
            "amp_delta": round(amp_delta, 2),
            "packets": self.packet_count,
            "top_subcarriers": [int(i) for i in np.argsort(ratio)[-5:][::-1]],
        }

    def summary_line(self):
        d = self.detect_disturbance()
        if d is None:
            return f"  {self.label:25s}  pkts={self.packet_count:>5}  (calibrating...)"
        flag = "!! DISTURBED !!" if d["disturbed"] else "   quiet      "
        return (
            f"  {self.label:25s}  "
            f"pkts={d['packets']:>5}  "
            f"RSSI={d['rssi_now']:>5.1f} ({d['rssi_delta']:+.1f})  "
            f"var_ratio: max={d['max_variance_ratio']:>6.1f} mean={d['mean_variance_ratio']:>5.1f}  "
            f"{flag}"
        )


def ping_candle(ip):
    """Ping a candle to generate a response packet with extractable CSI."""
    try:
        r = requests.get(f"http://{ip}/json/state", timeout=1)
        return r.status_code == 200
    except requests.RequestException:
        return False


def run_collector(args):
    os.makedirs(DATA_DIR, exist_ok=True)
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = os.path.join(DATA_DIR, f"csi_raw_{session_id}.jsonl")
    events_file = os.path.join(DATA_DIR, f"csi_events_{session_id}.jsonl")

    print(f"{'='*70}")
    print(f"  SEANCE CSI LAB — session {session_id}")
    print(f"{'='*70}")
    print(f"  Serial:  {SERIAL_PORT} @ {BAUD_RATE}")
    print(f"  Raw log: {raw_file}")
    print(f"  Events:  {events_file}")
    print(f"  Room candles: Yellow (04), Green (05), Purple (10)")
    print(f"{'='*70}\n")

    # Open serial
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print(f"FATAL: Cannot open {SERIAL_PORT}: {e}")
        print("Is the ESP32 connected? Check cable (must be data, not charge-only).")
        sys.exit(1)

    trackers = {}      # mac -> PathTracker
    mac_counter = defaultdict(int)
    total_packets = 0
    start_time = time.time()
    last_display = 0
    baseline_done = False
    baseline_target = args.baseline if args.baseline else 5  # seconds

    print("Listening for CSI packets...\n")

    with open(raw_file, "a") as raw_f, open(events_file, "a") as evt_f:
        try:
            while True:
                line = ser.readline()
                if not line:
                    continue
                try:
                    line = line.decode("utf-8", errors="replace").strip()
                except UnicodeDecodeError:
                    continue

                parsed = parse_csi_line(line)
                if parsed is None:
                    # Still log non-CSI lines that might be interesting
                    if line and not line.startswith("CSI_DATA") and len(line) > 5:
                        pass  # could log debug output here
                    continue

                total_packets += 1
                mac = parsed["mac"]
                mac_counter[mac] += 1

                # Log raw data — EVERY packet
                raw_f.write(json.dumps(parsed) + "\n")
                if total_packets % 20 == 0:
                    raw_f.flush()

                # Track per-path
                if mac not in trackers:
                    trackers[mac] = PathTracker(mac)
                    print(f"  [NEW PATH] {mac_label(mac)} — {mac}")
                trackers[mac].add_packet(parsed)

                # Active pinging
                if args.ping and total_packets % 50 == 0:
                    for candle_mac, info in KNOWN_MACS.items():
                        if info["candle"] in ("04", "05", "10"):
                            ping_candle(info["ip"])

                # Baseline calibration
                elapsed = time.time() - start_time
                if not baseline_done and elapsed > baseline_target:
                    print(f"\n  [BASELINE] Calibrating from {baseline_target}s of data...")
                    for t in trackers.values():
                        t.compute_baseline()
                        if t.baseline_mean is not None:
                            print(f"    {t.label}: baseline RSSI={t.baseline_rssi:.1f}, "
                                  f"mean_amp={np.mean(t.baseline_mean):.1f}, "
                                  f"subcarriers={len(t.baseline_mean)}")
                    baseline_done = True
                    print(f"  [BASELINE] Done. Watching for disturbances...\n")

                # Live display every 1s
                now = time.time()
                if now - last_display > 1.0:
                    last_display = now
                    elapsed = now - start_time
                    rate = total_packets / elapsed if elapsed > 0 else 0

                    # Clear and redraw
                    status = "BASELINE" if not baseline_done else "HUNTING"
                    print(f"\033[2J\033[H", end="")  # clear screen
                    print(f"{'='*70}")
                    print(f"  SEANCE CSI LAB — {status} — {elapsed:.0f}s — "
                          f"{total_packets} pkts ({rate:.0f}/s) — {len(trackers)} paths")
                    print(f"{'='*70}")

                    # Sort: room candles first, then by packet count
                    room_macs = {"485519ec2f04", "08f9e0690c68", "485519ecd18e"}
                    sorted_trackers = sorted(
                        trackers.values(),
                        key=lambda t: (t.mac not in room_macs, -t.packet_count)
                    )

                    print(f"\n  {'PATH':25s}  {'PKTS':>5}  {'RSSI':>13}  {'VARIANCE RATIO':>25}  STATUS")
                    print(f"  {'─'*25}  {'─'*5}  {'─'*13}  {'─'*25}  {'─'*16}")
                    for t in sorted_trackers:
                        print(t.summary_line())

                        # Log disturbance events
                        d = t.detect_disturbance()
                        if d and d["disturbed"]:
                            evt_f.write(json.dumps({
                                **d,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "session": session_id,
                            }) + "\n")
                            evt_f.flush()

                    print(f"\n  All MACs seen: {', '.join(f'{mac_label(m)}({c})' for m, c in sorted(mac_counter.items(), key=lambda x: -x[1]))}")
                    print(f"\n  [Ctrl+C to stop]")

        except KeyboardInterrupt:
            print(f"\n\n{'='*70}")
            print(f"  SESSION COMPLETE — {session_id}")
            print(f"  Duration: {time.time() - start_time:.0f}s")
            print(f"  Total packets: {total_packets}")
            print(f"  Unique MACs: {len(mac_counter)}")
            print(f"  Raw data: {raw_file}")
            print(f"  Events: {events_file}")
            for t in trackers.values():
                d = t.detect_disturbance()
                if d:
                    print(f"  {t.label}: {t.disturbance_count} disturbances detected")
            print(f"{'='*70}")


def dump_session(session_name):
    """Dump stats from a previous capture session."""
    if session_name == "latest":
        files = sorted(f for f in os.listdir(DATA_DIR) if f.startswith("csi_raw_"))
        if not files:
            print("No capture sessions found.")
            return
        session_name = files[-1].replace("csi_raw_", "").replace(".jsonl", "")

    raw_file = os.path.join(DATA_DIR, f"csi_raw_{session_name}.jsonl")
    if not os.path.exists(raw_file):
        print(f"Session file not found: {raw_file}")
        return

    print(f"Loading session {session_name}...")
    mac_data = defaultdict(lambda: {"rssi": [], "amps": [], "count": 0})

    with open(raw_file) as f:
        for line in f:
            try:
                p = json.loads(line)
                mac = p["mac"]
                mac_data[mac]["rssi"].append(p["rssi"])
                mac_data[mac]["amps"].append(p["amplitudes"])
                mac_data[mac]["count"] += 1
            except (json.JSONDecodeError, KeyError):
                continue

    print(f"\n{'='*70}")
    print(f"  SESSION: {session_name}")
    print(f"  Total packets: {sum(d['count'] for d in mac_data.values())}")
    print(f"  Unique MACs: {len(mac_data)}")
    print(f"{'='*70}\n")

    for mac, data in sorted(mac_data.items(), key=lambda x: -x[1]["count"]):
        rssi = np.array(data["rssi"])
        amps = np.array(data["amps"])
        if len(amps) == 0:
            continue

        mean_amp = np.mean(amps, axis=0)
        var_amp = np.var(amps, axis=0)

        print(f"  {mac_label(mac):25s}  ({mac})")
        print(f"    Packets: {data['count']}")
        print(f"    RSSI:    mean={np.mean(rssi):.1f}  std={np.std(rssi):.1f}  "
              f"range=[{np.min(rssi)}, {np.max(rssi)}]")
        print(f"    Amp:     mean={np.mean(mean_amp):.1f}  max_var={np.max(var_amp):.1f}  "
              f"subcarriers={len(mean_amp)}")
        # Find most volatile subcarriers
        top_volatile = np.argsort(var_amp)[-5:][::-1]
        print(f"    Hottest subcarriers: {list(top_volatile)} "
              f"(var={[round(var_amp[i], 1) for i in top_volatile]})")
        print()


def main():
    parser = argparse.ArgumentParser(description="Seance CSI Collector & Disturbance Detector")
    parser.add_argument("--baseline", type=int, default=5,
                        help="Seconds of baseline calibration (default: 5)")
    parser.add_argument("--ping", action="store_true",
                        help="Actively ping room candles to generate CSI")
    parser.add_argument("--dump", type=str, default=None,
                        help="Dump stats from a session ('latest' for most recent)")
    parser.add_argument("--port", type=str, default=SERIAL_PORT,
                        help="Serial port override")
    parser.add_argument("--threshold", type=float, default=DISTURBANCE_THRESHOLD,
                        help="Disturbance detection threshold (default: 3x baseline)")
    args = parser.parse_args()

    if args.port != SERIAL_PORT or args.threshold != DISTURBANCE_THRESHOLD:
        _apply_overrides(args.port, args.threshold)

    if args.dump:
        dump_session(args.dump)
    else:
        run_collector(args)


if __name__ == "__main__":
    main()
