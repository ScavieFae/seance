/**
 * Séance — 3D Room Visualization
 *
 * Three.js scene: a wireframe room with glowing candle spheres,
 * sensor nodes, and signal path lines. Rotatable like the Project
 * Backbone globe. Dark aesthetic, bioluminescent glow.
 *
 * Uses the same WebSocket data contract as seance-viz.js.
 */

import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js";

// ─── Config ──────────────────────────────────────────────────────────

const WS_URL = `ws://${location.hostname || "localhost"}:8765`;
const RECONNECT_INTERVAL = 3000;

// Room dimensions in meters (approximate hackathon room)
const ROOM = { width: 8, depth: 6, height: 3 };

// Candle positions in room coordinates (meters from corner)
// Update these after placing candles at the venue!
const CANDLES = {
  "485519ec2f04": { id: "04", name: "Yellow",  x: 2.0, y: 0.8, z: 1.8, color: 0xdcff00 },
  "08f9e0690c68": { id: "05", name: "Green",   x: 5.2, y: 0.8, z: 1.5, color: 0x00ff00 },
  "485519ecd18e": { id: "10", name: "Purple",  x: 4.0, y: 0.8, z: 4.2, color: 0x8000ff },
};

const SENSORS = {
  esp32_a: { x: 0.8, y: 1.2, z: 5.4 },
};

const PALETTE = {
  bg:          0x0a0a0a,
  roomWire:    0x1a1a1a,
  roomEdge:    0x2a2018,
  floor:       0x0f0e0c,
  pathIdle:    0x1a1008,
  lowActivity: 0xff8c00,
  medActivity: 0xff5014,
  highActivity:0xda70d6,
  peakActivity:0x1e90ff,
  sensorNode:  0x3a3a3a,
  candleIdle:  0xffb347,
};

// ─── State ───────────────────────────────────────────────────────────

let scene, camera, renderer, controls;
let roomGroup;
let candleMeshes = {};   // mac -> { sphere, glow, light, label }
let sensorMeshes = {};
let pathLines = {};      // mac -> { line, glowLine }
let lastData = null;
let connected = false;
let ws = null;
const smoothed = {};
const clock = new THREE.Clock();

// ─── Scene Setup ─────────────────────────────────────────────────────

function init() {
  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setClearColor(PALETTE.bg);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  document.getElementById("canvas3d").appendChild(renderer.domElement);

  // Scene
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(PALETTE.bg, 0.02);

  // Camera
  camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(12, 8, 12);
  camera.lookAt(ROOM.width / 2, ROOM.height / 2, ROOM.depth / 2);

  // Orbit controls — full 3-axis rotation like the globe
  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(ROOM.width / 2, ROOM.height / 2, ROOM.depth / 2);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.rotateSpeed = 0.5;
  controls.zoomSpeed = 0.8;
  controls.minDistance = 2;
  controls.maxDistance = 40;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.3;
  // Unlock full rotation — no polar angle clamp
  controls.minPolarAngle = 0;
  controls.maxPolarAngle = Math.PI;
  // Enable panning in screen space (all axes)
  controls.enablePan = true;
  controls.screenSpacePanning = true;

  // Ambient light (very dim — most light comes from candles)
  const ambient = new THREE.AmbientLight(0x111111, 0.5);
  scene.add(ambient);

  // Room group — everything inside
  roomGroup = new THREE.Group();
  scene.add(roomGroup);

  buildRoom();
  buildCandles();
  buildSensors();
  buildPaths();

  window.addEventListener("resize", onResize);

  // Stop auto-rotate on interaction
  renderer.domElement.addEventListener("pointerdown", () => {
    controls.autoRotate = false;
  });
}

function buildRoom() {
  const w = ROOM.width, h = ROOM.height, d = ROOM.depth;

  // Floor — subtle grid
  const floorGeo = new THREE.PlaneGeometry(w, d, 16, 12);
  const floorMat = new THREE.MeshBasicMaterial({
    color: PALETTE.floor,
    wireframe: true,
    transparent: true,
    opacity: 0.15,
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(w / 2, 0, d / 2);
  roomGroup.add(floor);

  // Solid dark floor plane
  const floorSolidGeo = new THREE.PlaneGeometry(w, d);
  const floorSolidMat = new THREE.MeshBasicMaterial({
    color: PALETTE.bg,
    side: THREE.DoubleSide,
  });
  const floorSolid = new THREE.Mesh(floorSolidGeo, floorSolidMat);
  floorSolid.rotation.x = -Math.PI / 2;
  floorSolid.position.set(w / 2, -0.01, d / 2);
  roomGroup.add(floorSolid);

  // Room wireframe edges
  const edgesGeo = new THREE.BoxGeometry(w, h, d);
  const edgesMat = new THREE.LineBasicMaterial({
    color: PALETTE.roomEdge,
    transparent: true,
    opacity: 0.3,
  });
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(edgesGeo),
    edgesMat
  );
  edges.position.set(w / 2, h / 2, d / 2);
  roomGroup.add(edges);

  // Corner markers — subtle dots at each room corner
  const cornerGeo = new THREE.SphereGeometry(0.04, 8, 8);
  const cornerMat = new THREE.MeshBasicMaterial({ color: PALETTE.roomEdge, transparent: true, opacity: 0.5 });
  for (const cx of [0, w]) {
    for (const cy of [0, h]) {
      for (const cz of [0, d]) {
        const dot = new THREE.Mesh(cornerGeo, cornerMat);
        dot.position.set(cx, cy, cz);
        roomGroup.add(dot);
      }
    }
  }
}

function buildCandles() {
  for (const [mac, candle] of Object.entries(CANDLES)) {
    // Inner core sphere
    const sphereGeo = new THREE.SphereGeometry(0.12, 16, 16);
    const sphereMat = new THREE.MeshBasicMaterial({ color: candle.color });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    sphere.position.set(candle.x, candle.y, candle.z);
    roomGroup.add(sphere);

    // Outer glow sphere
    const glowGeo = new THREE.SphereGeometry(0.4, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({
      color: candle.color,
      transparent: true,
      opacity: 0.08,
      depthWrite: false,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    glow.position.copy(sphere.position);
    roomGroup.add(glow);

    // Point light from candle
    const light = new THREE.PointLight(candle.color, 0.5, 4, 2);
    light.position.copy(sphere.position);
    roomGroup.add(light);

    // Label sprite
    const label = makeTextSprite(candle.name, candle.color);
    label.position.set(candle.x, candle.y + 0.35, candle.z);
    roomGroup.add(label);

    candleMeshes[mac] = { sphere, glow, light, label, config: candle };
  }
}

function buildSensors() {
  for (const [sid, sensor] of Object.entries(SENSORS)) {
    const geo = new THREE.OctahedronGeometry(0.08, 0);
    const mat = new THREE.MeshBasicMaterial({
      color: PALETTE.sensorNode,
      transparent: true,
      opacity: 0.6,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(sensor.x, sensor.y, sensor.z);
    roomGroup.add(mesh);

    const label = makeTextSprite("sensor", PALETTE.sensorNode);
    label.position.set(sensor.x, sensor.y + 0.25, sensor.z);
    roomGroup.add(label);

    sensorMeshes[sid] = { mesh, config: sensor };
  }
}

function buildPaths() {
  for (const [mac, candle] of Object.entries(CANDLES)) {
    for (const [sid, sensor] of Object.entries(SENSORS)) {
      const points = [
        new THREE.Vector3(candle.x, candle.y, candle.z),
        new THREE.Vector3(sensor.x, sensor.y, sensor.z),
      ];
      const geo = new THREE.BufferGeometry().setFromPoints(points);

      // Thin idle line
      const mat = new THREE.LineBasicMaterial({
        color: PALETTE.pathIdle,
        transparent: true,
        opacity: 0.15,
      });
      const line = new THREE.Line(geo, mat);
      roomGroup.add(line);

      // Glow line (thicker, invisible until disturbed)
      const glowMat = new THREE.LineBasicMaterial({
        color: candle.color,
        transparent: true,
        opacity: 0,
        linewidth: 2,
      });
      const glowLine = new THREE.Line(geo.clone(), glowMat);
      roomGroup.add(glowLine);

      pathLines[mac] = { line, glowLine, mat, glowMat };
    }
  }
}

function makeTextSprite(text, color) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 32;
  const ctx = canvas.getContext("2d");
  ctx.font = "14px monospace";
  ctx.fillStyle = typeof color === "number" ? `#${color.toString(16).padStart(6, "0")}` : color;
  ctx.globalAlpha = 0.4;
  ctx.textAlign = "center";
  ctx.fillText(text, 64, 20);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(1.0, 0.25, 1);
  return sprite;
}

// ─── Animation ───────────────────────────────────────────────────────

function activityColor(ratio) {
  if (ratio < 1.5)  return PALETTE.pathIdle;
  if (ratio < 3.0)  return PALETTE.lowActivity;
  if (ratio < 6.0)  return PALETTE.medActivity;
  if (ratio < 12.0) return PALETTE.highActivity;
  return PALETTE.peakActivity;
}

function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  const t = clock.elapsedTime;
  controls.update();

  const data = lastData || {};
  const paths = data.paths || {};

  // Smooth incoming values
  for (const [mac, pd] of Object.entries(paths)) {
    if (!smoothed[mac]) smoothed[mac] = { variance_ratio: 1.0, rssi: -50 };
    const s = smoothed[mac];
    s.variance_ratio += (pd.variance_ratio - s.variance_ratio) * 0.08;
    s.rssi += ((pd.rssi || -50) - s.rssi) * 0.08;
  }
  for (const [mac, s] of Object.entries(smoothed)) {
    if (!paths[mac]) s.variance_ratio += (1.0 - s.variance_ratio) * 0.02;
  }

  // Update candles
  for (const [mac, meshes] of Object.entries(candleMeshes)) {
    const ratio = smoothed[mac]?.variance_ratio || 1.0;
    const disturbed = ratio > 3.0;
    const breathe = 1 + Math.sin(t * 2 + meshes.config.x * 5) * 0.1;

    // Core sphere scale
    const scale = disturbed ? 1.0 + ratio * 0.05 : 0.8 * breathe;
    meshes.sphere.scale.setScalar(scale);

    // Glow
    const glowScale = disturbed ? 1.5 + ratio * 0.15 : 1.0 * breathe;
    meshes.glow.scale.setScalar(glowScale);
    meshes.glow.material.opacity = disturbed ? 0.12 + ratio * 0.01 : 0.06 * breathe;
    meshes.glow.material.color.setHex(disturbed ? activityColor(ratio) : meshes.config.color);

    // Light intensity
    meshes.light.intensity = disturbed ? 0.8 + ratio * 0.1 : 0.3 * breathe;
    meshes.light.color.setHex(disturbed ? activityColor(ratio) : meshes.config.color);
    meshes.light.distance = disturbed ? 5 + ratio * 0.5 : 3;
  }

  // Update paths
  for (const [mac, pl] of Object.entries(pathLines)) {
    const ratio = smoothed[mac]?.variance_ratio || 1.0;
    const disturbed = ratio > 3.0;
    const color = activityColor(ratio);

    // Idle line
    pl.mat.opacity = disturbed ? 0.05 : 0.1 + Math.sin(t + mac.charCodeAt(3)) * 0.05;

    // Glow line
    pl.glowMat.color.setHex(color);
    pl.glowMat.opacity = disturbed ? Math.min(0.6, 0.1 + ratio * 0.04) : 0;
  }

  // Update stats
  updateOverlay(data);

  renderer.render(scene, camera);
}

// ─── Overlay / Stats ─────────────────────────────────────────────────

function updateOverlay(data) {
  const meta = data.meta || {};
  const paths = data.paths || {};

  document.getElementById("s-candles").textContent = Object.keys(CANDLES).length;
  document.getElementById("s-sensors").textContent = Object.keys(SENSORS).length;
  document.getElementById("s-paths").textContent =
    Object.keys(CANDLES).length * Object.keys(SENSORS).length;
  document.getElementById("s-pps").textContent = meta.packets_per_sec || "—";
  document.getElementById("s-macs").textContent = meta.unique_macs || "—";
  document.getElementById("s-disturb").textContent = meta.disturbance_count || "0";

  const container = document.getElementById("candle-stats");
  let html = "";
  for (const [mac, candle] of Object.entries(CANDLES)) {
    const pd = paths[mac];
    const sm = smoothed[mac];
    const ratio = sm ? sm.variance_ratio.toFixed(1) : "—";
    const rssi = pd ? pd.rssi : "—";
    const colorHex = `#${candle.color.toString(16).padStart(6, "0")}`;
    const cls = pd?.disturbed ? "disturbed" : (sm && sm.variance_ratio > 1.5 ? "active" : "");
    html += `<div class="stat-row ${cls}">
      <span style="color:${colorHex}">${candle.name}</span>
      <span class="val">var=${ratio} rssi=${rssi}</span>
    </div>`;
  }
  container.innerHTML = html;

  if (data.narrative) {
    const el = document.getElementById("narrative-text");
    el.textContent = data.narrative;
    el.classList.add("active");
    clearTimeout(el._fadeTimer);
    el._fadeTimer = setTimeout(() => el.classList.remove("active"), 5000);
  }
}

// ─── WebSocket ───────────────────────────────────────────────────────

function connectWS() {
  const connEl = document.getElementById("connection");
  try {
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      connected = true;
      connEl.textContent = "\u25CF live";
      connEl.className = "conn-live";
    };
    ws.onmessage = (e) => {
      try { lastData = JSON.parse(e.data); } catch {}
    };
    ws.onclose = () => {
      connected = false;
      connEl.textContent = "\u25CF reconnecting...";
      connEl.className = "conn-dead";
      setTimeout(connectWS, RECONNECT_INTERVAL);
    };
    ws.onerror = () => ws.close();
  } catch {
    connEl.textContent = "\u25CF mock data";
    connEl.className = "conn-mock";
    setTimeout(connectWS, RECONNECT_INTERVAL);
  }
}

// Mock data fallback
function mockTick() {
  if (connected) return;
  const t = Date.now() * 0.001;
  const paths = {};
  for (const mac of Object.keys(CANDLES)) {
    const wave = Math.sin(t * 0.4 + mac.charCodeAt(4) * 2) * 0.5 + 0.5;
    const spike = Math.sin(t * 0.15 + mac.charCodeAt(2) * 3) > 0.85 ? 10 * Math.random() : 0;
    const ratio = Math.max(0.5, 1.0 + wave * 2.5 + spike);
    paths[mac] = {
      variance_ratio: ratio,
      rssi: -45 + Math.sin(t * 0.3 + mac.charCodeAt(2)) * 8,
      rssi_delta: Math.sin(t * 0.2) * 3,
      packets: Math.floor(t * 15),
      disturbed: ratio > 3.0,
    };
  }
  const dc = Object.values(paths).filter((p) => p.disturbed).length;
  lastData = {
    paths,
    meta: { packets_per_sec: 70, unique_macs: 4, disturbance_count: dc, uptime_s: Math.floor(t) },
    narrative: dc > 0
      ? "The field ripples. Something moves between the candles."
      : "Stillness. The electromagnetic whispers are faint.",
  };
}

// ─── Resize ──────────────────────────────────────────────────────────

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// ─── Boot ────────────────────────────────────────────────────────────

init();
connectWS();
setInterval(mockTick, 200);
animate();
