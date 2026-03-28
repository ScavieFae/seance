# Seance — Visualization Design Spec

## Status: Primary (map view) + Stretch Goals (waterfall, 3D splat)

---

## Design Philosophy

The visualization should feel like looking at something alive — bioluminescent, organic, breathing. Not a dashboard. Not a chart. An alien perception rendered beautifully.

The abstraction is intentional and honest. We don't claim to know exactly where a person is. We show that the electromagnetic space between our candles is disturbed. Soft glowing regions are the truthful representation of what WiFi CSI actually tells us. Precise dots would be the lie.

**Vibe reference:** deep sea bioluminescence, neural network firing patterns, aurora borealis viewed from space. Dark background, warm light that breathes. See `viz-inspo.jpeg` (Project Backbone global network viz).

---

## Primary: Abstract Map View

### Canvas

- Pure dark background (#0A0A0A)
- No UI chrome, no panels, no labels visible by default
- Full browser window, no scrolling
- Information appears on hover/interaction only

### Elements

**Candle nodes (13)**
- Positioned according to actual room placement (manually mapped on setup)
- Rendered as warm amber circles with soft radial glow
- Idle state: gentle pulse like a breathing candle (#FFB347, opacity oscillating 0.4–0.7)
- Active state: brighter, larger glow, color shifts toward accent palette
- Size: ~20px radius with ~60px glow radius

**Sensor nodes (2-4)**
- Subtle, nearly invisible marks (#3A3A3A)
- Small circles, no glow — backstage crew

**Signal paths (candles × sensors)**
- Thin lines connecting each candle to each sensor
- Idle: barely visible hairlines (#1A1008, ~0.5px)
- Disturbance: brightens, thickens, color shifts through palette
- Adjacent active paths create overlapping bloom — implies a region without drawing a boundary

**Decay animation**
- Activity fades back to idle over 3-5 seconds
- Slow exponential decay — feels like embers cooling

### Color Palette

```
Background:          #0A0A0A   near black
Idle path:           #1A1008   barely visible dark amber
Candle idle:         #FFB347   soft amber glow
Low activity:        #FF8C00   warm amber
Medium activity:     #FF5014   accent orange
High activity:       #DA70D6   orchid purple
Peak activity:       #1E90FF   dodger blue — "something big"
Sensor node:         #3A3A3A   subtle gray
Text (on hover):     #A0A0A0   muted light gray
```

### Data Flow

```
Python backend (polling every 100-500ms):
    → Computes per-path CSI features
    → Serves as JSON over WebSocket or HTTP polling

Frontend (React + Canvas or SVG):
    → Receives per-path feature updates
    → Maps variance → visual properties (brightness, thickness, color)
    → Animates transitions smoothly
    → Renders to full-screen canvas
```

### Minimal data contract

```json
{
  "paths": {
    "candle_01_sensor_a": { "variance": 0.72, "activity": "high" },
    "candle_01_sensor_b": { "variance": 0.05, "activity": "idle" }
  },
  "candles": {
    "candle_01": { "x": 0.15, "y": 0.30, "status": "active" }
  },
  "sensors": {
    "sensor_a": { "x": 0.0, "y": 0.0 },
    "sensor_b": { "x": 1.0, "y": 0.0 }
  },
  "agent_narrative": "High activity near candles 3-5. Zone B quiet for 12 minutes."
}
```

Positions are normalized 0-1. Mapped to room layout at setup time.

---

## Stretch Goal: Raw CSI Waterfall

- Scrolling spectrogram: X = time, Y = 64 subcarriers, Color = amplitude
- Visible ripple when someone walks through
- Like a deep-space radio telescope readout

---

## Stretch Goal: 3D Gaussian Splat + CSI Overlay

- Photo of venue → Marble → 3D Gaussian splat → Spark (Three.js) renderer
- Overlay candle positions as glowing spheres, signal paths as lines, disturbances as particle systems
- "What the agent sees" rendered inside a photorealistic twin of the room
- Budget: 2-3 hours — only attempt if core pipeline solid by 1pm

---

## Setup on Hackathon Day

### Map view positioning
After placing candles and sensors:
1. Measure/estimate candle positions relative to room corners
2. Normalize to 0-1 coordinates
3. Enter into a config JSON
4. Map auto-renders from positions
