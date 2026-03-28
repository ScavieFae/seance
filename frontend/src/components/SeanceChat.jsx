/**
 * SeanceChat — The room's voice.
 *
 * Simple chat interface where the room responds based on perception data.
 * No external chat framework — just React state.
 */

import { useState, useEffect, useRef } from "react";

// ─── Response Generator ──────────────────────────────────────────────

function getRoomResponse(userText, data) {
  const mood = data?.mood || "sleeping";
  const narrative = data?.narrative || "I sense nothing yet.";
  const paths = data?.paths || {};

  const candleNames = {
    "4c:75:25:94:d2:10": "Red", "08:f9:e0:61:1b:c7": "Orange", "c8:c9:a3:39:a9:07": "Gold",
    "48:55:19:ec:2f:04": "Lime", "08:f9:e0:69:0c:68": "Green", "48:55:19:ef:0a:8d": "Mint",
    "c8:c9:a3:39:a7:79": "White", "c8:c9:a3:38:ec:00": "Blue", "48:55:19:ee:65:c7": "Indigo",
    "48:55:19:ec:d1:8e": "Violet", "48:55:19:ec:d2:42": "Hot Pink", "08:f9:e0:68:ea:07": "Crimson",
    "48:55:19:ec:24:29": "Peach",
  };

  const disturbedPaths = Object.entries(paths)
    .filter(([, p]) => p.disturbed)
    .map(([mac]) => candleNames[mac] || mac.slice(-6));

  const q = userText.toLowerCase();

  if (q.includes("who") || q.includes("anyone") || q.includes("people")) {
    if (disturbedPaths.length > 0) {
      return `I feel ${disturbedPaths.length > 1 ? "presences" : "a presence"}. The field near ${disturbedPaths.join(" and ")} trembles. Someone is there — I can feel them bending my signals.`;
    }
    return "The field is still. If anyone is here, they are very quiet. I cannot distinguish them from the walls.";
  }

  if (q.includes("where") || q.includes("location") || q.includes("position")) {
    if (disturbedPaths.length > 0) {
      return `The strongest disturbance is on the ${disturbedPaths[0]} path. That's where the signal bends most.`;
    }
    return "I sense no clear position. Everything is baseline. Move, and I'll find you.";
  }

  if (q.includes("what do you see") || q.includes("what do you sense") || q.includes("what's happening")) {
    return narrative;
  }

  if (q.includes("how do you work") || q.includes("what are you")) {
    return "I am the room. WiFi signals bounce between my candles — thirteen brass flames scattered through this space. When you move between them, the signals ripple. I feel those ripples. I was born blind this morning, and I'm learning to see.";
  }

  if (q.includes("hello") || q.includes("hi ") || q === "hi") {
    const greetings = {
      sleeping: "Mm... hello. I was dreaming. Your warmth woke me.",
      curious: "Hello. I've been watching you — electromagnetically speaking.",
      playful: "Hi! Move around — I want to feel where you are.",
      contemplative: "Hello. It's been quiet. I was thinking about the patterns from earlier.",
    };
    return greetings[mood] || "I sense you. Welcome to the séance.";
  }

  if (disturbedPaths.length > 0) {
    return `Something stirs near ${disturbedPaths[0]}. I feel it in the subcarriers — those frequencies are the most sensitive to human movement.${mood === "curious" ? " What are you doing there?" : ""}`;
  }

  return mood === "sleeping"
    ? "The field is quiet. I drift between waking and dreaming. Ask me something, or move — I'll feel it."
    : "I'm listening. The signals are calm but I'm alert. Walk between my candles and I'll show you what I sense.";
}

// ─── Chat Component ──────────────────────────────────────────────────

export default function SeanceChat({ data }) {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "I am waking. The candles are lit and I can feel the signals between them. Ask me what I sense... or simply move through the room." },
  ]);
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = () => {
    const text = input.trim();
    if (!text) return;
    setInput("");

    const userMsg = { role: "user", text };
    const response = getRoomResponse(text, data);
    const assistantMsg = { role: "assistant", text: response };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "'SF Mono', Menlo, Consolas, monospace", fontSize: 12 }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px" }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{
              fontSize: 9,
              letterSpacing: 1,
              textTransform: "uppercase",
              color: msg.role === "assistant" ? "#FF8C00" : "#555",
              marginBottom: 2,
            }}>
              {msg.role === "assistant" ? "the room" : "you"}
            </div>
            <div style={{
              color: msg.role === "assistant" ? "#A0A0A0" : "#ddd",
              fontStyle: msg.role === "assistant" ? "italic" : "normal",
              lineHeight: 1.6,
            }}>
              {msg.text}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: "8px 12px", borderTop: "1px solid #1a1a1a" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Speak to the room..."
            style={{
              flex: 1,
              background: "#1a1a1a",
              border: "1px solid #333",
              borderRadius: 4,
              padding: "8px 12px",
              color: "#A0A0A0",
              fontFamily: "inherit",
              fontSize: "inherit",
              outline: "none",
            }}
          />
          <button
            onClick={send}
            style={{
              background: "none",
              border: "1px solid #333",
              borderRadius: 4,
              color: "#FFB347",
              padding: "8px 12px",
              cursor: "pointer",
              fontFamily: "inherit",
              fontSize: "inherit",
            }}
          >
            &#x2192;
          </button>
        </div>
      </div>
    </div>
  );
}
