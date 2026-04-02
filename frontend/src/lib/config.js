/**
 * Séance — Shared config
 * Single source of truth for room layout, candle data, and connection info.
 * Update candle positions here after measuring the venue room.
 */

// API runs on Lady-Titania — sensors send UDP there, not to this machine
export const WS_URL = `ws://10.9.0.160:8000/ws`;

// Conference room — facing back wall, door at front center
// x = left-right (stage left = 0), z = front(door) to back(wall), y = height
export const ROOM = { width: 4, depth: 4, height: 2.8 };

const CX = ROOM.width / 2;
const H = 0.75; // candle height (table level)

export const CANDLES = {
  // Back row (z=3.2) — Gold, Violet, Green (left to right as viewed)
  "c8:c9:a3:39:a9:07": { id: "03", name: "Gold",      color: "#FFC800", hex: 0xffc800, x: 0.8, y: H, z: 3.2 },
  "48:55:19:ec:d1:8e": { id: "10", name: "Violet",    color: "#C800FF", hex: 0xc800ff, x: 2.0, y: H, z: 3.2 },
  "08:f9:e0:69:0c:68": { id: "05", name: "Green",     color: "#00FF00", hex: 0x00ff00, x: 3.2, y: H, z: 3.2 },
  // Middle row (z=2.0) — Red, Orange, Lime
  "4c:75:25:94:d2:10": { id: "01", name: "Red",       color: "#FF0000", hex: 0xff0000, x: 0.8, y: H, z: 2.0 },
  "08:f9:e0:61:1b:c7": { id: "02", name: "Orange",    color: "#FF5000", hex: 0xff5000, x: 2.0, y: H, z: 2.0 },
  "48:55:19:ec:2f:04": { id: "04", name: "Lime",      color: "#B4FF00", hex: 0xb4ff00, x: 3.2, y: H, z: 2.0 },
  // Front row (z=0.8) — Hot Pink, Blue, Crimson (door is in front of Crimson)
  "48:55:19:ec:d2:42": { id: "11", name: "Hot Pink",  color: "#FF0096", hex: 0xff0096, x: 0.8, y: H, z: 0.8 },
  "c8:c9:a3:38:ec:00": { id: "08", name: "Blue",      color: "#0000FF", hex: 0x0000ff, x: 2.0, y: H, z: 0.8 },
  "08:f9:e0:68:ea:07": { id: "12", name: "Crimson",   color: "#FF0032", hex: 0xff0032, x: 3.2, y: H, z: 0.8 },
  // Outside door (in front of Crimson, between room and table)
  "48:55:19:ec:24:29": { id: "13", name: "Peach",     color: "#FF9632", hex: 0xff9632, x: 3.2, y: H, z: -0.5 },
  // Offline — not in the room, hide off-screen
  "48:55:19:ef:0a:8d": { id: "06", name: "Mint (offline)", color: "#00FFB4", hex: 0x00ffb4, x: -99, y: H, z: -99 },
  // Our table — left of door, further out into venue
  // Indigo on left (outer edge), White on right (outer edge)
  "48:55:19:ee:65:c7": { id: "09", name: "Indigo",    color: "#5000FF", hex: 0x5000ff, x: 0.5, y: H, z: -2.8 },
  "c8:c9:a3:39:a7:79": { id: "07", name: "White",     color: "#FFFFFF", hex: 0xffffff, x: 2.0, y: H, z: -2.8 },
};

export const SENSORS = {
  // Conference room boards
  "10.9.0.242": { label: "D", x: 0.5, y: 1.0, z: 3.0, zone: "conf" },
  "10.9.0.110": { label: "C", x: 3.5, y: 1.0, z: 2.0, zone: "conf" },
  // Our table boards
  "10.9.0.237": { label: "A", x: 0.8, y: 1.0, z: -2.0, zone: "table" },
  "10.9.0.199": { label: "B", x: 1.8, y: 1.0, z: -2.0, zone: "table" },
};

// Which sensors each candle connects to
// Conf room candles → conf room boards (C, D)
// Table candles → table boards (A, B)
// Peach (hallway) → both
const CONF_SENSORS = ["10.9.0.242", "10.9.0.110"];
const TABLE_SENSORS = ["10.9.0.237", "10.9.0.199"];
const CONF_CANDLES = [
  "c8:c9:a3:39:a9:07", "48:55:19:ec:d1:8e", "08:f9:e0:69:0c:68",  // back row
  "4c:75:25:94:d2:10", "08:f9:e0:61:1b:c7", "48:55:19:ec:2f:04",  // middle row
  "48:55:19:ec:d2:42", "c8:c9:a3:38:ec:00", "08:f9:e0:68:ea:07",  // front row
];
const TABLE_CANDLES = ["48:55:19:ee:65:c7", "c8:c9:a3:39:a7:79"]; // Indigo, White
const HALLWAY_CANDLE = "48:55:19:ec:24:29"; // Peach

export function getSensorsForCandle(mac) {
  if (CONF_CANDLES.includes(mac)) return CONF_SENSORS;
  if (TABLE_CANDLES.includes(mac)) return TABLE_SENSORS;
  if (mac === HALLWAY_CANDLE) return [...CONF_SENSORS, ...TABLE_SENSORS];
  return [];
}

// Known presences — people we can identify
export const KNOWN_PRESENCES = {
  "da:95:6a:26:6c:05": { name: "Mattie", color: "#FF4488", hex: 0xff4488 },
  "7e:bb:d4:3e:14:11": { name: "Brian", color: "#44FF88", hex: 0x44ff88 },
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
