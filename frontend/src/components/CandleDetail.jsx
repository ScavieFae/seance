/**
 * CandleDetail — Live data stream for a selected candle.
 * Shows rolling variance, RSSI, disturbance state, and a mini history.
 */

import { useRef, useEffect, useState } from "react";
import { CANDLES } from "../lib/config";

const MAX_HISTORY = 60; // ~12 seconds at 5 updates/sec

export default function CandleDetail({ mac, data }) {
  const config = CANDLES[mac];
  const pd = data?.paths?.[mac];
  const [history, setHistory] = useState([]);
  const lastTs = useRef(0);

  // Accumulate history
  useEffect(() => {
    if (!pd) return;
    const now = Date.now();
    if (now - lastTs.current < 200) return; // throttle to 5/sec
    lastTs.current = now;
    setHistory((prev) => {
      const next = [...prev, { t: now, ...pd }];
      return next.slice(-MAX_HISTORY);
    });
  }, [pd]);

  if (!config) return <div style={s.empty}>Unknown candle</div>;

  const ratio = pd?.variance_ratio ?? 0;
  const rssi = pd?.rssi ?? -99;
  const delta = pd?.rssi_delta ?? 0;
  const packets = pd?.packets ?? 0;
  const disturbed = pd?.disturbed ?? false;

  // Mini sparkline of variance history
  const maxVar = Math.max(3, ...history.map((h) => h.variance_ratio));

  return (
    <div style={s.container}>
      {/* Live stats */}
      <div style={s.section}>
        <div style={s.sectionTitle}>LIVE</div>
        <div style={s.statGrid}>
          <StatBox label="Variance" value={ratio.toFixed(1)} color={disturbed ? "#FF5014" : "#FFB347"} />
          <StatBox label="RSSI" value={`${rssi.toFixed(0)} dB`} color="#A0A0A0" />
          <StatBox label="RSSI Delta" value={`${delta > 0 ? "+" : ""}${delta.toFixed(1)}`} color={Math.abs(delta) > 3 ? "#FF8C00" : "#666"} />
          <StatBox label="Packets" value={packets.toLocaleString()} color="#666" />
        </div>
        <div style={{ ...s.statusBadge, background: disturbed ? "#FF501422" : "#1a1a1a", borderColor: disturbed ? "#FF5014" : "#333" }}>
          {disturbed ? "DISTURBED — movement detected" : "BASELINE — quiet"}
        </div>
      </div>

      {/* Variance sparkline */}
      <div style={s.section}>
        <div style={s.sectionTitle}>VARIANCE HISTORY</div>
        <svg width="100%" height={80} style={{ display: "block" }}>
          {/* Threshold line */}
          <line
            x1="0" x2="100%"
            y1={80 - (3 / maxVar) * 70}
            y2={80 - (3 / maxVar) * 70}
            stroke="#FF5014" strokeWidth={0.5} strokeDasharray="4 4" opacity={0.4}
          />
          {/* Sparkline */}
          {history.length > 1 && (
            <polyline
              fill="none"
              stroke={config.color}
              strokeWidth={1.5}
              opacity={0.8}
              points={history.map((h, i) => {
                const x = (i / (MAX_HISTORY - 1)) * 100 + "%";
                const xNum = (i / (MAX_HISTORY - 1)) * 340;
                const y = 80 - (Math.min(h.variance_ratio, maxVar) / maxVar) * 70;
                return `${xNum},${y}`;
              }).join(" ")}
            />
          )}
          {/* Current value dot */}
          {history.length > 0 && (() => {
            const last = history[history.length - 1];
            const x = ((history.length - 1) / (MAX_HISTORY - 1)) * 340;
            const y = 80 - (Math.min(last.variance_ratio, maxVar) / maxVar) * 70;
            return <circle cx={x} cy={y} r={3} fill={config.color} />;
          })()}
        </svg>
      </div>

      {/* RSSI sparkline */}
      <div style={s.section}>
        <div style={s.sectionTitle}>RSSI HISTORY</div>
        <svg width="100%" height={60} style={{ display: "block" }}>
          {history.length > 1 && (() => {
            const rssis = history.map((h) => h.rssi || -80);
            const minR = Math.min(...rssis) - 5;
            const maxR = Math.max(...rssis) + 5;
            const range = maxR - minR || 1;
            return (
              <polyline
                fill="none"
                stroke="#4488FF"
                strokeWidth={1.5}
                opacity={0.6}
                points={history.map((h, i) => {
                  const x = (i / (MAX_HISTORY - 1)) * 340;
                  const y = 55 - ((h.rssi || -80) - minR) / range * 45;
                  return `${x},${y}`;
                }).join(" ")}
              />
            );
          })()}
        </svg>
      </div>

      {/* Raw stream */}
      <div style={s.section}>
        <div style={s.sectionTitle}>RAW STREAM</div>
        <div style={s.stream}>
          {history.slice(-15).reverse().map((h, i) => (
            <div key={i} style={s.streamRow}>
              <span style={{ color: "#444" }}>
                {new Date(h.t).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
              <span style={{ color: h.disturbed ? "#FF5014" : "#666" }}>
                var={h.variance_ratio?.toFixed(1)}
              </span>
              <span style={{ color: "#4488FF" }}>
                rssi={h.rssi?.toFixed(0)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, color }) {
  return (
    <div style={s.statBox}>
      <div style={{ fontSize: 9, color: "#555", letterSpacing: 1, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 18, color, fontWeight: "bold", fontFamily: "'SF Mono', Menlo, monospace" }}>{value}</div>
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
  empty: { color: "#666", padding: 20 },
  section: { marginBottom: 16 },
  sectionTitle: {
    fontSize: 9,
    letterSpacing: 2,
    color: "#FF8C00",
    textTransform: "uppercase",
    marginBottom: 6,
  },
  statGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
    marginBottom: 8,
  },
  statBox: {
    background: "#1a1a1a",
    borderRadius: 4,
    padding: "6px 10px",
  },
  statusBadge: {
    padding: "6px 10px",
    borderRadius: 4,
    border: "1px solid #333",
    fontSize: 10,
    color: "#A0A0A0",
    textAlign: "center",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  stream: {
    maxHeight: 180,
    overflowY: "auto",
    background: "#0d0d0d",
    borderRadius: 4,
    padding: "4px 8px",
  },
  streamRow: {
    display: "flex",
    gap: 12,
    fontSize: 10,
    lineHeight: 1.8,
  },
};
