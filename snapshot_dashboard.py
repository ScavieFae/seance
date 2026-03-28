#!/usr/bin/env python3
"""
Seance — Snapshot Dashboard
Web UI showing the latest camera snapshot alongside per-channel audio feature charts.
Predicts an image by spatially compositing past snapshots using stereo audio matching:
  CH1 (left mic) matches the left side of the frame,
  CH2 (right mic) matches the right side.
"""

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
import base64

import cv2
import numpy as np
import sounddevice as sd
from flask import Flask, jsonify

# --- Config ---
AUDIO_DEVICE_NAME = "M6"
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_DURATION = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "data", "snapshots")

LIBRARY_MAX = 500  # max snapshots to keep in memory
MIN_LIBRARY = 10   # need this many before predicting
NUM_STRIPS = 8     # vertical strips for spatial compositing
BLEND_WIDTH = 0.15 # fraction of strip width for cross-fade

BANDS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 4000),
    "high": (4000, 20000),
}
BAND_NAMES = list(BANDS.keys())

# Shared state
latest = {
    "timestamp": None, "image_b64": None,
    "audio_ch1": None, "audio_ch2": None,
    "predicted_b64": None, "library_size": 0,
}
lock = threading.Lock()

# Snapshot library: list of (ch1_vec, ch2_vec, frame_bgr)
library = deque(maxlen=LIBRARY_MAX)
lib_lock = threading.Lock()

app = Flask(__name__)


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


def features_to_vec(features):
    """Convert feature dict to numpy vector for similarity matching."""
    return np.array([
        features["db"] / 100.0,  # normalize roughly
        features["rms"] * 100,
        features["spectral_centroid"] / 10000.0,
        features["spectral_bandwidth"] / 10000.0,
        features["spectral_rolloff"] / 20000.0,
        features["dominant_freq"] / 10000.0,
    ] + [features["bands"][b] * 1e4 for b in BAND_NAMES], dtype=np.float32)


def cosine_sim(a, b):
    dot = np.dot(a, b)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return float(dot / (na * nb))


def find_best_match(query_vec, channel_idx):
    """Find the library entry whose channel best matches query_vec."""
    best_sim = -1.0
    best_idx = 0
    with lib_lock:
        for i, (ch1_vec, ch2_vec, _) in enumerate(library):
            vec = ch1_vec if channel_idx == 0 else ch2_vec
            sim = cosine_sim(query_vec, vec)
            if sim > best_sim:
                best_sim = sim
                best_idx = i
    return best_idx, best_sim


def predict_image(ch1_features, ch2_features):
    """
    Composite a predicted image from library snapshots using stereo audio matching.
    Splits the frame into vertical strips. Each strip's source image is chosen by
    blending between CH1-matched (left) and CH2-matched (right) based on horizontal
    position.
    """
    with lib_lock:
        if len(library) < MIN_LIBRARY:
            return None
        lib_snapshot = list(library)

    ch1_vec = features_to_vec(ch1_features)
    ch2_vec = features_to_vec(ch2_features)

    # Find best matches for each channel
    ch1_sims = []
    ch2_sims = []
    for ch1_v, ch2_v, _ in lib_snapshot:
        ch1_sims.append(cosine_sim(ch1_vec, ch1_v))
        ch2_sims.append(cosine_sim(ch2_vec, ch2_v))

    ch1_sims = np.array(ch1_sims)
    ch2_sims = np.array(ch2_sims)

    # Get top-K matches per channel for variety
    k = min(3, len(lib_snapshot))
    ch1_top = np.argsort(ch1_sims)[-k:][::-1]
    ch2_top = np.argsort(ch2_sims)[-k:][::-1]

    # Use the single best match per channel for now
    ch1_frame = lib_snapshot[ch1_top[0]][2]
    ch2_frame = lib_snapshot[ch2_top[0]][2]

    h, w = ch1_frame.shape[:2]
    result = np.zeros_like(ch1_frame, dtype=np.float32)

    # Composite: for each column, blend between ch1_frame and ch2_frame
    # based on horizontal position (0=left/ch1, 1=right/ch2)
    for x in range(w):
        t = x / max(w - 1, 1)  # 0.0 at left, 1.0 at right
        # Smooth blend with sigmoid-like curve
        blend = 1.0 / (1.0 + np.exp(-10 * (t - 0.5)))
        result[:, x] = (1.0 - blend) * ch1_frame[:, x].astype(np.float32) + \
                        blend * ch2_frame[:, x].astype(np.float32)

    result = np.clip(result, 0, 255).astype(np.uint8)
    _, buf = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf).decode("ascii")


def capture_loop():
    audio_device = find_audio_device()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open camera")
        return

    print(f"Audio: {sd.query_devices(audio_device)['name']}")
    print(f"Camera: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tick = 0

    try:
        while True:
            audio = sd.rec(
                CHUNK_SAMPLES,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                device=audio_device,
                dtype="float32",
            )
            ret, frame = cap.read()
            sd.wait()

            timestamp = datetime.now(timezone.utc).isoformat()
            ch1 = extract_features(audio[:, 0], SAMPLE_RATE)
            ch2 = extract_features(audio[:, 1], SAMPLE_RATE)

            # Encode current frame
            img_b64 = None
            if ret:
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                img_b64 = base64.b64encode(buf).decode("ascii")

            # Generate prediction from library before adding current frame
            predicted_b64 = predict_image(ch1, ch2)

            # Add to library
            if ret:
                ch1_vec = features_to_vec(ch1)
                ch2_vec = features_to_vec(ch2)
                with lib_lock:
                    library.append((ch1_vec, ch2_vec, frame.copy()))

            with lock:
                latest["timestamp"] = timestamp
                latest["image_b64"] = img_b64
                latest["audio_ch1"] = ch1
                latest["audio_ch2"] = ch2
                latest["predicted_b64"] = predicted_b64
                with lib_lock:
                    latest["library_size"] = len(library)

            lib_size = len(library)
            pred_status = "predicting" if predicted_b64 else f"collecting ({lib_size}/{MIN_LIBRARY})"
            print(
                f"#{tick:>5}  {timestamp}  "
                f"ch1={ch1['db']:>7.2f}dB  ch2={ch2['db']:>7.2f}dB  "
                f"lib={lib_size}  {pred_status}"
            )
            tick += 1

    except Exception as e:
        print(f"Capture error: {e}")
    finally:
        cap.release()


@app.route("/")
def index():
    return DASHBOARD_HTML


@app.route("/api/latest")
def api_latest():
    with lock:
        return jsonify(latest)


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Seance — Snapshot Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0A0A0A; color: #ccc; font-family: -apple-system, sans-serif; padding: 24px; }
  h1 { color: #FFB347; font-size: 20px; margin-bottom: 4px; }
  .subtitle { color: #555; font-size: 12px; margin-bottom: 20px; }
  h2 { color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    gap: 16px;
  }

  .panel {
    background: #141414;
    border-radius: 8px;
    padding: 16px;
    overflow: hidden;
  }

  .image-panel img {
    width: 100%;
    height: auto;
    border-radius: 4px;
    display: block;
  }

  .placeholder-img {
    width: 100%;
    aspect-ratio: 4/3;
    background: #1a1a1a;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #444;
    font-size: 14px;
    border: 1px dashed #333;
    flex-direction: column;
    gap: 8px;
  }

  .placeholder-img .count { color: #FFB347; font-size: 18px; font-weight: bold; }

  .timestamp { color: #666; font-size: 11px; margin-top: 8px; }
  .match-info { color: #555; font-size: 11px; margin-top: 4px; }

  .channel-charts {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .chart-section { margin-bottom: 16px; }
  .chart-section:last-child { margin-bottom: 0; }
  .chart-label { font-size: 11px; color: #666; margin-bottom: 6px; }

  .bar-chart {
    display: flex;
    align-items: flex-end;
    gap: 4px;
    height: 100px;
  }

  .bar-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .bar {
    width: 100%;
    border-radius: 2px 2px 0 0;
    transition: height 0.3s ease;
    min-height: 1px;
  }

  .bar-name {
    font-size: 9px;
    color: #555;
    margin-top: 4px;
    text-align: center;
  }

  .metric-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .metric {
    background: #1a1a1a;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 12px;
  }

  .metric .label { color: #666; font-size: 10px; display: block; margin-bottom: 2px; }
  .metric .value { color: #FFB347; font-weight: bold; font-size: 16px; }

  .ch1-color { background: linear-gradient(to top, #FF5014, #FF8C00); }
  .ch2-color { background: linear-gradient(to top, #1E90FF, #87CEFA); }
</style>
</head>
<body>

<h1>Seance — Snapshot Dashboard</h1>
<div class="subtitle">Stereo audio → spatial image prediction. Left channel matches left side, right channel matches right side.</div>

<div class="grid">
  <div class="panel image-panel">
    <h2>Latest Snapshot</h2>
    <div id="snapshot"><div class="placeholder-img">Waiting for data...</div></div>
    <div class="timestamp" id="ts"></div>
  </div>

  <div class="panel image-panel">
    <h2>Predicted Image (from audio)</h2>
    <div id="predicted"><div class="placeholder-img">Building library...<div class="count" id="lib-count">0</div></div></div>
    <div class="match-info" id="match-info"></div>
  </div>

  <div class="channel-charts">
    <div class="panel" id="ch1-panel">
      <h2>Channel 1 (Left)</h2>
      <div class="metric-row" id="ch1-metrics"></div>
      <div class="chart-section">
        <div class="chart-label">Band Energy</div>
        <div class="bar-chart" id="ch1-bands"></div>
      </div>
    </div>

    <div class="panel" id="ch2-panel">
      <h2>Channel 2 (Right)</h2>
      <div class="metric-row" id="ch2-metrics"></div>
      <div class="chart-section">
        <div class="chart-label">Band Energy</div>
        <div class="bar-chart" id="ch2-bands"></div>
      </div>
    </div>
  </div>
</div>

<script>
const BAND_NAMES = ['sub_bass', 'bass', 'low_mid', 'mid', 'upper_mid', 'high'];
const BAND_LABELS = ['Sub', 'Bass', 'Low', 'Mid', 'Upper', 'High'];

function renderMetrics(containerId, data) {
  const el = document.getElementById(containerId);
  const metrics = [
    { label: 'dB', value: data.db.toFixed(1) },
    { label: 'RMS', value: data.rms.toFixed(4) },
    { label: 'Peak', value: data.peak.toFixed(4) },
    { label: 'Centroid', value: Math.round(data.spectral_centroid) + ' Hz' },
    { label: 'Dominant', value: Math.round(data.dominant_freq) + ' Hz' },
    { label: 'Rolloff', value: Math.round(data.spectral_rolloff) + ' Hz' },
  ];
  el.innerHTML = metrics.map(m =>
    `<div class="metric"><span class="label">${m.label}</span><span class="value">${m.value}</span></div>`
  ).join('');
}

function renderBands(containerId, bands, cssClass) {
  const el = document.getElementById(containerId);
  const values = BAND_NAMES.map(b => bands[b] || 0);
  const maxVal = Math.max(...values, 1e-10);
  el.innerHTML = values.map((v, i) => {
    const h = Math.max(1, (v / maxVal) * 90);
    return `<div class="bar-group">
      <div class="bar ${cssClass}" style="height:${h}px"></div>
      <div class="bar-name">${BAND_LABELS[i]}</div>
    </div>`;
  }).join('');
}

async function poll() {
  try {
    const res = await fetch('/api/latest');
    const data = await res.json();

    if (data.image_b64) {
      document.getElementById('snapshot').innerHTML =
        `<img src="data:image/jpeg;base64,${data.image_b64}">`;
    }
    if (data.timestamp) {
      document.getElementById('ts').textContent = data.timestamp;
    }

    if (data.predicted_b64) {
      document.getElementById('predicted').innerHTML =
        `<img src="data:image/jpeg;base64,${data.predicted_b64}">`;
      document.getElementById('match-info').textContent =
        `Library: ${data.library_size} snapshots`;
    } else {
      document.getElementById('predicted').innerHTML =
        `<div class="placeholder-img">Building library...<div class="count">${data.library_size || 0} / 10</div></div>`;
    }

    if (data.audio_ch1) {
      renderMetrics('ch1-metrics', data.audio_ch1);
      renderBands('ch1-bands', data.audio_ch1.bands, 'ch1-color');
    }
    if (data.audio_ch2) {
      renderMetrics('ch2-metrics', data.audio_ch2);
      renderBands('ch2-bands', data.audio_ch2.bands, 'ch2-color');
    }
  } catch(e) {}
  setTimeout(poll, 600);
}

poll();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    capturer = threading.Thread(target=capture_loop, daemon=True)
    capturer.start()

    print("Dashboard: http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
