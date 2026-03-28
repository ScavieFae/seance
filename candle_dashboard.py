#!/usr/bin/env python3
"""
Seance — Candle Brightness Dashboard
Web UI with signal/brightness bar charts and magnitude/bias sliders.
Continuously polls candles and adjusts brightness based on inverse signal strength.
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request

from flask import Flask, jsonify, request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "candles.json")) as f:
    CONFIG = json.load(f)

CANDLES = CONFIG["candles"]
POLL_INTERVAL = 0.5
SIGNAL_MIN = 40
SIGNAL_MAX = 100

# Shared state
candle_state = {}
settings = {"magnitude": 1.0, "bias": 0.0}  # magnitude 0-2, bias -1 to 1
state_lock = threading.Lock()

app = Flask(__name__)


def update_candle(candle_id, ip, mag, bias):
    try:
        req = Request(f"http://{ip}/json/info", headers={"Connection": "close"})
        with urlopen(req, timeout=0.8) as resp:
            info = json.loads(resp.read())
        signal = info.get("wifi", {}).get("signal", 0)

        normalized = max(0.0, min(1.0, (signal - SIGNAL_MIN) / (SIGNAL_MAX - SIGNAL_MIN)))
        # Apply magnitude and bias: invert, scale by magnitude, shift by bias
        adjusted = (1.0 - normalized) * mag + bias
        adjusted = max(0.0, min(1.0, adjusted))
        bri = max(1, min(255, int(adjusted * 255)))

        payload = json.dumps({"bri": bri}).encode()
        req = Request(
            f"http://{ip}/json/state",
            data=payload,
            headers={"Content-Type": "application/json", "Connection": "close"},
            method="POST",
        )
        with urlopen(req, timeout=0.8):
            pass

        return candle_id, {"signal": signal, "brightness": bri, "online": True}
    except Exception:
        return candle_id, {"signal": 0, "brightness": 0, "online": False}


def poll_loop():
    global candle_state
    while True:
        with state_lock:
            mag = settings["magnitude"]
            bias = settings["bias"]

        with ThreadPoolExecutor(max_workers=13) as pool:
            futures = {
                pool.submit(update_candle, cid, c["ip"], mag, bias): cid
                for cid, c in CANDLES.items()
            }
            results = {}
            for future in as_completed(futures):
                cid, data = future.result()
                results[cid] = data

        with state_lock:
            candle_state = results

        online = sum(1 for v in results.values() if v["online"])
        print(f"tick: {online}/13 online  mag={mag:.2f}  bias={bias:.2f}")
        time.sleep(POLL_INTERVAL)


@app.route("/")
def index():
    return DASHBOARD_HTML


@app.route("/api/state")
def api_state():
    with state_lock:
        return jsonify({"candles": candle_state, "settings": settings})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json()
    with state_lock:
        if "magnitude" in data:
            settings["magnitude"] = float(data["magnitude"])
        if "bias" in data:
            settings["bias"] = float(data["bias"])
    return jsonify({"ok": True})


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Seance — Candle Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0A0A0A; color: #ccc; font-family: -apple-system, sans-serif; padding: 24px; }
  h1 { color: #FFB347; font-size: 20px; margin-bottom: 20px; }
  .controls { display: flex; gap: 40px; margin-bottom: 30px; padding: 16px; background: #141414; border-radius: 8px; }
  .slider-group { flex: 1; }
  .slider-group label { display: block; font-size: 13px; color: #888; margin-bottom: 6px; }
  .slider-group .value { color: #FFB347; font-weight: bold; }
  input[type=range] { width: 100%; accent-color: #FFB347; }
  .chart { display: flex; align-items: flex-end; gap: 8px; height: 350px; padding: 16px; background: #141414; border-radius: 8px; }
  .candle-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
  .bars { display: flex; gap: 3px; align-items: flex-end; height: 280px; }
  .bar { width: 24px; border-radius: 3px 3px 0 0; transition: height 0.3s ease; position: relative; }
  .bar-signal { background: linear-gradient(to top, #FF8C00, #FFB347); }
  .bar-brightness { background: linear-gradient(to top, #1E90FF, #87CEFA); }
  .candle-label { font-size: 11px; color: #888; margin-top: 6px; text-align: center; line-height: 1.3; }
  .candle-label .name { color: #ccc; font-weight: bold; }
  .bar-val { font-size: 10px; color: #aaa; text-align: center; margin-top: 2px; }
  .offline { opacity: 0.25; }
  .legend { display: flex; gap: 20px; margin-top: 12px; font-size: 12px; color: #888; }
  .legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
  .legend-signal { background: #FFB347; }
  .legend-brightness { background: #87CEFA; }
</style>
</head>
<body>

<h1>Seance — Candle Dashboard</h1>

<div class="controls">
  <div class="slider-group">
    <label>Magnitude <span class="value" id="mag-val">1.00</span></label>
    <input type="range" id="magnitude" min="0" max="2" step="0.01" value="1.0">
  </div>
  <div class="slider-group">
    <label>Bias <span class="value" id="bias-val">0.00</span></label>
    <input type="range" id="bias" min="-1" max="1" step="0.01" value="0.0">
  </div>
</div>

<div class="chart" id="chart"></div>
<div class="legend">
  <span><span class="legend-dot legend-signal"></span>Signal Strength</span>
  <span><span class="legend-dot legend-brightness"></span>Brightness</span>
</div>

<script>
const CANDLE_COLORS = {
  candle_01: '#FF0000', candle_02: '#FF6400', candle_03: '#FFC800',
  candle_04: '#DCFF00', candle_05: '#00FF00', candle_06: '#00FF80',
  candle_07: '#00FFFF', candle_08: '#0080FF', candle_09: '#0000FF',
  candle_10: '#8000FF', candle_11: '#FF00FF', candle_12: '#FF0064',
  candle_13: '#FFB464'
};

const CANDLE_NAMES = {
  candle_01: 'Red', candle_02: 'Orange', candle_03: 'Gold',
  candle_04: 'Yellow', candle_05: 'Green', candle_06: 'Teal',
  candle_07: 'Cyan', candle_08: 'Sky Blue', candle_09: 'Blue',
  candle_10: 'Purple', candle_11: 'Magenta', candle_12: 'Rose',
  candle_13: 'Warm Wht'
};

const chart = document.getElementById('chart');
const magSlider = document.getElementById('magnitude');
const biasSlider = document.getElementById('bias');
const magVal = document.getElementById('mag-val');
const biasVal = document.getElementById('bias-val');

function sendSettings() {
  fetch('/api/settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      magnitude: parseFloat(magSlider.value),
      bias: parseFloat(biasSlider.value)
    })
  });
}

magSlider.addEventListener('input', () => { magVal.textContent = parseFloat(magSlider.value).toFixed(2); sendSettings(); });
biasSlider.addEventListener('input', () => { biasVal.textContent = parseFloat(biasSlider.value).toFixed(2); sendSettings(); });

function render(candles) {
  const ids = Object.keys(candles).sort();
  chart.innerHTML = '';
  for (const id of ids) {
    const c = candles[id];
    const num = id.replace('candle_', '');
    const sigH = (c.signal / 100) * 280;
    const briH = (c.brightness / 255) * 280;
    const offline = !c.online;

    const col = document.createElement('div');
    col.className = 'candle-col' + (offline ? ' offline' : '');

    col.innerHTML = `
      <div class="bars">
        <div>
          <div class="bar bar-signal" style="height:${sigH}px"></div>
          <div class="bar-val">${c.signal}</div>
        </div>
        <div>
          <div class="bar bar-brightness" style="height:${briH}px"></div>
          <div class="bar-val">${c.brightness}</div>
        </div>
      </div>
      <div class="candle-label">
        <div class="name">${num}</div>
        <div>${CANDLE_NAMES[id] || ''}</div>
      </div>
    `;
    chart.appendChild(col);
  }
}

async function poll() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    render(data.candles);
    magSlider.value = data.settings.magnitude;
    biasSlider.value = data.settings.bias;
    magVal.textContent = data.settings.magnitude.toFixed(2);
    biasVal.textContent = data.settings.bias.toFixed(2);
  } catch(e) {}
  setTimeout(poll, 600);
}

poll();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    poller = threading.Thread(target=poll_loop, daemon=True)
    poller.start()
    print("Dashboard: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
