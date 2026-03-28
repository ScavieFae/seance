#!/usr/bin/env python3
"""
Seance — Unified Snapshot Collector
Every 0.5s captures:
  - Camera frame (FaceTime)
  - Audio features per channel (M6 stereo: CH1=left, CH2=right)
  - CSI perception from all ESP32 sensors via Mattie's API (10.9.0.160:8000)
  - State/signal from all WLED candles
  - Active ping of one candle per tick (cycling), triggering CSI response

Serves a live dashboard at http://localhost:5001
Logs everything to data/snapshots/snapshot_log.jsonl
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError
import base64

import cv2
import numpy as np
import sounddevice as sd
from flask import Flask, jsonify, request

# --- Config ---
AUDIO_DEVICE_NAME = "M6"
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_DURATION = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "data", "snapshots")
LOG_FILE = os.path.join(OUTPUT_DIR, "snapshot_log.jsonl")

API_BASE = "http://10.9.0.160:8000"

with open(os.path.join(SCRIPT_DIR, "candles.json")) as f:
    CONFIG = json.load(f)

CANDLES = CONFIG["candles"]
CANDLE_IDS = sorted(CANDLES.keys())

BANDS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 4000),
    "high": (4000, 20000),
}

# Shared state for dashboard
latest = {
    "timestamp": None, "image_b64": None,
    "audio_ch1": None, "audio_ch2": None,
    "candles": {}, "csi": {}, "sensors": {},
    "pinged_candle": None, "tick": 0,
    "people_count": 0,
}
lock = threading.Lock()

app = Flask(__name__)


# --- Audio ---

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


# --- CSI from API ---

def fetch_csi_snapshot():
    """Pull CSI perception data from Mattie's API."""
    try:
        req = Request(f"{API_BASE}/csi/snapshot", headers={"Connection": "close"})
        with urlopen(req, timeout=1.0) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def fetch_sensors():
    """Pull sensor stats from API."""
    try:
        req = Request(f"{API_BASE}/sensors", headers={"Connection": "close"})
        with urlopen(req, timeout=1.0) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


# --- Candle polling ---

def poll_candle(candle_id, ip):
    try:
        req = Request(f"http://{ip}/json/info", headers={"Connection": "close"})
        with urlopen(req, timeout=0.8) as resp:
            info = json.loads(resp.read())

        req = Request(f"http://{ip}/json/state", headers={"Connection": "close"})
        with urlopen(req, timeout=0.8) as resp:
            state = json.loads(resp.read())

        seg = state.get("seg", [{}])[0]
        col = seg.get("col", [[0, 0, 0]])[0]
        wifi = info.get("wifi", {})
        leds = info.get("leds", {})

        return candle_id, {
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
            "online": True,
        }
    except Exception:
        return candle_id, {"online": False}


def poll_all_candles():
    results = {}
    with ThreadPoolExecutor(max_workers=13) as pool:
        futures = {
            pool.submit(poll_candle, cid, c["ip"]): cid
            for cid, c in CANDLES.items()
        }
        for future in as_completed(futures):
            cid, data = future.result()
            results[cid] = data
    return results


def ping_candle(candle_id):
    """Active echolocation: ping a candle to trigger a WiFi response packet."""
    ip = CANDLES[candle_id]["ip"]
    try:
        req = Request(f"http://{ip}/json/state", headers={"Connection": "close"})
        with urlopen(req, timeout=0.5):
            pass
        return True
    except Exception:
        return False


# --- Main capture loop ---

def capture_loop():
    audio_device = find_audio_device()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open camera")
        return

    print(f"Audio: {sd.query_devices(audio_device)['name']}")
    print(f"Camera: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"CSI API: {API_BASE}")
    print(f"Candles: {len(CANDLES)} configured")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tick = 0
    candle_ping_idx = 0

    log_f = open(LOG_FILE, "a")

    try:
        while True:
            # Which candle to ping this tick
            ping_id = CANDLE_IDS[candle_ping_idx % len(CANDLE_IDS)]
            candle_ping_idx += 1

            # Start audio recording
            audio = sd.rec(
                CHUNK_SAMPLES,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                device=audio_device,
                dtype="float32",
            )

            # While audio records: grab frame, ping candle, poll candles, fetch CSI
            ret, frame = cap.read()
            ping_ok = ping_candle(ping_id)

            # These run concurrently via threads
            with ThreadPoolExecutor(max_workers=3) as pool:
                candle_future = pool.submit(poll_all_candles)
                csi_future = pool.submit(fetch_csi_snapshot)
                sensor_future = pool.submit(fetch_sensors)

                candle_data = candle_future.result()
                csi_data = csi_future.result()
                sensor_data = sensor_future.result()

            # Wait for audio
            sd.wait()
            timestamp = datetime.now(timezone.utc).isoformat()

            ch1 = extract_features(audio[:, 0], SAMPLE_RATE)
            ch2 = extract_features(audio[:, 1], SAMPLE_RATE)

            # Encode frame
            img_b64 = None
            ts_safe = timestamp.replace(":", "-").replace("+", "_")
            img_filename = f"{ts_safe}.jpg" if ret else None
            if ret:
                cv2.imwrite(
                    os.path.join(OUTPUT_DIR, img_filename), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 80],
                )
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                img_b64 = base64.b64encode(buf).decode("ascii")

            # Build log entry
            with lock:
                people_count = latest["people_count"]

            log_entry = {
                "timestamp": timestamp,
                "tick": tick,
                "duration_s": CHUNK_DURATION,
                "people_count": people_count,
                "pinged_candle": ping_id,
                "ping_ok": ping_ok,
                "image": img_filename,
                "audio_ch1": ch1,
                "audio_ch2": ch2,
                "candles": candle_data,
                "csi": csi_data,
                "sensors": sensor_data,
            }

            log_f.write(json.dumps(log_entry) + "\n")
            log_f.flush()

            # Update dashboard state
            with lock:
                latest["timestamp"] = timestamp
                latest["image_b64"] = img_b64
                latest["audio_ch1"] = ch1
                latest["audio_ch2"] = ch2
                latest["candles"] = candle_data
                latest["csi"] = csi_data
                latest["sensors"] = sensor_data
                latest["pinged_candle"] = ping_id
                latest["tick"] = tick

            online = sum(1 for v in candle_data.values() if v.get("online"))
            n_sensors = len(sensor_data)
            total_pps = sum(s.get("pps", 0) for s in sensor_data.values())
            # Count disturbed paths across all sensors
            n_disturbed = 0
            for sensor_paths in csi_data.values():
                for path in sensor_paths.values():
                    if path.get("disturbed"):
                        n_disturbed += 1

            print(
                f"#{tick:>5}  {timestamp}  "
                f"ch1={ch1['db']:>7.2f}dB  ch2={ch2['db']:>7.2f}dB  "
                f"candles={online}/13  sensors={n_sensors}  "
                f"csi={total_pps:.0f}pps  disturbed={n_disturbed}  "
                f"ping={ping_id}{'*' if ping_ok else '!'}"
            )
            tick += 1

    except Exception as e:
        print(f"Capture error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cap.release()
        log_f.close()


# --- Flask routes ---

@app.route("/")
def index():
    return DASHBOARD_HTML


@app.route("/api/latest")
def api_latest():
    with lock:
        return jsonify(latest)


@app.route("/api/people", methods=["POST"])
def api_people():
    data = request.get_json()
    with lock:
        if "count" in data:
            latest["people_count"] = max(0, int(data["count"]))
    return jsonify({"people_count": latest["people_count"]})


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Seance — Snapshot Collector</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0A0A0A; color: #ccc; font-family: -apple-system, sans-serif; padding: 24px; }
  h1 { color: #FFB347; font-size: 20px; margin-bottom: 4px; }
  .subtitle { color: #555; font-size: 12px; margin-bottom: 20px; }
  h2 { color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }

  .top-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
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
  }

  .info-line { color: #666; font-size: 11px; margin-top: 6px; }
  .info-line .highlight { color: #FFB347; }
  .info-line .blue { color: #1E90FF; }
  .info-line .purple { color: #DA70D6; }

  .channel-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }

  .metric-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .metric {
    background: #1a1a1a;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11px;
  }
  .metric .label { color: #666; font-size: 9px; display: block; margin-bottom: 1px; }
  .metric .value { color: #FFB347; font-weight: bold; font-size: 14px; }

  .bar-chart {
    display: flex;
    align-items: flex-end;
    gap: 4px;
    height: 80px;
  }
  .bar-group { flex: 1; display: flex; flex-direction: column; align-items: center; }
  .bar { width: 100%; border-radius: 2px 2px 0 0; transition: height 0.3s ease; min-height: 1px; }
  .bar-name { font-size: 9px; color: #555; margin-top: 4px; }
  .ch1-color { background: linear-gradient(to top, #FF5014, #FF8C00); }
  .ch2-color { background: linear-gradient(to top, #1E90FF, #87CEFA); }

  .candle-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
  }
  .candle-card {
    background: #1a1a1a;
    border-radius: 6px;
    padding: 8px;
    font-size: 11px;
    border-left: 3px solid #333;
    transition: all 0.3s;
  }
  .candle-card.online { border-left-color: #FFB347; }
  .candle-card.offline { opacity: 0.3; }
  .candle-card.pinged { border-left-color: #1E90FF; box-shadow: 0 0 8px rgba(30,144,255,0.3); }
  .candle-card .name { color: #ccc; font-weight: bold; margin-bottom: 4px; }
  .candle-card .stat { color: #888; }
  .candle-card .val { color: #aaa; }
  .candle-card .disturbed { color: #DA70D6; font-weight: bold; }

  .people-counter {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    background: #141414;
    border-radius: 8px;
    padding: 12px 20px;
  }
  .people-counter h2 { margin-bottom: 0; }
  .people-counter .count-display {
    color: #FFB347;
    font-size: 36px;
    font-weight: bold;
    min-width: 60px;
    text-align: center;
  }
  .people-counter button {
    background: #1a1a1a;
    border: 1px solid #333;
    color: #ccc;
    font-size: 20px;
    width: 40px;
    height: 40px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .people-counter button:hover { background: #2a2a2a; }
  .people-counter button:active { background: #FFB347; color: #0A0A0A; }

  .sensor-row {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px;
    margin-bottom: 16px;
  }
  .sensor-card {
    background: #1a1a1a;
    border-radius: 6px;
    padding: 10px;
    border-left: 3px solid #DA70D6;
  }
  .sensor-card .name { color: #DA70D6; font-weight: bold; font-size: 12px; margin-bottom: 4px; }
  .sensor-card .stat { color: #888; font-size: 11px; }
  .sensor-card .stat .val { color: #ccc; }
</style>
</head>
<body>

<h1>Seance — Snapshot Collector</h1>
<div class="subtitle" id="status">Starting...</div>

<div class="people-counter">
  <h2>People in Room</h2>
  <button onclick="adjustPeople(-1)">−</button>
  <div class="count-display" id="people-count">0</div>
  <button onclick="adjustPeople(1)">+</button>
</div>

<div class="top-row">
  <div class="panel image-panel">
    <h2>Camera</h2>
    <div id="snapshot"><div class="placeholder-img">Waiting...</div></div>
    <div class="info-line" id="ts"></div>
  </div>

  <div class="panel">
    <h2>ESP32 Sensors (via API)</h2>
    <div class="sensor-row" id="sensor-row"></div>
    <div class="info-line">Pinged: <span class="blue" id="ping-id">—</span></div>
  </div>
</div>

<div class="channel-row">
  <div class="panel">
    <h2>Channel 1 (Left)</h2>
    <div class="metric-row" id="ch1-metrics"></div>
    <div class="bar-chart" id="ch1-bands"></div>
  </div>
  <div class="panel">
    <h2>Channel 2 (Right)</h2>
    <div class="metric-row" id="ch2-metrics"></div>
    <div class="bar-chart" id="ch2-bands"></div>
  </div>
</div>

<div class="panel" style="margin-bottom:16px">
  <h2>Candles</h2>
  <div class="candle-grid" id="candle-grid"></div>
</div>

<script>
const BAND_NAMES = ['sub_bass','bass','low_mid','mid','upper_mid','high'];
const BAND_LABELS = ['Sub','Bass','Low','Mid','Upper','High'];

function renderMetrics(id, d) {
  document.getElementById(id).innerHTML = [
    {l:'dB',v:d.db.toFixed(1)},{l:'RMS',v:d.rms.toFixed(4)},{l:'Peak',v:d.peak.toFixed(4)},
    {l:'Centroid',v:Math.round(d.spectral_centroid)+' Hz'},
    {l:'Dominant',v:Math.round(d.dominant_freq)+' Hz'},
    {l:'Rolloff',v:Math.round(d.spectral_rolloff)+' Hz'},
  ].map(m=>`<div class="metric"><span class="label">${m.l}</span><span class="value">${m.v}</span></div>`).join('');
}

function renderBands(id, bands, cls) {
  const vals = BAND_NAMES.map(b=>bands[b]||0);
  const mx = Math.max(...vals, 1e-10);
  document.getElementById(id).innerHTML = vals.map((v,i)=>{
    const h = Math.max(1,(v/mx)*70);
    return `<div class="bar-group"><div class="bar ${cls}" style="height:${h}px"></div><div class="bar-name">${BAND_LABELS[i]}</div></div>`;
  }).join('');
}

function renderSensors(sensors) {
  const el = document.getElementById('sensor-row');
  const ips = Object.keys(sensors).sort();
  if (!ips.length) { el.innerHTML = '<div class="sensor-card"><div class="name">No sensors</div></div>'; return; }
  el.innerHTML = ips.map(ip => {
    const s = sensors[ip];
    return `<div class="sensor-card">
      <div class="name">${s.label || ip}</div>
      <div class="stat">Packets: <span class="val">${s.packets?.toLocaleString() || 0}</span></div>
      <div class="stat">Rate: <span class="val">${s.pps || 0} pps</span></div>
      <div class="stat">Candles: <span class="val">${(s.candles_visible||[]).length}</span></div>
    </div>`;
  }).join('');
}

function renderCandles(candles, csi, pinged) {
  const grid = document.getElementById('candle-grid');
  const ids = Object.keys(candles).sort();

  // Build a lookup of disturbed state from CSI data
  // csi is keyed by sensor label, values are {candle_name: {disturbed, variance_ratio, ...}}
  const disturbance = {};  // candle_id -> max variance_ratio
  for (const sensorPaths of Object.values(csi || {})) {
    for (const [pathName, pathData] of Object.entries(sensorPaths)) {
      // pathName is like "Green (05)" — extract the ID
      const m = pathName.match(/\\((\\d+)\\)/);
      if (m) {
        const cid = 'candle_' + m[1];
        const prev = disturbance[cid] || 0;
        disturbance[cid] = Math.max(prev, pathData.variance_ratio || 0);
      }
    }
  }

  grid.innerHTML = ids.map(id => {
    const c = candles[id];
    const num = id.replace('candle_','');
    const cls = !c.online ? 'offline' : (id===pinged ? 'pinged' : 'online');
    const vr = disturbance[id];
    const isDisturbed = vr && vr > 3;

    let stats = '';
    if (c.online) {
      stats += `<div class="stat">sig <span class="val">${c.signal||'?'}</span></div>`;
      stats += `<div class="stat">rssi <span class="val">${c.rssi||'?'}</span></div>`;
      if (vr !== undefined) {
        stats += `<div class="stat ${isDisturbed?'disturbed':''}">var ${vr.toFixed(1)}</div>`;
      }
    } else {
      stats = '<div class="stat">offline</div>';
    }
    return `<div class="candle-card ${cls}"><div class="name">${num}</div>${stats}</div>`;
  }).join('');
}

function adjustPeople(delta) {
  const el = document.getElementById('people-count');
  const current = parseInt(el.textContent) || 0;
  const newVal = Math.max(0, current + delta);
  el.textContent = newVal;
  fetch('/api/people', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({count: newVal})
  });
}

async function poll() {
  try {
    const res = await fetch('/api/latest');
    const d = await res.json();

    if (d.image_b64) document.getElementById('snapshot').innerHTML = `<img src="data:image/jpeg;base64,${d.image_b64}">`;
    if (d.timestamp) document.getElementById('ts').textContent = d.timestamp;
    document.getElementById('status').textContent = `Tick #${d.tick}`;
    document.getElementById('ping-id').textContent = d.pinged_candle || '—';

    if (d.audio_ch1) { renderMetrics('ch1-metrics',d.audio_ch1); renderBands('ch1-bands',d.audio_ch1.bands,'ch1-color'); }
    if (d.audio_ch2) { renderMetrics('ch2-metrics',d.audio_ch2); renderBands('ch2-bands',d.audio_ch2.bands,'ch2-color'); }
    if (d.sensors) renderSensors(d.sensors);
    renderCandles(d.candles || {}, d.csi || {}, d.pinged_candle);
    if (d.people_count !== undefined) document.getElementById('people-count').textContent = d.people_count;
  } catch(e){}
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
