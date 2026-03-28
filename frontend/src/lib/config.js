/**
 * Séance — Shared config
 * Single source of truth for room layout, candle data, and connection info.
 * Update candle positions here after measuring the venue room.
 */

export const WS_URL = `ws://${window.location.hostname || "localhost"}:8765`;

// Room dimensions in meters
export const ROOM = { width: 8, depth: 6, height: 3 };

// Candles currently in the room
// x/y/z = meters from room corner (y = height off floor)
export const CANDLES = {
  "485519ec2f04": { id: "04", name: "Yellow",  x: 2.0, y: 0.8, z: 1.8, color: "#DCFF00", hex: 0xdcff00 },
  "08f9e0690c68": { id: "05", name: "Green",   x: 5.2, y: 0.8, z: 1.5, color: "#00FF00", hex: 0x00ff00 },
  "485519ecd18e": { id: "10", name: "Purple",  x: 4.0, y: 0.8, z: 4.2, color: "#8000FF", hex: 0x8000ff },
};

export const SENSORS = {
  esp32_a: { x: 0.8, y: 1.2, z: 5.4 },
};

// All 13 candles (for future scaling)
export const ALL_CANDLES = {
  "4c752594d210": { id: "01", name: "Red",        color: "#FF0000" },
  "08f9e0611bc7": { id: "02", name: "Orange",     color: "#FF6400" },
  "c8c9a339a907": { id: "03", name: "Gold",       color: "#FFC800" },
  "485519ec2f04": { id: "04", name: "Yellow",     color: "#DCFF00" },
  "08f9e0690c68": { id: "05", name: "Green",      color: "#00FF00" },
  "485519ef0a8d": { id: "06", name: "Teal",       color: "#00FF80" },
  "c8c9a339a779": { id: "07", name: "Cyan",       color: "#00FFFF" },
  "c8c9a338ec00": { id: "08", name: "Sky Blue",   color: "#0080FF" },
  "485519ee65c7": { id: "09", name: "Blue",       color: "#0000FF" },
  "485519ecd18e": { id: "10", name: "Purple",     color: "#8000FF" },
  "485519ecd242": { id: "11", name: "Magenta",    color: "#FF00FF" },
  "08f9e068ea07": { id: "12", name: "Rose",       color: "#FF0064" },
  "485519ec2429": { id: "13", name: "Warm White", color: "#FFB464" },
};

// Moods
export const MOODS = {
  SLEEPING:       "sleeping",
  WAKING:         "waking",
  CURIOUS:        "curious",
  PLAYFUL:        "playful",
  EXCITED:        "excited",
  CONTEMPLATIVE:  "contemplative",
  DREAMING:       "dreaming",
};
