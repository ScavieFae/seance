/**
 * StatsOverlay — HUD-style stats panel over the 3D view.
 * Shows room metrics, per-candle status, and connection state.
 */

import { CANDLES } from "../lib/config";

function activityClass(ratio) {
  if (ratio > 3.0) return "disturbed";
  if (ratio > 1.5) return "active";
  return "";
}

export default function StatsOverlay({ data, connected }) {
  const meta = data?.meta || {};
  const paths = data?.paths || {};
  const mood = data?.mood || "sleeping";
  const narrative = data?.narrative || "Listening for electromagnetic whispers...";

  return (
    <>
      {/* Top-left stats */}
      <div style={styles.stats}>
        <h1 style={styles.title}>&#x26B5; Séance</h1>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>&#x25C8; Room</h2>
          <Row label="Candles" value={Object.keys(CANDLES).length} />
          <Row label="Mood" value={mood} className={mood} />
          <Row label="Packets/sec" value={meta.packets_per_sec || "—"} />
          <Row label="Unique MACs" value={meta.unique_macs || "—"} />
          <Row label="Disturbances" value={meta.disturbance_count || "0"} />
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>&#x25C8; Candle Paths</h2>
          {Object.entries(CANDLES).map(([mac, candle]) => {
            const pd = paths[mac];
            const ratio = pd?.variance_ratio;
            // Log-scale intensity bar: 0-100%
            const pct = ratio ? Math.min(100, Math.round(Math.log10(Math.max(1, ratio)) / 3 * 100)) : 0;
            const rssi = pd?.rssi != null ? Math.round(pd.rssi) : "—";
            return (
              <Row
                key={mac}
                label={<span style={{ color: candle.color }}>{candle.name}</span>}
                value={
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{
                      width: 40, height: 4, background: "#1a1a1a", borderRadius: 2, overflow: "hidden",
                      display: "inline-block",
                    }}>
                      <span style={{
                        width: `${pct}%`, height: "100%", display: "block", borderRadius: 2,
                        background: pct > 60 ? "#FF5014" : pct > 30 ? "#FF8C00" : "#333",
                      }} />
                    </span>
                    <span style={{ fontSize: 9, minWidth: 28 }}>{rssi}dB</span>
                  </span>
                }
                className={pd ? activityClass(pd.variance_ratio) : ""}
              />
            );
          })}
        </div>
      </div>

      {/* Top-right connection */}
      <div style={styles.connection}>
        <span style={{ color: connected ? "#00FF80" : "#FF8C00" }}>
          &#x25CF; {connected ? "live" : "mock data"}
        </span>
      </div>

      {/* Bottom narrative */}
      <div style={styles.narrative}>
        <span style={styles.narrativeText}>{narrative}</span>
      </div>
    </>
  );
}

function Row({ label, value, className }) {
  const valColor =
    className === "disturbed"
      ? "#FF5014"
      : className === "active"
        ? "#FFB347"
        : "#A0A0A0";
  return (
    <div style={styles.row}>
      <span style={{ color: "#666" }}>{label}</span>
      <span style={{ color: valColor, textAlign: "right" }}>{value}</span>
    </div>
  );
}

const styles = {
  stats: {
    position: "absolute",
    top: 24,
    left: 24,
    zIndex: 10,
    pointerEvents: "none",
    maxWidth: 280,
  },
  title: {
    fontSize: 13,
    letterSpacing: 3,
    color: "#FFB347",
    marginBottom: 16,
    textTransform: "uppercase",
    fontWeight: "normal",
  },
  section: {
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 9,
    letterSpacing: 2,
    color: "#FF8C00",
    textTransform: "uppercase",
    marginBottom: 4,
    fontWeight: "normal",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 11,
    lineHeight: 1.6,
  },
  connection: {
    position: "absolute",
    top: 24,
    right: 24,
    zIndex: 10,
    fontSize: 9,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  narrative: {
    position: "absolute",
    bottom: 24,
    left: 24,
    right: 400,
    zIndex: 10,
    pointerEvents: "none",
  },
  narrativeText: {
    fontSize: 13,
    color: "#666",
    lineHeight: 1.6,
    fontStyle: "italic",
  },
};
