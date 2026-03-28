/**
 * Séance — Room Perception Visualization
 *
 * Renders candle nodes, sensor nodes, and signal paths on a dark canvas.
 * Connects to a WebSocket backend for live CSI data, falls back to mock data.
 *
 * Data contract (received via WebSocket JSON):
 * {
 *   "paths": {
 *     "<mac>": {
 *       "variance_ratio": 1.0,     // 1.0 = baseline, >3 = disturbed
 *       "rssi": -45,
 *       "rssi_delta": -2.1,
 *       "packets": 120,
 *       "disturbed": false,
 *       "amp_mean": 12.5,
 *       "hottest_subcarriers": [14, 22, 33]
 *     }
 *   },
 *   "meta": {
 *     "packets_per_sec": 85,
 *     "unique_macs": 6,
 *     "disturbance_count": 2,
 *     "uptime_s": 142
 *   },
 *   "narrative": "Motion detected between Yellow and the sensor."
 * }
 */

// ─── Config ──────────────────────────────────────────────────────────

const WS_URL = `ws://${location.hostname || 'localhost'}:8765`;
const RECONNECT_INTERVAL = 3000;

// Room layout — normalized 0-1 coordinates
// Update these after placing candles at the venue!
const ROOM_CONFIG = {
  candles: {
    "485519ec2f04": { id: "04", name: "Yellow",  x: 0.25, y: 0.30, color: "#DCFF00" },
    "08f9e0690c68": { id: "05", name: "Green",   x: 0.65, y: 0.25, color: "#00FF00" },
    "485519ecd18e": { id: "10", name: "Purple",  x: 0.50, y: 0.70, color: "#8000FF" },
  },
  sensors: {
    "esp32_a": { x: 0.10, y: 0.90 },
  },
};

// All 13 candles for when we scale up
const ALL_CANDLES = {
  "4c752594d210": { id: "01", name: "Red",       color: "#FF0000" },
  "08f9e0611bc7": { id: "02", name: "Orange",    color: "#FF6400" },
  "c8c9a339a907": { id: "03", name: "Gold",      color: "#FFC800" },
  "485519ec2f04": { id: "04", name: "Yellow",    color: "#DCFF00" },
  "08f9e0690c68": { id: "05", name: "Green",     color: "#00FF00" },
  "485519ef0a8d": { id: "06", name: "Teal",      color: "#00FF80" },
  "c8c9a339a779": { id: "07", name: "Cyan",      color: "#00FFFF" },
  "c8c9a338ec00": { id: "08", name: "Sky Blue",  color: "#0080FF" },
  "485519ee65c7": { id: "09", name: "Blue",      color: "#0000FF" },
  "485519ecd18e": { id: "10", name: "Purple",    color: "#8000FF" },
  "485519ecd242": { id: "11", name: "Magenta",   color: "#FF00FF" },
  "08f9e068ea07": { id: "12", name: "Rose",      color: "#FF0064" },
  "485519ec2429": { id: "13", name: "Warm White", color: "#FFB464" },
};

// Visual palette
const PALETTE = {
  bg:           "#0A0A0A",
  pathIdle:     "#1A1008",
  candleIdle:   "#FFB347",
  lowActivity:  "#FF8C00",
  medActivity:  "#FF5014",
  highActivity: "#DA70D6",
  peakActivity: "#1E90FF",
  sensorNode:   "#3A3A3A",
  text:         "#A0A0A0",
};

// ─── State ───────────────────────────────────────────────────────────

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
let W, H;
let ws = null;
let connected = false;
let lastData = null;
let animTime = 0;
let hoverTarget = null;
let mouseX = 0, mouseY = 0;

// Smoothed values for animation (keyed by mac)
const smoothed = {};

function resize() {
  const dpr = window.devicePixelRatio || 1;
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener("resize", resize);
resize();

// ─── Coordinate helpers ──────────────────────────────────────────────

function roomToScreen(nx, ny) {
  // Map 0-1 normalized room coords to screen, with padding
  const pad = 120;
  const areaW = W - pad * 2;
  const areaH = H - pad * 2;
  return {
    x: pad + nx * areaW,
    y: pad + ny * areaH,
  };
}

// ─── Drawing ─────────────────────────────────────────────────────────

function activityColor(ratio) {
  // Map variance ratio to color
  if (ratio < 1.5)  return PALETTE.pathIdle;
  if (ratio < 3.0)  return PALETTE.lowActivity;
  if (ratio < 6.0)  return PALETTE.medActivity;
  if (ratio < 12.0) return PALETTE.highActivity;
  return PALETTE.peakActivity;
}

function activityAlpha(ratio) {
  if (ratio < 1.0) return 0.08;
  if (ratio < 2.0) return 0.15 + (ratio - 1.0) * 0.15;
  if (ratio < 5.0) return 0.3 + (ratio - 2.0) * 0.1;
  return Math.min(0.9, 0.6 + (ratio - 5.0) * 0.03);
}

function drawPath(fromPos, toPos, ratio, mac) {
  const a = roomToScreen(fromPos.x, fromPos.y);
  const b = roomToScreen(toPos.x, toPos.y);

  const color = activityColor(ratio);
  const alpha = activityAlpha(ratio);
  const width = ratio < 2 ? 0.5 : Math.min(4, 0.5 + ratio * 0.3);

  // Main line
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.strokeStyle = color;
  ctx.globalAlpha = alpha;
  ctx.lineWidth = width;
  ctx.stroke();

  // Glow for active paths
  if (ratio > 2.0) {
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = color;
    ctx.globalAlpha = alpha * 0.3;
    ctx.lineWidth = width + 6;
    ctx.stroke();
  }

  // Pulse particles along disturbed paths
  if (ratio > 3.0) {
    const t = (animTime * 0.001 + mac.charCodeAt(0) * 0.1) % 1;
    const px = a.x + (b.x - a.x) * t;
    const py = a.y + (b.y - a.y) * t;
    ctx.beginPath();
    ctx.arc(px, py, 2 + ratio * 0.3, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.globalAlpha = alpha * 0.8;
    ctx.fill();
  }

  ctx.globalAlpha = 1;
}

function drawCandle(mac, config, pathData) {
  const pos = roomToScreen(config.x, config.y);
  const ratio = pathData ? (pathData.variance_ratio || 1.0) : 1.0;
  const disturbed = pathData ? pathData.disturbed : false;

  // Breathing animation
  const breathe = 1 + Math.sin(animTime * 0.002 + config.x * 10) * 0.15;

  // Base glow radius
  const glowR = disturbed ? 50 + ratio * 5 : 35;
  const coreR = disturbed ? 10 + ratio : 7;

  // Outer glow
  const gradient = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowR * breathe);
  const glowColor = disturbed ? activityColor(ratio) : config.color;
  gradient.addColorStop(0, glowColor);
  gradient.addColorStop(0.3, glowColor);
  gradient.addColorStop(1, "transparent");

  ctx.beginPath();
  ctx.arc(pos.x, pos.y, glowR * breathe, 0, Math.PI * 2);
  ctx.fillStyle = gradient;
  ctx.globalAlpha = disturbed ? 0.25 + ratio * 0.03 : 0.12 * breathe;
  ctx.fill();

  // Core circle
  ctx.beginPath();
  ctx.arc(pos.x, pos.y, coreR * breathe, 0, Math.PI * 2);
  ctx.fillStyle = disturbed ? activityColor(ratio) : config.color;
  ctx.globalAlpha = disturbed ? 0.9 : 0.5 + breathe * 0.2;
  ctx.fill();

  // Label (subtle)
  ctx.globalAlpha = 0.3;
  ctx.font = "9px SeanceUI, monospace";
  ctx.fillStyle = config.color;
  ctx.textAlign = "center";
  ctx.fillText(config.name, pos.x, pos.y + coreR * breathe + 14);

  ctx.globalAlpha = 1;
}

function drawSensor(config) {
  const pos = roomToScreen(config.x, config.y);

  ctx.beginPath();
  ctx.arc(pos.x, pos.y, 4, 0, Math.PI * 2);
  ctx.fillStyle = PALETTE.sensorNode;
  ctx.globalAlpha = 0.4;
  ctx.fill();

  ctx.globalAlpha = 0.2;
  ctx.font = "8px SeanceUI, monospace";
  ctx.fillStyle = PALETTE.sensorNode;
  ctx.textAlign = "center";
  ctx.fillText("sensor", pos.x, pos.y + 14);

  ctx.globalAlpha = 1;
}

function drawFrame(timestamp) {
  animTime = timestamp;
  ctx.clearRect(0, 0, W, H);

  const data = lastData || {};
  const paths = data.paths || {};

  // Smooth incoming values
  for (const [mac, pd] of Object.entries(paths)) {
    if (!smoothed[mac]) {
      smoothed[mac] = { variance_ratio: 1.0, rssi: -50 };
    }
    const s = smoothed[mac];
    const lerp = 0.1; // smoothing factor
    s.variance_ratio += (pd.variance_ratio - s.variance_ratio) * lerp;
    s.rssi += ((pd.rssi || -50) - s.rssi) * lerp;
  }
  // Decay paths we haven't heard from
  for (const [mac, s] of Object.entries(smoothed)) {
    if (!paths[mac]) {
      s.variance_ratio += (1.0 - s.variance_ratio) * 0.02;
    }
  }

  // Draw signal paths
  for (const [mac, candle] of Object.entries(ROOM_CONFIG.candles)) {
    for (const [sid, sensor] of Object.entries(ROOM_CONFIG.sensors)) {
      const ratio = smoothed[mac] ? smoothed[mac].variance_ratio : 1.0;
      drawPath(candle, sensor, ratio, mac);
    }
  }

  // Draw sensors
  for (const sensor of Object.values(ROOM_CONFIG.sensors)) {
    drawSensor(sensor);
  }

  // Draw candles
  for (const [mac, candle] of Object.entries(ROOM_CONFIG.candles)) {
    drawCandle(mac, candle, paths[mac] || null);
  }

  // Update stats panel
  updateStats(data);

  // Tooltip on hover
  updateTooltip();

  requestAnimationFrame(drawFrame);
}

// ─── Stats panel ─────────────────────────────────────────────────────

function updateStats(data) {
  const meta = data.meta || {};
  const paths = data.paths || {};

  document.getElementById("s-candles").textContent = Object.keys(ROOM_CONFIG.candles).length;
  document.getElementById("s-sensors").textContent = Object.keys(ROOM_CONFIG.sensors).length;
  document.getElementById("s-paths").textContent =
    Object.keys(ROOM_CONFIG.candles).length * Object.keys(ROOM_CONFIG.sensors).length;
  document.getElementById("s-pps").textContent = meta.packets_per_sec || "—";
  document.getElementById("s-macs").textContent = meta.unique_macs || "—";
  document.getElementById("s-disturb").textContent = meta.disturbance_count || "0";

  // Per-candle stats
  const container = document.getElementById("candle-stats");
  let html = "";
  for (const [mac, candle] of Object.entries(ROOM_CONFIG.candles)) {
    const pd = paths[mac];
    const sm = smoothed[mac];
    const ratio = sm ? sm.variance_ratio.toFixed(1) : "—";
    const rssi = pd ? pd.rssi : "—";
    const cls = pd && pd.disturbed ? "disturbed" : (sm && sm.variance_ratio > 1.5 ? "active" : "");
    html += `<div class="stat-row ${cls}">
      <span style="color:${candle.color}">${candle.name}</span>
      <span class="val">var=${ratio} rssi=${rssi}</span>
    </div>`;
  }
  container.innerHTML = html;

  // Narrative
  if (data.narrative) {
    const el = document.getElementById("narrative-text");
    el.textContent = data.narrative;
    el.classList.add("active");
    clearTimeout(el._fadeTimer);
    el._fadeTimer = setTimeout(() => el.classList.remove("active"), 5000);
  }
}

// ─── Hover / Tooltip ─────────────────────────────────────────────────

canvas.addEventListener("mousemove", (e) => {
  mouseX = e.clientX;
  mouseY = e.clientY;
});

function updateTooltip() {
  const tooltip = document.getElementById("tooltip");
  let found = null;

  for (const [mac, candle] of Object.entries(ROOM_CONFIG.candles)) {
    const pos = roomToScreen(candle.x, candle.y);
    const dx = mouseX - pos.x;
    const dy = mouseY - pos.y;
    if (dx * dx + dy * dy < 900) { // 30px radius
      found = { mac, candle };
      break;
    }
  }

  if (found) {
    const pd = lastData?.paths?.[found.mac] || {};
    const sm = smoothed[found.mac] || {};
    tooltip.style.display = "block";
    tooltip.style.left = (mouseX + 16) + "px";
    tooltip.style.top = (mouseY + 16) + "px";
    tooltip.innerHTML = `
      <strong style="color:${found.candle.color}">${found.candle.name}</strong> (candle ${found.candle.id})<br>
      MAC: ${found.mac}<br>
      RSSI: ${pd.rssi || "—"} dBm (Δ${pd.rssi_delta || 0})<br>
      Variance ratio: ${sm.variance_ratio?.toFixed(2) || "—"}<br>
      Packets: ${pd.packets || "—"}<br>
      ${pd.disturbed ? '<span style="color:#FF5014">⚠ DISTURBED</span>' : '<span style="color:#666">quiet</span>'}
    `;
  } else {
    tooltip.style.display = "none";
  }
}

// ─── WebSocket connection ────────────────────────────────────────────

function connectWS() {
  const connEl = document.getElementById("connection");

  try {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      connected = true;
      connEl.textContent = "● live";
      connEl.className = "conn-live";
      console.log("[seance] WebSocket connected to", WS_URL);
    };

    ws.onmessage = (event) => {
      try {
        lastData = JSON.parse(event.data);
      } catch (e) {
        console.warn("[seance] Bad JSON:", e);
      }
    };

    ws.onclose = () => {
      connected = false;
      connEl.textContent = "● reconnecting...";
      connEl.className = "conn-dead";
      console.log("[seance] WebSocket closed, reconnecting...");
      setTimeout(connectWS, RECONNECT_INTERVAL);
    };

    ws.onerror = (err) => {
      console.warn("[seance] WebSocket error:", err);
      ws.close();
    };
  } catch (e) {
    console.warn("[seance] WebSocket failed:", e);
    connEl.textContent = "● mock data";
    connEl.className = "conn-mock";
    setTimeout(connectWS, RECONNECT_INTERVAL);
  }
}

// ─── Mock data for development ───────────────────────────────────────

function generateMockData() {
  if (connected) return;

  const t = Date.now() * 0.001;
  const paths = {};

  for (const mac of Object.keys(ROOM_CONFIG.candles)) {
    // Simulate occasional disturbances with perlin-ish noise
    const wave = Math.sin(t * 0.5 + mac.charCodeAt(4) * 2) * 0.5 + 0.5;
    const spike = Math.random() < 0.02 ? 8 + Math.random() * 10 : 0;
    const ratio = 1.0 + wave * 2.5 + spike;

    paths[mac] = {
      variance_ratio: ratio,
      rssi: -45 + Math.sin(t * 0.3 + mac.charCodeAt(2)) * 8,
      rssi_delta: Math.sin(t * 0.2) * 3,
      packets: Math.floor(50 + Math.random() * 80),
      disturbed: ratio > 3.0,
      hottest_subcarriers: [14, 22, 33, 41, 8],
    };
  }

  const disturbCount = Object.values(paths).filter((p) => p.disturbed).length;

  lastData = {
    paths,
    meta: {
      packets_per_sec: Math.floor(60 + Math.random() * 40),
      unique_macs: 3 + Math.floor(Math.random() * 4),
      disturbance_count: disturbCount,
      uptime_s: Math.floor(t),
    },
    narrative: disturbCount > 0
      ? "Electromagnetic disturbance detected. The room is shifting."
      : "The candles are quiet. Ambient signals only.",
  };
}

// ─── Boot ────────────────────────────────────────────────────────────

connectWS();
setInterval(generateMockData, 200);
requestAnimationFrame(drawFrame);

console.log("[seance] Visualization started. Waiting for data on", WS_URL);
