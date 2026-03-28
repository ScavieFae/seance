/**
 * RoomView — 3D room visualization using React Three Fiber.
 * Renders the wireframe room, candle nodes, sensor, and signal paths.
 */

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { ROOM, CANDLES, SENSORS } from "../lib/config";

function activityColor(ratio) {
  if (ratio < 1.5) return "#1a1008";
  if (ratio < 3.0) return "#FF8C00";
  if (ratio < 6.0) return "#FF5014";
  if (ratio < 12.0) return "#DA70D6";
  return "#1E90FF";
}

// ─── Candle Node ─────────────────────────────────────────────────────

function CandleNode({ config, pathData, smoothedRef }) {
  const sphereRef = useRef();
  const glowRef = useRef();
  const lightRef = useRef();

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const sm = smoothedRef.current[config.mac] || { variance_ratio: 1.0 };
    const ratio = sm.variance_ratio;
    const disturbed = ratio > 3.0;
    const breathe = 1 + Math.sin(t * 2 + config.x * 5) * 0.1;

    if (sphereRef.current) {
      const s = disturbed ? 1.0 + ratio * 0.05 : 0.8 * breathe;
      sphereRef.current.scale.setScalar(s);
    }
    if (glowRef.current) {
      const gs = disturbed ? 1.5 + ratio * 0.15 : 1.0 * breathe;
      glowRef.current.scale.setScalar(gs);
      glowRef.current.material.opacity = disturbed
        ? 0.12 + ratio * 0.01
        : 0.06 * breathe;
      glowRef.current.material.color.set(
        disturbed ? activityColor(ratio) : config.color
      );
    }
    if (lightRef.current) {
      lightRef.current.intensity = disturbed ? 0.8 + ratio * 0.1 : 0.3 * breathe;
      lightRef.current.color.set(disturbed ? activityColor(ratio) : config.color);
      lightRef.current.distance = disturbed ? 5 + ratio * 0.5 : 3;
    }
  });

  return (
    <group position={[config.x, config.y, config.z]}>
      <mesh ref={sphereRef}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshBasicMaterial color={config.color} />
      </mesh>
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.4, 16, 16]} />
        <meshBasicMaterial
          color={config.color}
          transparent
          opacity={0.08}
          depthWrite={false}
        />
      </mesh>
      <pointLight
        ref={lightRef}
        color={config.color}
        intensity={0.5}
        distance={4}
        decay={2}
      />
    </group>
  );
}

// ─── Signal Path ─────────────────────────────────────────────────────

function SignalPath({ from, to, mac, smoothedRef }) {
  const lineRef = useRef();
  const glowRef = useRef();

  const points = useMemo(
    () => [new THREE.Vector3(from.x, from.y, from.z), new THREE.Vector3(to.x, to.y, to.z)],
    [from, to]
  );
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  useFrame(() => {
    const sm = smoothedRef.current[mac] || { variance_ratio: 1.0 };
    const ratio = sm.variance_ratio;
    const disturbed = ratio > 3.0;

    if (lineRef.current) {
      lineRef.current.material.opacity = disturbed ? 0.05 : 0.12;
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = disturbed
        ? Math.min(0.6, 0.1 + ratio * 0.04)
        : 0;
      glowRef.current.material.color.set(activityColor(ratio));
    }
  });

  return (
    <>
      <line ref={lineRef} geometry={geometry}>
        <lineBasicMaterial color="#1a1008" transparent opacity={0.12} />
      </line>
      <line ref={glowRef} geometry={geometry}>
        <lineBasicMaterial color="#FF8C00" transparent opacity={0} />
      </line>
    </>
  );
}

// ─── Room Box ────────────────────────────────────────────────────────

function RoomBox() {
  const { width: w, height: h, depth: d } = ROOM;
  return (
    <group>
      {/* Floor grid */}
      <gridHelper
        args={[Math.max(w, d), 16, "#1a1008", "#0f0e0c"]}
        position={[w / 2, 0, d / 2]}
        rotation={[0, 0, 0]}
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
    <mesh position={[config.x, config.y, config.z]}>
      <octahedronGeometry args={[0.08, 0]} />
      <meshBasicMaterial color="#3A3A3A" transparent opacity={0.6} />
    </mesh>
  );
}

// ─── Scene ───────────────────────────────────────────────────────────

function Scene({ data }) {
  const smoothedRef = useRef({});

  // Smooth incoming data
  useFrame(() => {
    const paths = data?.paths || {};
    for (const [mac, pd] of Object.entries(paths)) {
      if (!smoothedRef.current[mac]) {
        smoothedRef.current[mac] = { variance_ratio: 1.0, rssi: -50 };
      }
      const s = smoothedRef.current[mac];
      s.variance_ratio += (pd.variance_ratio - s.variance_ratio) * 0.08;
      s.rssi += ((pd.rssi || -50) - s.rssi) * 0.08;
    }
    // Decay absent paths
    for (const [mac, s] of Object.entries(smoothedRef.current)) {
      if (!paths[mac]) {
        s.variance_ratio += (1.0 - s.variance_ratio) * 0.02;
      }
    }
  });

  return (
    <>
      <ambientLight intensity={0.3} color="#111111" />
      <fog attach="fog" args={["#0A0A0A", 15, 40]} />

      <RoomBox />

      {Object.entries(CANDLES).map(([mac, candle]) => (
        <CandleNode
          key={mac}
          config={{ ...candle, mac }}
          pathData={data?.paths?.[mac]}
          smoothedRef={smoothedRef}
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
            smoothedRef={smoothedRef}
          />
        ))
      )}
    </>
  );
}

// ─── Exported Component ──────────────────────────────────────────────

export default function RoomView({ data }) {
  const { width: w, height: h, depth: d } = ROOM;

  return (
    <Canvas
      camera={{
        position: [12, 8, 12],
        fov: 45,
        near: 0.1,
        far: 100,
      }}
      style={{ background: "#0A0A0A" }}
    >
      <Scene data={data} />
      <OrbitControls
        target={[w / 2, h / 2, d / 2]}
        enableDamping
        dampingFactor={0.05}
        rotateSpeed={0.5}
        zoomSpeed={0.8}
        minDistance={2}
        maxDistance={40}
        autoRotate
        autoRotateSpeed={0.3}
        minPolarAngle={0}
        maxPolarAngle={Math.PI}
        enablePan
        screenSpacePanning
      />
    </Canvas>
  );
}
