#!/usr/bin/env python3
"""
Seance — CSI Experiment Runner
Quick experiments to characterize signal paths and disturbances.

Experiments:
  1. passive    — Just listen, log what we see without touching anything
  2. ping_sweep — Ping each room candle one at a time, measure CSI response
  3. echo       — Rapid-fire ping one candle, build high-res amplitude profile
  4. baseline   — Collect calm-room baseline for all paths (nobody move!)
  5. snapshot   — Take a 5s snapshot and dump per-path stats immediately
"""

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

SERIAL_PORT = "/dev/cu.usbserial-1110"
BAUD_RATE = 921600
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csi")

ROOM_CANDLES = {
    "485519ec2f04": {"name": "Yellow",  "ip": "10.9.3.104"},
    "08f9e0690c68": {"name": "Green",   "ip": "10.9.3.105"},
    "485519ecd18e": {"name": "Purple",  "ip": "10.9.3.110"},
}

CSI_PADDING_PAIRS = 6


def _override_port(port):
    global SERIAL_PORT
    SERIAL_PORT = port


def parse_csi(line):
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

        return {"mac": mac, "rssi": rssi, "amplitudes": amplitudes,
                "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception:
        return None


def open_serial():
    try:
        return serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
    except serial.SerialException as e:
        print(f"Cannot open {SERIAL_PORT}: {e}")
        sys.exit(1)


def collect_for(ser, duration, label="collecting"):
    """Collect CSI packets for a fixed duration. Returns list of parsed packets."""
    packets = []
    start = time.time()
    while time.time() - start < duration:
        line = ser.readline()
        if not line:
            continue
        try:
            line = line.decode("utf-8", errors="replace").strip()
        except UnicodeDecodeError:
            continue
        p = parse_csi(line)
        if p:
            packets.append(p)
    return packets


def ping_candle(ip):
    try:
        requests.get(f"http://{ip}/json/state", timeout=1)
    except requests.RequestException:
        pass


def save_experiment(name, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(DATA_DIR, f"exp_{name}_{ts}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved: {path}")
    return path


def stats_for_mac(packets, mac):
    """Compute stats for a single MAC from a packet list."""
    mac_pkts = [p for p in packets if p["mac"] == mac]
    if not mac_pkts:
        return None
    rssis = [p["rssi"] for p in mac_pkts]
    amps = np.array([p["amplitudes"] for p in mac_pkts])
    return {
        "mac": mac,
        "name": ROOM_CANDLES.get(mac, {}).get("name", "unknown"),
        "count": len(mac_pkts),
        "rssi_mean": round(float(np.mean(rssis)), 1),
        "rssi_std": round(float(np.std(rssis)), 2),
        "rssi_range": [int(np.min(rssis)), int(np.max(rssis))],
        "amp_mean_per_sc": [round(float(x), 2) for x in np.mean(amps, axis=0)],
        "amp_var_per_sc": [round(float(x), 2) for x in np.var(amps, axis=0)],
        "amp_overall_mean": round(float(np.mean(amps)), 2),
        "amp_max_variance": round(float(np.max(np.var(amps, axis=0))), 2),
        "hottest_subcarriers": [int(i) for i in np.argsort(np.var(amps, axis=0))[-5:][::-1]],
    }


# ─── Experiments ──────────────────────────────────────────────────────

def exp_passive(duration=10):
    """Just listen. Don't touch anything. See what we hear."""
    print(f"\n  EXPERIMENT: passive ({duration}s)")
    print(f"  Just listening to ambient WiFi CSI...\n")
    ser = open_serial()
    packets = collect_for(ser, duration, "passive")
    ser.close()

    macs = defaultdict(int)
    for p in packets:
        macs[p["mac"]] += 1

    print(f"  Collected {len(packets)} packets from {len(macs)} unique MACs:\n")
    for mac, count in sorted(macs.items(), key=lambda x: -x[1]):
        name = ROOM_CANDLES.get(mac, {}).get("name", f"?:{mac[-6:]}")
        rssis = [p["rssi"] for p in packets if p["mac"] == mac]
        print(f"    {name:15s} ({mac})  pkts={count:>4}  RSSI mean={np.mean(rssis):.1f}")

    results = {
        "experiment": "passive",
        "duration": duration,
        "total_packets": len(packets),
        "unique_macs": len(macs),
        "mac_counts": dict(macs),
        "per_mac_stats": {mac: stats_for_mac(packets, mac) for mac in macs},
    }
    save_experiment("passive", results)
    return results


def exp_ping_sweep(rounds=3, pause=2):
    """Ping each room candle individually, see how CSI responds."""
    print(f"\n  EXPERIMENT: ping_sweep ({rounds} rounds)")
    print(f"  Pinging each candle individually to characterize signal paths...\n")
    ser = open_serial()
    results = {"experiment": "ping_sweep", "rounds": []}

    for r in range(rounds):
        round_data = {"round": r + 1, "candles": {}}
        for mac, info in ROOM_CANDLES.items():
            name = info["name"]
            ip = info["ip"]

            # Collect quiet baseline for 2s
            print(f"  Round {r+1}/{rounds}: Quiet baseline (2s)...")
            quiet = collect_for(ser, 2)

            # Ping the candle 10 times rapidly while collecting
            print(f"  Round {r+1}/{rounds}: Pinging {name} ({ip})...")
            ping_start = time.time()
            for _ in range(10):
                ping_candle(ip)
                time.sleep(0.1)
            active = collect_for(ser, pause)

            q_stats = stats_for_mac(quiet, mac)
            a_stats = stats_for_mac(active, mac)

            round_data["candles"][name] = {
                "mac": mac,
                "quiet": q_stats,
                "after_ping": a_stats,
            }

            if q_stats and a_stats:
                print(f"    {name}: quiet RSSI={q_stats['rssi_mean']}, "
                      f"after_ping RSSI={a_stats['rssi_mean']}, "
                      f"quiet_var={q_stats['amp_max_variance']:.1f}, "
                      f"ping_var={a_stats['amp_max_variance']:.1f}")
            else:
                print(f"    {name}: insufficient data (quiet={q_stats is not None}, active={a_stats is not None})")

        results["rounds"].append(round_data)

    ser.close()
    save_experiment("ping_sweep", results)
    return results


def exp_echo(target="Yellow", count=50, gap=0.05):
    """Rapid-fire ping one candle to build high-resolution amplitude profile."""
    mac = None
    ip = None
    for m, info in ROOM_CANDLES.items():
        if info["name"].lower() == target.lower():
            mac, ip = m, info["ip"]
            break
    if not mac:
        print(f"  Unknown candle: {target}")
        return

    print(f"\n  EXPERIMENT: echo — {count} rapid pings to {target} ({ip})")
    ser = open_serial()

    # Pre-ping baseline
    print(f"  Collecting 3s baseline...")
    baseline = collect_for(ser, 3)

    # Rapid ping burst
    print(f"  Firing {count} pings at {gap}s intervals...")
    ping_start = time.time()
    for i in range(count):
        ping_candle(ip)
        time.sleep(gap)
    ping_duration = time.time() - ping_start

    # Collect response
    response = collect_for(ser, 3)

    ser.close()

    b_stats = stats_for_mac(baseline, mac)
    r_stats = stats_for_mac(response, mac)

    print(f"\n  Ping burst took {ping_duration:.1f}s")
    if b_stats:
        print(f"  Baseline:  {b_stats['count']} pkts, RSSI={b_stats['rssi_mean']}, max_var={b_stats['amp_max_variance']:.1f}")
    if r_stats:
        print(f"  Response:  {r_stats['count']} pkts, RSSI={r_stats['rssi_mean']}, max_var={r_stats['amp_max_variance']:.1f}")

    results = {
        "experiment": "echo",
        "target": target,
        "pings": count,
        "gap": gap,
        "baseline": b_stats,
        "response": r_stats,
    }
    save_experiment("echo", results)
    return results


def exp_snapshot(duration=5):
    """Quick snapshot — collect and dump everything immediately."""
    print(f"\n  EXPERIMENT: snapshot ({duration}s)")
    print(f"  Quick capture and dump...\n")
    ser = open_serial()
    packets = collect_for(ser, duration)
    ser.close()

    macs = set(p["mac"] for p in packets)
    print(f"  {len(packets)} packets from {len(macs)} MACs in {duration}s\n")

    all_stats = {}
    for mac in macs:
        s = stats_for_mac(packets, mac)
        if s:
            all_stats[mac] = s
            name = s["name"] if s["name"] != "unknown" else f"?:{mac[-6:]}"
            print(f"  {name:15s}  pkts={s['count']:>4}  RSSI={s['rssi_mean']:>5.1f}±{s['rssi_std']:.1f}  "
                  f"amp={s['amp_overall_mean']:>5.1f}  max_var={s['amp_max_variance']:>6.1f}  "
                  f"hot_sc={s['hottest_subcarriers'][:3]}")

    # Dump raw amplitude heatmap data for room candles
    print(f"\n  Per-subcarrier amplitude (room candles):")
    for mac in ROOM_CANDLES:
        if mac in all_stats:
            s = all_stats[mac]
            amps = s["amp_mean_per_sc"]
            # Simple ASCII sparkline
            if amps:
                mx = max(amps) if max(amps) > 0 else 1
                bars = "".join("▁▂▃▄▅▆▇█"[min(int(a / mx * 7), 7)] for a in amps[:52])
                print(f"    {s['name']:10s}: {bars}")

    results = {"experiment": "snapshot", "duration": duration,
               "total_packets": len(packets), "stats": all_stats}
    save_experiment("snapshot", results)
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seance CSI Experiments")
    parser.add_argument("experiment", choices=["passive", "ping_sweep", "echo", "snapshot", "all"],
                        help="Which experiment to run")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    parser.add_argument("--target", type=str, default="Yellow", help="Target candle for echo")
    parser.add_argument("--port", type=str, default=SERIAL_PORT)
    args = parser.parse_args()

    if args.port != SERIAL_PORT:
        _override_port(args.port)

    if args.experiment == "passive":
        exp_passive(args.duration)
    elif args.experiment == "ping_sweep":
        exp_ping_sweep()
    elif args.experiment == "echo":
        exp_echo(target=args.target)
    elif args.experiment == "snapshot":
        exp_snapshot(args.duration)
    elif args.experiment == "all":
        print("Running all experiments in sequence...\n")
        exp_snapshot(5)
        print("\n" + "="*70 + "\n")
        exp_passive(10)
        print("\n" + "="*70 + "\n")
        exp_echo("Yellow")
        print("\n" + "="*70 + "\n")
        exp_echo("Green")
        print("\n" + "="*70 + "\n")
        exp_echo("Purple")
        print("\n" + "="*70 + "\n")
        exp_ping_sweep()


if __name__ == "__main__":
    main()
