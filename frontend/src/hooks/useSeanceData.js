/**
 * useSeanceData — WebSocket hook for live CSI perception data.
 * Connects to ws_bridge.py, returns current room state.
 * Falls back to mock data when disconnected.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { WS_URL, CANDLES } from "../lib/config";

function generateMockData() {
  const t = Date.now() * 0.001;
  const paths = {};
  for (const mac of Object.keys(CANDLES)) {
    const wave = Math.sin(t * 0.4 + mac.charCodeAt(4) * 2) * 0.5 + 0.5;
    const spike =
      Math.sin(t * 0.15 + mac.charCodeAt(2) * 3) > 0.85
        ? 10 * Math.random()
        : 0;
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
  return {
    paths,
    meta: {
      packets_per_sec: 70,
      unique_macs: 4,
      disturbance_count: dc,
      uptime_s: Math.floor(t),
    },
    narrative: dc > 0
      ? "The field ripples. Something moves between the candles."
      : "Stillness. The electromagnetic whispers are faint.",
    mood: dc > 1 ? "playful" : dc > 0 ? "curious" : "sleeping",
  };
}

export default function useSeanceData() {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => {
        try {
          setData(JSON.parse(e.data));
        } catch {}
      };
      ws.onclose = () => {
        setConnected(false);
        reconnectRef.current = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    } catch {
      setConnected(false);
      reconnectRef.current = setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  // Mock data fallback
  useEffect(() => {
    if (connected) return;
    const id = setInterval(() => setData(generateMockData()), 200);
    return () => clearInterval(id);
  }, [connected]);

  return { data, connected };
}
