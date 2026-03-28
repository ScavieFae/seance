#!/usr/bin/env python3
"""
Seance — Unified Sensor Logger
Captures audio features from the MOTU Ultralite M6 and polls all WLED candles
every 0.5s. Writes timestamped JSONL for cross-modal correlation with CSI data.

Output: data/sensor_log.jsonl
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

import numpy as np
import sounddevice as sd
from scipy import signal as sig

# --- Config ---
DEVICE_NAME = "M6"
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_DURATION = 0.5  # seconds per analysis window
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "sensor_log.jsonl")

# Load candle config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "candles.json")) as f:
    CONFIG = json.load(f)

CANDLES = CONFIG["candles"]  # {"candle_01": {"ip": "10.9.3.101", ...}, ...}

# Spectral band edges (Hz)
BANDS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 4000),
    "high": (4000, 20000),
}

CANDLE_TIMEOUT = 0.4  # seconds — must finish within the 0.5s tick


def find_device():
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if DEVICE_NAME in d["name"] and d["max_input_channels"] > 0:
            return i
    raise RuntimeError(f"Audio device '{DEVICE_NAME}' not found. Available: {devices}")


def band_energy(freqs, magnitudes, low, high):
    mask = (freqs >= low) & (freqs < high)
    if not mask.any():
        return 0.0
    return float(np.mean(magnitudes[mask] ** 2))


def extract_audio_features(audio, sample_rate):
    """Extract amplitude and spectral features from a mono audio chunk."""
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    db = float(20 * np.log10(rms + 1e-10))

    n = len(audio)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    fft_mag = np.abs(np.fft.rfft(audio)) / n

    total_energy = np.sum(fft_mag)
    if total_energy > 1e-10:
        spectral_centroid = float(np.sum(freqs * fft_mag) / total_energy)
        spectral_bandwidth = float(
            np.sqrt(np.sum(((freqs - spectral_centroid) ** 2) * fft_mag) / total_energy)
        )
    else:
        spectral_centroid = 0.0
        spectral_bandwidth = 0.0

    cumulative = np.cumsum(fft_mag)
    rolloff_idx = np.searchsorted(cumulative, 0.85 * cumulative[-1])
    spectral_rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    dominant_freq = float(freqs[np.argmax(fft_mag[1:]) + 1]) if len(fft_mag) > 1 else 0.0

    bands = {name: band_energy(freqs, fft_mag, lo, hi) for name, (lo, hi) in BANDS.items()}

    return {
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "db": round(db, 2),
        "spectral_centroid": round(spectral_centroid, 2),
        "spectral_bandwidth": round(spectral_bandwidth, 2),
        "spectral_rolloff": round(spectral_rolloff, 2),
        "dominant_freq": round(dominant_freq, 2),
        "bands": {k: round(v, 8) for k, v in bands.items()},
    }


def poll_candle(candle_id, ip):
    """Poll a single candle for state and info. Returns dict or None on failure."""
    try:
        # Get info (signal, uptime, heap, power)
        req_info = Request(f"http://{ip}/json/info", headers={"Connection": "close"})
        with urlopen(req_info, timeout=CANDLE_TIMEOUT) as resp:
            info = json.loads(resp.read())

        # Get state (brightness, color, effect)
        req_state = Request(f"http://{ip}/json/state", headers={"Connection": "close"})
        with urlopen(req_state, timeout=CANDLE_TIMEOUT) as resp:
            state = json.loads(resp.read())

        seg = state.get("seg", [{}])[0]
        col = seg.get("col", [[0, 0, 0]])[0]
        wifi = info.get("wifi", {})
        leds = info.get("leds", {})

        return {
            "id": candle_id,
            "on": state.get("on"),
            "bri": state.get("bri"),
            "color": col,
            "fx": seg.get("fx", 0),
            "rssi": wifi.get("rssi"),
            "signal": wifi.get("signal"),
            "channel": wifi.get("channel"),
            "led_power": leds.get("pwr"),
            "led_fps": leds.get("fps"),
            "uptime": info.get("uptime"),
            "free_heap": info.get("freeheap"),
        }
    except Exception:
        return {"id": candle_id, "error": "unreachable"}


def poll_all_candles():
    """Poll all candles concurrently. Returns dict keyed by candle id."""
    results = {}
    with ThreadPoolExecutor(max_workers=13) as pool:
        futures = {
            pool.submit(poll_candle, cid, c["ip"]): cid
            for cid, c in CANDLES.items()
        }
        for future in as_completed(futures):
            cid = futures[future]
            results[cid] = future.result()
    return results


def main():
    device_id = find_device()
    device_info = sd.query_devices(device_id)
    print(f"Audio: {device_info['name']} (id={device_id}, {CHANNELS}ch @ {SAMPLE_RATE}Hz)")
    print(f"Candles: {len(CANDLES)} configured")
    print(f"Tick: {CHUNK_DURATION}s")
    print(f"Output: {OUTPUT_FILE}")
    print("Recording... (Ctrl+C to stop)\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    tick = 0
    with open(OUTPUT_FILE, "a") as f:
        try:
            while True:
                tick_start = time.monotonic()

                # Start audio recording (blocks for CHUNK_DURATION)
                audio = sd.rec(
                    CHUNK_SAMPLES,
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    device=device_id,
                    dtype="float32",
                )

                # Poll candles concurrently while audio records
                candle_data = poll_all_candles()

                # Wait for audio to finish
                sd.wait()
                timestamp = datetime.now(timezone.utc).isoformat()

                # Extract audio features
                mono = np.mean(audio, axis=1)
                audio_features = extract_audio_features(mono, SAMPLE_RATE)

                # Build log entry
                entry = {
                    "timestamp": timestamp,
                    "tick": tick,
                    "duration_s": CHUNK_DURATION,
                    "audio": audio_features,
                    "candles": candle_data,
                }

                f.write(json.dumps(entry) + "\n")
                f.flush()

                # Print summary
                reachable = sum(1 for c in candle_data.values() if "error" not in c)
                signals = [c["signal"] for c in candle_data.values() if "signal" in c and c["signal"] is not None]
                avg_signal = sum(signals) / len(signals) if signals else 0

                elapsed = time.monotonic() - tick_start
                print(
                    f"#{tick:>5}  {timestamp}  "
                    f"dB={audio_features['db']:>7.2f}  "
                    f"candles={reachable}/13  "
                    f"avg_signal={avg_signal:.0f}  "
                    f"tick_ms={elapsed*1000:.0f}"
                )

                tick += 1

        except KeyboardInterrupt:
            print(f"\nStopped after {tick} ticks.")


if __name__ == "__main__":
    main()
