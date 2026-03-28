/**
 * RoomView — 3D conference room visualization using React Three Fiber.
 * Renders wireframe room, candle nodes with labels, sensors, and signal paths.
 * Glow intensity uses log scale to prevent blowout on high variance.
 */

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Text, Billboard } from "@react-three/drei";
import * as THREE from "three";
import { ROOM, CANDLES, SENSORS } from "../lib/config";

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

// ─── Scene ───────────────────────────────────────────────────────────

function Scene({ data, onCandleClick, selectedCandle }) {
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
    </>
  );
}

// ─── Exported Component ──────────────────────────────────────────────

export default function RoomView({ data, onCandleClick, selectedCandle }) {
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
      <Scene data={data} onCandleClick={onCandleClick} selectedCandle={selectedCandle} />
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
