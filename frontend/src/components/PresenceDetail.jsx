/**
 * PresenceDetail — Info panel for an unknown MAC (ghost presence).
 * Shows which sensors see it, RSSI from each, estimated position, and OUI vendor lookup.
 */

import { useRef, useEffect, useState } from "react";
import { SENSORS, KNOWN_PRESENCES } from "../lib/config";

// Common OUI prefixes — enough to identify device types at a hackathon
const OUI_HINTS = {
  "e8:f6:0a": "Intel (laptop/PC)",
  "90:e5:b1": "Intel (laptop/PC)",
  "94:83:c4": "GL Technologies (router/AP)",
  "a6:24:15": "Randomized (phone/tablet)",
  "a6:81:94": "Randomized (phone/tablet)",
  "3e:a0:0d": "Randomized (phone/tablet)",
  "56:57:2e": "Randomized (phone/tablet)",
  "da:ce:2c": "Randomized (phone/tablet)",
  "dc:97:ba": "Randomized (phone/tablet)",
  "f6:8d:06": "Randomized (phone/tablet)",
  "22:f0:8e": "Randomized (phone/tablet)",
  "92:9b:fc": "Randomized (phone/tablet)",
  "16:07:5a": "Randomized (phone/tablet)",
  "c8:c9:a3": "Espressif (ESP32)",
  "48:55:19": "Espressif (ESP32)",
  "08:f9:e0": "Espressif (ESP32)",
  "4c:75:25": "Espressif (ESP32)",
};

function getDeviceHint(mac) {
  const prefix = mac.substring(0, 8);
  if (OUI_HINTS[prefix]) return OUI_HINTS[prefix];
  // Check if locally administered (randomized MAC)
  const firstByte = parseInt(mac.substring(0, 2), 16);
  if (firstByte & 0x02) return "Randomized MAC (likely phone/tablet)";
  return "Unknown device";
}

const MAX_HISTORY = 40;

export default function PresenceDetail({ mac, data }) {
  const presence = data?.presences?.[mac];
  const sensors = presence?.sensors || {};
  const [history, setHistory] = useState([]);
  const lastTs = useRef(0);

  useEffect(() => {
    if (!presence) return;
    const now = Date.now();
    if (now - lastTs.current < 500) return;
    lastTs.current = now;
    setHistory((prev) => {
      const entry = { t: now, sensors: { ...sensors } };
      return [...prev, entry].slice(-MAX_HISTORY);
    });
  }, [presence, sensors]);

  const known = KNOWN_PRESENCES[mac.toLowerCase()] || KNOWN_PRESENCES[mac];
  const deviceHint = known ? `${known.name}'s device` : getDeviceHint(mac);
  const sensorCount = Object.keys(sensors).length;

  // Strongest sensor
  let strongest = null;
  let strongestRSSI = -999;
  for (const [ip, s] of Object.entries(sensors)) {
    if (s.rssi > strongestRSSI) {
      strongestRSSI = s.rssi;
      strongest = ip;
    }
  }

  return (
    <div style={s.container}>
      {/* Identity */}
      <div style={s.section}>
        <div style={s.sectionTitle}>IDENTITY</div>
        {known && <div style={{ fontSize: 16, color: known.color, fontWeight: "bold", marginBottom: 4 }}>{known.name}</div>}
        <div style={s.mac}>{mac}</div>
        <div style={s.hint}>{deviceHint}</div>
      </div>

      {/* Sensor visibility */}
      <div style={s.section}>
        <div style={s.sectionTitle}>SEEN BY {sensorCount} SENSOR{sensorCount !== 1 ? "S" : ""}</div>
        {Object.entries(sensors).map(([ip, sData]) => {
          const sensor = SENSORS[ip];
          const label = sensor?.label || ip;
          const isStrongest = ip === strongest;
          const rssi = sData.rssi?.toFixed(0) || "?";
          // RSSI bar: -30 = max, -90 = min
          const pct = Math.max(0, Math.min(100, ((sData.rssi || -90) + 90) / 60 * 100));
          return (
            <div key={ip} style={s.sensorRow}>
              <span style={{ color: isStrongest ? "#FFB347" : "#666", minWidth: 50 }}>
                Board {label}
              </span>
              <span style={{ flex: 1, display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{
                  width: 60, height: 4, background: "#1a1a1a", borderRadius: 2, overflow: "hidden",
                  display: "inline-block",
                }}>
                  <span style={{
                    width: `${pct}%`, height: "100%", display: "block", borderRadius: 2,
                    background: isStrongest ? "#FFB347" : "#555",
                  }} />
                </span>
              </span>
              <span style={{ color: isStrongest ? "#FFB347" : "#A0A0A0", fontSize: 10, minWidth: 40, textAlign: "right" }}>
                {rssi} dB
              </span>
            </div>
          );
        })}
        {strongest && (
          <div style={s.nearestBadge}>
            Nearest to Board {SENSORS[strongest]?.label || strongest}
          </div>
        )}
      </div>

      {/* RSSI history per sensor */}
      <div style={s.section}>
        <div style={s.sectionTitle}>RSSI HISTORY</div>
        <svg width="100%" height={80} style={{ display: "block" }}>
          {Object.keys(SENSORS).map((sensorIp, idx) => {
            const color = ["#FF8C00", "#4488FF", "#00FF80", "#DA70D6"][idx] || "#666";
            const label = SENSORS[sensorIp]?.label || "?";
            if (history.length < 2) return null;

            const rssis = history.map((h) => h.sensors[sensorIp]?.rssi).filter(Boolean);
            if (rssis.length < 2) return null;

            const points = history.map((h, i) => {
              const rssi = h.sensors[sensorIp]?.rssi;
              if (rssi == null) return null;
              const x = (i / (MAX_HISTORY - 1)) * 340;
              const y = 75 - ((rssi + 90) / 60) * 65;
              return `${x},${y}`;
            }).filter(Boolean).join(" ");

            return (
              <g key={sensorIp}>
                <polyline fill="none" stroke={color} strokeWidth={1.2} opacity={0.7} points={points} />
                <text x={345} y={10 + idx * 12} fill={color} fontSize={8}>{label}</text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Raw observations */}
      <div style={s.section}>
        <div style={s.sectionTitle}>OBSERVATIONS</div>
        <div style={s.stream}>
          {history.slice(-10).reverse().map((h, i) => (
            <div key={i} style={s.streamRow}>
              <span style={{ color: "#444" }}>
                {new Date(h.t).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
              {Object.entries(h.sensors).map(([ip, sd]) => (
                <span key={ip} style={{ color: "#666" }}>
                  {SENSORS[ip]?.label || "?"}:{sd.rssi?.toFixed(0)}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const s = {
  container: {
    padding: "12px 16px",
    height: "100%",
    overflowY: "auto",
    fontFamily: "'SF Mono', Menlo, Consolas, monospace",
    fontSize: 11,
  },
  section: { marginBottom: 16 },
  sectionTitle: {
    fontSize: 9,
    letterSpacing: 2,
    color: "#FF8C00",
    textTransform: "uppercase",
    marginBottom: 6,
  },
  mac: {
    fontSize: 14,
    color: "#FFFFFF",
    fontWeight: "bold",
    marginBottom: 2,
  },
  hint: {
    fontSize: 11,
    color: "#888",
    fontStyle: "italic",
  },
  sensorRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 10,
    lineHeight: 2,
  },
  nearestBadge: {
    marginTop: 6,
    padding: "4px 8px",
    background: "#1a1a1a",
    border: "1px solid #333",
    borderRadius: 4,
    fontSize: 9,
    color: "#FFB347",
    textAlign: "center",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  stream: {
    maxHeight: 150,
    overflowY: "auto",
    background: "#0d0d0d",
    borderRadius: 4,
    padding: "4px 8px",
  },
  streamRow: {
    display: "flex",
    gap: 10,
    fontSize: 10,
    lineHeight: 1.8,
  },
};
