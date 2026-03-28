# Frontend Architecture — Séance

**Status:** Scaffolded, evolving. Hack mode — nothing is set in stone.

---

## Stack

- **Vite + React** — zero-config dev server, fast HMR
- **@assistant-ui/react** + **@assistant-ui/react-ui** — chat interface with built-in TTS
- **Three.js** via **@react-three/fiber** + **@react-three/drei** — 3D room visualization
- **WebSocket** — live data from `ws_bridge.py`

## Running

```bash
cd frontend
npm install
npm run dev          # dev server on :5173
```

Also run the data bridge (in another terminal):
```bash
python3 viz/ws_bridge.py --mock   # mock data, no hardware
python3 viz/ws_bridge.py          # real ESP32 data
```

## Layout

```
┌──────────────────────────────────┬──────────────┐
│                                  │   ⚵ Séance   │
│        3D Room View              │  commune w/   │
│    (rotatable, zoomable)         │   the room    │
│                                  │              │
│  Stats overlay (top-left)        │  [chat msgs]  │
│  Connection status (top-right)   │              │
│                                  │  [composer]   │
│  Narrative text (bottom)         │              │
└──────────────────────────────────┴──────────────┘
```

## Key Files

```
frontend/
├── src/
│   ├── App.jsx              — Main layout (room + chat side by side)
│   ├── App.css              — Layout + assistant-ui dark theme overrides
│   ├── index.css            — Global styles (dark, monospace)
│   ├── components/
│   │   ├── RoomView.jsx     — 3D Three.js room (R3F)
│   │   ├── SeanceChat.jsx   — assistant-ui chat with voice + room persona
│   │   └── StatsOverlay.jsx — HUD stats over the 3D view
│   ├── hooks/
│   │   └── useSeanceData.js — WebSocket hook, mock data fallback
│   └── lib/
│       └── config.js        — Candle positions, room dims, shared constants
├── package.json
└── vite.config.js
```

## Voice Output (TTS)

assistant-ui has built-in TTS via `SpeechSynthesisAdapter`:

```jsx
// Browser voices (works now, robotic):
const runtime = useLocalRuntime(adapter, {
  adapters: { speech: new WebSpeechSynthesisAdapter() }
});

// Custom TTS (swap later for atmosphere):
const customSpeech = {
  speak: async (text) => {
    const res = await fetch("/api/tts", { method: "POST", body: JSON.stringify({ text }) });
    const audio = new Audio(URL.createObjectURL(await res.blob()));
    audio.play();
    return { stop: () => audio.pause() };
  }
};
```

Each assistant message gets a "read aloud" button. For the séance, we can auto-speak room narratives.

## Data Contract

The viz and chat both consume the same WebSocket JSON from `ws_bridge.py`:

```json
{
  "paths": {
    "<mac>": {
      "variance_ratio": 4.2,
      "rssi": -42,
      "rssi_delta": -2.1,
      "packets": 350,
      "disturbed": true
    }
  },
  "meta": {
    "packets_per_sec": 85,
    "unique_macs": 6,
    "disturbance_count": 2,
    "uptime_s": 142
  },
  "narrative": "Motion detected between Yellow and the sensor.",
  "mood": "curious"
}
```

## Chat Persona

The room speaks in first person. The chat adapter currently uses a template-based response generator (no LLM yet). To swap in a real LLM:

1. Replace `generateRoomResponse()` in `SeanceChat.jsx` with an API call
2. The system prompt already carries live perception data (mood, disturbed paths, narrative)
3. Target: DigitalOcean GPU for inference (sponsor integration)

## What's Next

- [ ] Wire real LLM (DigitalOcean or OpenAI API)
- [ ] Auto-speak room narratives (not just on button click)
- [ ] Room-initiated messages (the room speaks unprompted when it detects something)
- [ ] Generative UI — inline perception maps in chat messages
- [ ] Custom TTS voice (ElevenLabs or OpenAI for atmosphere)
- [ ] Update candle positions from actual venue measurements
- [ ] Mobile responsive for QR-code demo
