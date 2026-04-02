/**
 * RoomView — 3D conference room visualization using React Three Fiber.
 * Renders wireframe room, candle nodes with labels, sensors, and signal paths.
 * Glow intensity uses log scale to prevent blowout on high variance.
 */

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Text, Billboard } from "@react-three/drei";
import * as THREE from "three";
import { ROOM, CANDLES, SENSORS, KNOWN_PRESENCES } from "../lib/config";

// Log-scale mapping: variance 1-1000+ → 0-1 normalized intensity
function normalizeVar(ratio) {
  if (ratio <= 1) return 0;
  return Math.min(1, Math.log10(ratio) / 3); // log10(1000) = 3
}

function activityColor(norm) {
  if (norm < 0.15) return "#1a1008";
  if (norm < 0.35) return "#FF8C00";
  if (norm < 0.6) return "#FF5014";
  if (norm < 0.8) return "#DA70D6";
  return "#1E90FF";
}

// ─── Candle Node ─────────────────────────────────────────────────────

function CandleNode({ config, smoothedRef, onClick, selected }) {
  const sphereRef = useRef();
  const glowRef = useRef();
  const lightRef = useRef();

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const sm = smoothedRef.current[config.mac] || { variance_ratio: 1.0 };
    const norm = normalizeVar(sm.variance_ratio);
    const breathe = 1 + Math.sin(t * 2 + config.x * 5) * 0.05;

    if (sphereRef.current) {
      const s = (0.06 + norm * 0.06) * breathe;
      sphereRef.current.scale.setScalar(s / 0.06); // relative to base geometry
    }
    if (glowRef.current) {
      // Glow radius: 0.15 at rest → 0.6 max (capped)
      const gs = (0.15 + norm * 0.45) * breathe;
      glowRef.current.scale.setScalar(gs / 0.15);
      glowRef.current.material.opacity = 0.04 + norm * 0.12;
      glowRef.current.material.color.set(
        norm > 0.15 ? activityColor(norm) : config.color
      );
    }
    if (lightRef.current) {
      lightRef.current.intensity = 0.2 + norm * 0.8;
      lightRef.current.color.set(norm > 0.15 ? activityColor(norm) : config.color);
      lightRef.current.distance = 1.5 + norm * 2;
    }
  });

  return (
    <group position={[config.x, config.y, config.z]} onClick={(e) => { e.stopPropagation(); onClick?.(config.mac); }} style={{ cursor: "pointer" }}>
      {/* Core sphere — clickable */}
      <mesh ref={sphereRef} onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = "pointer"; }} onPointerOut={() => { document.body.style.cursor = ""; }}>
        <sphereGeometry args={[0.06, 16, 16]} />
        <meshBasicMaterial color={config.color} />
      </mesh>
      {/* Selection ring */}
      {selected && (
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.18, 0.22, 32]} />
          <meshBasicMaterial color={config.color} transparent opacity={0.6} />
        </mesh>
      )}
      {/* Glow sphere */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.15, 16, 16]} />
        <meshBasicMaterial
          color={config.color}
          transparent
          opacity={0.06}
          depthWrite={false}
        />
      </mesh>
      {/* Point light */}
      <pointLight
        ref={lightRef}
        color={config.color}
        intensity={0.3}
        distance={2}
        decay={2}
      />
      {/* Label — always faces camera */}
      <Billboard position={[0, 0.2, 0]}>
        <Text
          fontSize={0.1}
          color={config.color}
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.005}
          outlineColor="#000000"
        >
          {config.name}
        </Text>
      </Billboard>
    </group>
  );
}

// ─── Signal Path ─────────────────────────────────────────────────────

function SignalPath({ from, to, mac, sensorIp, candleColor, sensorPathsRef }) {
  const lineRef = useRef();
  const glowRef = useRef();
  const tubeRef = useRef();
  const smoothed = useRef(1.0);

  const points = useMemo(
    () => [new THREE.Vector3(from.x, from.y, from.z), new THREE.Vector3(to.x, to.y, to.z)],
    [from, to]
  );
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  const curve = useMemo(
    () => new THREE.LineCurve3(
      new THREE.Vector3(from.x, from.y, from.z),
      new THREE.Vector3(to.x, to.y, to.z)
    ),
    [from, to]
  );
  const tubeGeom = useMemo(() => new THREE.TubeGeometry(curve, 1, 0.02, 6, false), [curve]);

  useFrame(({ clock }) => {
    // Get per-sensor-per-candle variance (real data for this specific path)
    const sensorData = sensorPathsRef.current?.[sensorIp]?.[mac];
    const rawRatio = sensorData?.variance_ratio ?? 1.0;
    smoothed.current += (rawRatio - smoothed.current) * 0.15;
    const norm = normalizeVar(smoothed.current);
    const t = clock.elapsedTime;

    if (lineRef.current) {
      lineRef.current.material.opacity = 0.04 + norm * 0.1;
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = norm > 0.15 ? norm * 0.6 : 0;
      glowRef.current.material.color.set(norm > 0.5 ? activityColor(norm) : candleColor);
    }
    if (tubeRef.current) {
      const pulse = norm > 0.15 ? 0.5 + Math.sin(t * 4 + from.x * 3) * 0.2 : 0;
      tubeRef.current.material.opacity = norm > 0.15 ? norm * pulse : 0;
      tubeRef.current.material.color.set(norm > 0.5 ? activityColor(norm) : candleColor);
      tubeRef.current.visible = norm > 0.1;
    }
  });

  return (
    <>
      {/* Faint base line */}
      <line ref={lineRef} geometry={geometry}>
        <lineBasicMaterial color="#2a2018" transparent opacity={0.04} />
      </line>
      {/* Bright line on activity */}
      <line ref={glowRef} geometry={geometry}>
        <lineBasicMaterial color={candleColor} transparent opacity={0} />
      </line>
      {/* Glowing tube on disturbance */}
      <mesh ref={tubeRef} geometry={tubeGeom} visible={false}>
        <meshBasicMaterial color={candleColor} transparent opacity={0} depthWrite={false} />
      </mesh>
    </>
  );
}

// ─── Door Indicator ──────────────────────────────────────────────────

function DoorIndicator() {
  // Door in front of Crimson (x=3.2)
  const doorX = 3.2;
  const doorW = 1.0;
  return (
    <group>
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            array={new Float32Array([
              doorX - doorW / 2, 0, 0,
              doorX - doorW / 2, 2.1, 0,
              doorX + doorW / 2, 2.1, 0,
              doorX + doorW / 2, 0, 0,
            ])}
            count={4}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#FF9632" transparent opacity={0.3} />
      </line>
      <Billboard position={[doorX, -0.15, 0]}>
        <Text
          fontSize={0.1}
          color="#555"
          anchorX="center"
        >
          DOOR
        </Text>
      </Billboard>
    </group>
  );
}

// ─── Our Table (main venue) ──────────────────────────────────────────

function OurTable() {
  // Left of door, further into venue
  const tx = 1.25, tz = -2.5;
  const tw = 2.2, td = 1.2, th = 0.72;
  return (
    <group>
      <mesh position={[tx, th / 2, tz]}>
        <boxGeometry args={[tw, 0.04, td]} />
        <meshBasicMaterial color="#1a1610" transparent opacity={0.3} />
      </mesh>
      <lineSegments position={[tx, th / 2, tz]}>
        <edgesGeometry args={[new THREE.BoxGeometry(tw, 0.04, td)]} />
        <lineBasicMaterial color="#FF9632" transparent opacity={0.25} />
      </lineSegments>
      <Billboard position={[tx, 0.9, tz]}>
        <Text fontSize={0.08} color="#444" anchorX="center">
          OUR TABLE
        </Text>
      </Billboard>
    </group>
  );
}

// ─── Room Box ────────────────────────────────────────────────────────

function RoomBox() {
  const { width: w, height: h, depth: d } = ROOM;
  return (
    <group>
      {/* Floor grid */}
      <gridHelper
        args={[Math.max(w, d), 12, "#1a1008", "#0f0e0c"]}
        position={[w / 2, 0, d / 2]}
      />
      {/* Wireframe edges */}
      <lineSegments position={[w / 2, h / 2, d / 2]}>
        <edgesGeometry args={[new THREE.BoxGeometry(w, h, d)]} />
        <lineBasicMaterial color="#2a2018" transparent opacity={0.3} />
      </lineSegments>
    </group>
  );
}

// ─── Sensor Node ─────────────────────────────────────────────────────

function SensorNode({ config }) {
  return (
    <group position={[config.x, config.y, config.z]}>
      <mesh>
        <octahedronGeometry args={[0.05, 0]} />
        <meshBasicMaterial color="#3A3A3A" transparent opacity={0.6} />
      </mesh>
      <Billboard position={[0, 0.12, 0]}>
        <Text
          fontSize={0.07}
          color="#555"
          anchorX="center"
          anchorY="bottom"
        >
          {config.label}
        </Text>
      </Billboard>
    </group>
  );
}

// ─── Triangulation ───────────────────────────────────────────────

function triangulate(sensorRSSI) {
  // Convert RSSI to distance estimates using log-distance path loss
  // Reference: ~-40 dBm at 1 meter, path loss exponent ~2.5 indoors
  const points = [];
  for (const [ip, sData] of Object.entries(sensorRSSI)) {
    const sensor = SENSORS[ip];
    if (!sensor) continue;
    const rssi = sData.rssi || -80;
    const dist = Math.pow(10, (-40 - rssi) / 25); // meters (rough)
    points.push({ x: sensor.x, z: sensor.z, dist });
  }

  if (points.length === 0) return null;
  if (points.length === 1) {
    // One sensor: place at estimated distance in a consistent direction
    const p = points[0];
    return { x: p.x + p.dist * 0.5, z: p.z + p.dist * 0.3 };
  }

  // Gradient descent to minimize distance errors — naturally goes outside grid
  let x = points.reduce((s, p) => s + p.x, 0) / points.length;
  let z = points.reduce((s, p) => s + p.z, 0) / points.length;

  for (let iter = 0; iter < 30; iter++) {
    let dx = 0, dz = 0;
    for (const p of points) {
      const d = Math.sqrt((x - p.x) ** 2 + (z - p.z) ** 2) || 0.01;
      const error = d - p.dist;
      dx += (error * (x - p.x)) / d;
      dz += (error * (z - p.z)) / d;
    }
    x -= dx * 0.15;
    z -= dz * 0.15;
  }

  return { x, z };
}

// ─── Presences (unknown MACs triangulated from RSSI) ─────────────

function Presences({ data, onGhostClick }) {
  const ghostsRef = useRef({});

  useFrame(() => {
    const presences = data?.presences || {};

    for (const [mac, info] of Object.entries(presences)) {
      const sensors = info.sensors || {};
      if (Object.keys(sensors).length < 1) continue;

      const pos = triangulate(sensors);
      if (!pos) continue;

      if (!ghostsRef.current[mac]) {
        ghostsRef.current[mac] = { x: pos.x, z: pos.z, opacity: 0, age: 0, sensorCount: 0 };
      }
      const g = ghostsRef.current[mac];
      const isKnown = !!KNOWN_PRESENCES[mac.toLowerCase()] || !!KNOWN_PRESENCES[mac];
      // Heavier smoothing to reduce RSSI jitter — known presences get extra smoothing
      const lerp = isKnown ? 0.015 : 0.03;
      // Only move if delta is significant (deadzone to prevent micro-jitter)
      const dx = pos.x - g.x;
      const dz = pos.z - g.z;
      const dist = Math.sqrt(dx * dx + dz * dz);
      if (dist > 0.1) {
        g.x += dx * lerp;
        g.z += dz * lerp;
      }
      g.opacity = Math.min(0.5, g.opacity + 0.02);
      g.sensorCount = Object.keys(sensors).length;
      g.age = 0;
    }

    for (const [mac, g] of Object.entries(ghostsRef.current)) {
      if (!presences[mac]) {
        g.opacity -= 0.005;
        g.age++;
      }
      if (g.opacity <= 0) {
        delete ghostsRef.current[mac];
      }
    }
  });

  const ghostMacs = Object.keys(ghostsRef.current);

  return (
    <>
      {ghostMacs.map((mac) => (
        <GhostDot key={mac} mac={mac} ghostsRef={ghostsRef} onClick={onGhostClick} />
      ))}
    </>
  );
}

function GhostDot({ mac, ghostsRef, onClick }) {
  const meshRef = useRef();
  const glowRef = useRef();
  const known = KNOWN_PRESENCES[mac.toLowerCase()] || KNOWN_PRESENCES[mac];
  const color = known ? known.color : "#FFFFFF";
  const size = known ? 0.08 : 0.04;
  const glowSize = known ? 0.25 : 0.15;

  useFrame(({ clock }) => {
    const g = ghostsRef.current[mac];
    if (!g || !meshRef.current) return;
    const t = clock.elapsedTime;

    const drift = known ? 0 : Math.sin(t * 0.7 + mac.charCodeAt(4) * 2) * 0.05;
    meshRef.current.position.set(g.x + drift, 0.6, g.z + drift * 0.7);
    meshRef.current.material.opacity = known ? 0.9 : g.opacity * 0.8;

    if (glowRef.current) {
      glowRef.current.position.copy(meshRef.current.position);
      glowRef.current.material.opacity = known ? 0.2 : g.opacity * 0.15;
      const pulse = 1 + Math.sin(t * (known ? 2.5 : 1.5) + mac.charCodeAt(2)) * 0.15;
      glowRef.current.scale.setScalar(pulse);
    }
  });

  return (
    <group onClick={(e) => { e.stopPropagation(); onClick?.(mac); }}>
      <mesh
        ref={meshRef}
        onPointerOver={(e) => { e.stopPropagation(); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { document.body.style.cursor = ""; }}
      >
        <sphereGeometry args={[size, known ? 16 : 8, known ? 16 : 8]} />
        <meshBasicMaterial color={color} transparent opacity={0} depthWrite={false} />
      </mesh>
      <mesh ref={glowRef}>
        <sphereGeometry args={[glowSize, known ? 16 : 8, known ? 16 : 8]} />
        <meshBasicMaterial color={color} transparent opacity={0} depthWrite={false} />
      </mesh>
      {known && (
        <Billboard position={[0, 0.18, 0]}>
          <Text fontSize={0.1} color={color} anchorX="center" anchorY="bottom" outlineWidth={0.005} outlineColor="#000000">
            {known.name}
          </Text>
        </Billboard>
      )}
    </group>
  );
}

// ─── Scene ───────────────────────────────────────────────────────────

function Scene({ data, onCandleClick, selectedCandle, onGhostClick }) {
  const smoothedRef = useRef({});
  const sensorPathsRef = useRef({});

  useFrame(() => {
    const paths = data?.paths || {};
    for (const [mac, pd] of Object.entries(paths)) {
      if (!smoothedRef.current[mac]) {
        smoothedRef.current[mac] = { variance_ratio: 1.0, rssi: -50 };
      }
      const s = smoothedRef.current[mac];
      s.variance_ratio += (pd.variance_ratio - s.variance_ratio) * 0.3;
      s.rssi += ((pd.rssi || -50) - s.rssi) * 0.3;
    }
    for (const [mac, s] of Object.entries(smoothedRef.current)) {
      if (!paths[mac]) {
        s.variance_ratio += (1.0 - s.variance_ratio) * 0.05;
      }
    }
    // Store per-sensor data for signal paths
    if (data?.sensor_paths) {
      sensorPathsRef.current = data.sensor_paths;
    }
  });

  return (
    <>
      <ambientLight intensity={0.15} color="#111111" />
      <fog attach="fog" args={["#0A0A0A", 8, 25]} />

      <RoomBox />
      <DoorIndicator />
      <OurTable />

      {Object.entries(CANDLES).map(([mac, candle]) => (
        <CandleNode
          key={mac}
          config={{ ...candle, mac }}
          smoothedRef={smoothedRef}
          onClick={onCandleClick}
          selected={selectedCandle === mac}
        />
      ))}

      {Object.entries(SENSORS).map(([sid, sensor]) => (
        <SensorNode key={sid} config={sensor} />
      ))}

      {Object.entries(CANDLES).map(([mac, candle]) =>
        Object.entries(SENSORS).map(([sid, sensor]) => (
          <SignalPath
            key={`${mac}-${sid}`}
            from={candle}
            to={sensor}
            mac={mac}
            sensorIp={sid}
            candleColor={candle.color}
            sensorPathsRef={sensorPathsRef}
          />
        ))
      )}

      <Presences data={data} onGhostClick={onGhostClick} />
    </>
  );
}

// ─── Exported Component ──────────────────────────────────────────────

export default function RoomView({ data, onCandleClick, selectedCandle, onGhostClick }) {
  const { width: w, height: h, depth: d } = ROOM;

  return (
    <Canvas
      camera={{
        position: [w / 2 + 5, 5, -3],
        fov: 40,
        near: 0.1,
        far: 100,
      }}
      style={{ background: "#0A0A0A" }}
    >
      <Scene data={data} onCandleClick={onCandleClick} selectedCandle={selectedCandle} onGhostClick={onGhostClick} />
      <OrbitControls
        target={[w / 2, 0, d / 2]}
        enableDamping
        dampingFactor={0.05}
        rotateSpeed={0.5}
        zoomSpeed={0.8}
        minDistance={2}
        maxDistance={20}
        minPolarAngle={0}
        maxPolarAngle={Math.PI}
        enablePan
        screenSpacePanning
      />
    </Canvas>
  );
}
