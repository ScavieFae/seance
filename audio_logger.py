#!/usr/bin/env python3
"""
Seance — Audio Feature Logger
Captures audio from the MOTU Ultralite M6 and logs timestamped amplitude
and spectral features as JSONL for cross-modal correlation with CSI data.

Output: data/audio/audio_features.jsonl
"""

import json
import os
import time
from datetime import datetime, timezone

import numpy as np
import sounddevice as sd
from scipy import signal as sig

# --- Config ---
DEVICE_NAME = "M6"
SAMPLE_RATE = 44100
CHANNELS = 2          # stereo pair from M6 (inputs 1-2). Adjust if needed.
CHUNK_DURATION = 0.5  # seconds per analysis window
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "audio")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "audio_features.jsonl")

# Spectral band edges (Hz)
BANDS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 4000),
    "high": (4000, 20000),
}


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


def extract_features(audio, sample_rate):
    """Extract amplitude and spectral features from a mono audio chunk."""
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    db = float(20 * np.log10(rms + 1e-10))

    # FFT
    n = len(audio)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    fft_mag = np.abs(np.fft.rfft(audio)) / n

    # Spectral centroid
    total_energy = np.sum(fft_mag)
    if total_energy > 1e-10:
        spectral_centroid = float(np.sum(freqs * fft_mag) / total_energy)
    else:
        spectral_centroid = 0.0

    # Spectral bandwidth
    if total_energy > 1e-10:
        spectral_bandwidth = float(
            np.sqrt(np.sum(((freqs - spectral_centroid) ** 2) * fft_mag) / total_energy)
        )
    else:
        spectral_bandwidth = 0.0

    # Spectral rolloff (85%)
    cumulative = np.cumsum(fft_mag)
    rolloff_idx = np.searchsorted(cumulative, 0.85 * cumulative[-1])
    spectral_rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    # Dominant frequency
    dominant_freq = float(freqs[np.argmax(fft_mag[1:]) + 1]) if len(fft_mag) > 1 else 0.0

    # Band energies
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
    device_id = find_device()
    device_info = sd.query_devices(device_id)
    print(f"Using device: {device_info['name']} (id={device_id}, {CHANNELS}ch @ {SAMPLE_RATE}Hz)")
    print(f"Chunk duration: {CHUNK_DURATION}s ({CHUNK_SAMPLES} samples)")
    print(f"Output: {OUTPUT_FILE}")
    print("Recording... (Ctrl+C to stop)\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, "a") as f:
        try:
            while True:
                # Record one chunk
                audio = sd.rec(
                    CHUNK_SAMPLES,
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    device=device_id,
                    dtype="float32",
                )
                sd.wait()

                timestamp = datetime.now(timezone.utc).isoformat()

                # Mix to mono for feature extraction
                mono = np.mean(audio, axis=1)

                features = extract_features(mono, SAMPLE_RATE)
                features["timestamp"] = timestamp
                features["duration_s"] = CHUNK_DURATION

                line = json.dumps(features)
                f.write(line + "\n")
                f.flush()

                # Print summary
                print(
                    f"{timestamp}  "
                    f"dB={features['db']:>7.2f}  "
                    f"peak={features['peak']:.4f}  "
                    f"centroid={features['spectral_centroid']:>8.1f}Hz  "
                    f"dominant={features['dominant_freq']:>8.1f}Hz"
                )

        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
