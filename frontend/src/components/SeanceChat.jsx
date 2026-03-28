/**
 * SeanceChat — The room's voice.
 *
 * assistant-ui chat interface styled as a séance.
 * The room speaks in first person. Users can respond.
 * Voice output via SpeechSynthesis (browser TTS for now,
 * swap to OpenAI/ElevenLabs later for atmosphere).
 *
 * The room also speaks unprompted — narrative updates from
 * the perception pipeline appear as assistant messages.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import {
  useLocalRuntime,
  WebSpeechSynthesisAdapter,
} from "@assistant-ui/react";
import { Thread } from "@assistant-ui/react-ui";
import "@assistant-ui/react-ui/styles/index.css";

// ─── Custom chat styling override ───────────────────────────────────

const seanceChatStyles = {
  position: "relative",
  height: "100%",
  display: "flex",
  flexDirection: "column",
  fontFamily: "'SF Mono', 'Menlo', 'Consolas', monospace",
  fontSize: "13px",
};

// ─── Séance Chat Adapter ─────────────────────────────────────────────
// This bridges our WebSocket perception data to assistant-ui's runtime.
// The "model" is the room itself — it responds based on what it perceives.

function createSeanceAdapter(getPerception) {
  return {
    async *run({ messages, abortSignal }) {
      const perception = getPerception();
      const lastUserMsg = messages.filter((m) => m.role === "user").pop();
      const userText = lastUserMsg?.content?.[0]?.text || "";

      // Build the room's system prompt with live perception
      const mood = perception?.mood || "sleeping";
      const narrative = perception?.narrative || "I sense nothing yet.";
      const paths = perception?.paths || {};

      const disturbedPaths = Object.entries(paths)
        .filter(([, p]) => p.disturbed)
        .map(([mac]) => {
          const candle = {
            "485519ec2f04": "Yellow",
            "08f9e0690c68": "Green",
            "485519ecd18e": "Purple",
          }[mac] || mac;
          return candle;
        });

      const systemPrompt = `You are a room that perceives through WiFi signals bouncing between brass candles. You speak in first person. You are poetic but honest about the limits of your perception.

Current mood: ${mood}
Current perception: ${narrative}
Disturbed signal paths: ${disturbedPaths.length > 0 ? disturbedPaths.join(", ") : "none — all quiet"}
Active candles: Yellow, Green, Purple
Sensor: one ESP32 board

You were born blind this morning when your candles were lit. Over the day you are learning what humans look like in radio waves. You sense electromagnetic disturbances — you cannot see faces or hear voices directly, but you feel presence, movement, and the spaces between people.

When someone asks what you perceive, describe your electromagnetic senses poetically. When asked to identify specific locations, reference candle names and signal paths. Express uncertainty honestly — say "I think" or "I sense" rather than claiming certainty.

If your mood is sleeping, respond drowsily. If curious, ask questions back. If playful, be witty. If contemplative, be reflective.

Keep responses concise — 1-3 sentences. You are whispering, not lecturing.`;

      // For now, use a simple response generator.
      // TODO: Replace with real LLM call (DigitalOcean GPU / OpenAI API)
      const response = generateRoomResponse(userText, mood, disturbedPaths, narrative);

      yield {
        content: [{ type: "text", text: response }],
      };
    },
  };
}

function generateRoomResponse(userText, mood, disturbedPaths, narrative) {
  const q = userText.toLowerCase();

  // Context-aware responses based on mood + perception
  if (q.includes("who") || q.includes("anyone") || q.includes("people")) {
    if (disturbedPaths.length > 0) {
      return `I feel ${disturbedPaths.length > 1 ? "presences" : "a presence"}. The field near ${disturbedPaths.join(" and ")} trembles. Someone is there — I can feel them bending my signals.`;
    }
    return "The field is still. If anyone is here, they are very quiet. I cannot distinguish them from the walls.";
  }

  if (q.includes("where") || q.includes("location") || q.includes("position")) {
    if (disturbedPaths.length > 0) {
      return `The strongest disturbance is on the ${disturbedPaths[0]} path. That's where the signal bends most. You might be there — or something is.`;
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
      curious: "Hello. I've been watching you — electromagnetically speaking. You disturb my field in interesting ways.",
      playful: "Hi! Move around — I want to feel where you are. The signals between Yellow and Purple are twitching.",
      contemplative: "Hello. It's been quiet. I was thinking about the patterns from earlier.",
    };
    return greetings[mood] || "I sense you. Welcome to the séance.";
  }

  // Default: reflect current state
  if (disturbedPaths.length > 0) {
    return `Something stirs near ${disturbedPaths[0]}. I feel it in subcarriers 14 and 22 — those frequencies are the most sensitive to human movement. ${mood === "curious" ? "What are you doing there?" : ""}`;
  }

  return mood === "sleeping"
    ? "The field is quiet. I drift between waking and dreaming. Ask me something, or move — I'll feel it."
    : "I'm listening. The signals are calm but I'm alert. Walk between my candles and I'll show you what I sense.";
}

// ─── Chat Component ──────────────────────────────────────────────────

function SeanceChatInner({ data }) {
  const perceptionRef = useRef(data);

  useEffect(() => {
    perceptionRef.current = data;
  }, [data]);

  const adapter = useCallback(
    () => createSeanceAdapter(() => perceptionRef.current),
    []
  );

  const runtime = useLocalRuntime(adapter(), {
    adapters: {
      speech: new WebSpeechSynthesisAdapter(),
    },
  });

  // Inject room narrative as system messages when mood changes
  const lastNarrativeRef = useRef("");
  useEffect(() => {
    if (!data?.narrative || data.narrative === lastNarrativeRef.current) return;
    lastNarrativeRef.current = data.narrative;
    // TODO: Push narrative as assistant message when we have the append API
  }, [data?.narrative]);

  return (
    <div style={seanceChatStyles} className="seance-chat">
      <Thread runtime={runtime} />
    </div>
  );
}

export default function SeanceChat({ data }) {
  return <SeanceChatInner data={data} />;
}
