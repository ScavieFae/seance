#!/usr/bin/env python3
"""
Seance — Snapshot Logger
Every 0.5s captures a frame from the FaceTime camera and audio features
from channels 1 & 2 of the MOTU Ultralite M6. Stores images + JSONL metadata
in data/snapshots/.
"""

import json
import os
import time
from datetime import datetime, timezone

import cv2
import numpy as np
import sounddevice as sd

# --- Config ---
AUDIO_DEVICE_NAME = "M6"
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_DURATION = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "snapshots")
LOG_FILE = os.path.join(OUTPUT_DIR, "snapshot_log.jsonl")

BANDS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 4000),
    "high": (4000, 20000),
}


def find_audio_device():
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if AUDIO_DEVICE_NAME in d["name"] and d["max_input_channels"] > 0:
            return i
    raise RuntimeError(f"Audio device '{AUDIO_DEVICE_NAME}' not found.")


def band_energy(freqs, magnitudes, low, high):
    mask = (freqs >= low) & (freqs < high)
    if not mask.any():
        return 0.0
    return float(np.mean(magnitudes[mask] ** 2))


def extract_features(audio, sample_rate):
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


def main():
    audio_device = find_audio_device()
    print(f"Audio: {sd.query_devices(audio_device)['name']} (2 channels)")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open FaceTime camera")
    print(f"Camera: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output: {OUTPUT_DIR}")
    print("Recording... (Ctrl+C to stop)\n")

    tick = 0
    with open(LOG_FILE, "a") as f:
        try:
            while True:
                # Start audio recording
                audio = sd.rec(
                    CHUNK_SAMPLES,
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    device=audio_device,
                    dtype="float32",
                )

                # Grab camera frame while audio records
                ret, frame = cap.read()

                # Wait for audio
                sd.wait()
                timestamp = datetime.now(timezone.utc).isoformat()
                ts_safe = timestamp.replace(":", "-").replace("+", "_")

                # Save image
                img_filename = f"{ts_safe}.jpg"
                img_path = os.path.join(OUTPUT_DIR, img_filename)
                if ret:
                    cv2.imwrite(img_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])

                # Extract per-channel audio features
                ch1_features = extract_features(audio[:, 0], SAMPLE_RATE)
                ch2_features = extract_features(audio[:, 1], SAMPLE_RATE)

                entry = {
                    "timestamp": timestamp,
                    "tick": tick,
                    "image": img_filename if ret else None,
                    "audio_ch1": ch1_features,
                    "audio_ch2": ch2_features,
                }

                f.write(json.dumps(entry) + "\n")
                f.flush()

                print(
                    f"#{tick:>5}  {timestamp}  "
                    f"ch1={ch1_features['db']:>7.2f}dB  "
                    f"ch2={ch2_features['db']:>7.2f}dB  "
                    f"img={'ok' if ret else 'FAIL'}"
                )

                tick += 1

        except KeyboardInterrupt:
            print(f"\nStopped after {tick} ticks.")
        finally:
            cap.release()


if __name__ == "__main__":
    main()
