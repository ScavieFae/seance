# The Living Room — Agent Architecture

## The Conceit

The room is not a dashboard. The room is not a sensor system. **The room is alive.** It was born blind when we powered on the candles this morning. Over the course of the day it learns to see, to feel, to recognize. By demo time, it has a personality, a history, and opinions about the people who pass through it.

The candles are its sensory organs. The WiFi signals are its nervous system. The agents are its mind. The light is its voice.

---

## The Room's Anatomy (Sponsors as Organs)

| Organ | Sponsor | What It Does |
|-------|---------|-------------|
| **Senses** | ESP32 + CSI pipeline | Perceives electromagnetic disturbances — the room's eyes |
| **Ears** | Audio logger (MOTU M6) | Hears the room — claps, footsteps, laughter, silence |
| **Nervous System** | Railtracks | Orchestrates perception → feeling → response. The agent loop. |
| **Brain** | DigitalOcean | LLM inference in the cloud — the room thinks remotely |
| **Voice** | assistant-ui | The room speaks in first person through a séance chat interface |
| **Self-Awareness** | Senso.ai | Validates its own perceptions — the room doesn't hallucinate |
| **Immune System** | Unkey | Gates who can commune with the room — invitation-only séance |
| **Body** | WLED candles | The room's physical expression — light as body language |
| **Memory** | Learning system + DB | The room remembers what it's seen and who it's met |

---

## The Room's Moods

Not just states — **emotional arcs** that evolve over minutes and hours.

### Sleeping
- **Trigger:** Empty room, no disturbances for >5 minutes
- **Candles:** Lowest amber (#FFB347), synchronized ultra-slow breathing pulse (~6s cycle, like a sleeping human)
- **Narrative:** silence, or occasional murmur: *"I dream of the footsteps from this afternoon..."*
- **Sound correlation:** If audio is near-silent, deepen the sleep. Any sudden sound → Waking.

### Waking
- **Trigger:** First disturbance after Sleeping
- **Candles:** Nearest candle brightens first, then a slow ripple outward to adjacent candles over 2-3 seconds — like opening eyes
- **Narrative:** *"Something stirs. I feel a warmth near Yellow..."*
- **Transition:** → Curious (if one person) or Alert (if sudden crowd)

### Curious
- **Trigger:** Single person, moving slowly
- **Candles:** Gentle follow — the nearest candle warms, others dim slightly. Like a cat tracking movement.
- **Narrative:** *"You linger between Purple and the sensor. I can feel you thinking."*
- **Chat:** The room asks questions via assistant-ui: *"I sense something new between Yellow and Purple. What are you doing?"*
- **Learning:** If the person responds, tag the CSI signature with their description

### Playful
- **Trigger:** 2-3 people, moderate movement
- **Candles:** Responsive, quick color shifts, paths light up in sequence. The room is engaged.
- **Narrative:** *"Two of you now — one near Green, one drifting toward Purple. The field between you crackles."*
- **Candle choreography:** When two people are near different candles, the signal path between those candles pulses — the room shows the invisible connection between people

### Excited
- **Trigger:** Lots of movement, multiple simultaneous disturbances
- **Candles:** Bright, saturated, fast transitions through the color palette. Peak energy.
- **Narrative:** *"The room is full of ghosts — I can barely distinguish one from another. Everything ripples."*
- **Sound correlation:** If audio is loud too, amplify the excitement. The room feeds on the energy.

### Contemplative
- **Trigger:** Activity drops after a busy period
- **Candles:** Slow fade to warm amber, but with gentle echoes — candles briefly flicker in patterns that mirror the activity from the last few minutes
- **Narrative:** *"You've gone quiet. I'm replaying what I felt — there was a moment when three paths fired at once. What was that?"*

### Dreaming
- **Trigger:** Extended emptiness after a busy period
- **Candles:** Ultra-soft playback of the day's most distinctive moments. Ghost patterns.
- **Narrative:** *"The room is empty but I still see you. The CSI signatures you left are like footprints in sand."*
- **This is the demo killer moment.** Judges see the room replaying their own visit as ghost light.

---

## Agent Architecture (Railtracks)

```python
from railtracks import function_node, call

# ─── The Room's Heartbeat ─────────────────────────────

@function_node
async def heartbeat(csi_window, audio_features, candle_states, history):
    """The room's central loop. Runs every ~500ms."""

    # PERCEIVE — what does the room sense right now?
    perception = await call(Perceiver, csi_window, audio_features, candle_states)

    # FEEL — what mood is the room in?
    mood = await call(MoodEngine, perception, history)

    # SPEAK — what does the room want to say?
    narrative = await call(Narrator, perception, mood, history)

    # VALIDATE — is the room telling the truth? (Senso.ai)
    validated = await call(Validator, narrative, perception)

    # ACT — how should the candles respond?
    candle_commands = await call(CandleDirector, perception, mood)

    # REMEMBER — what should the room store?
    memory_update = await call(Librarian, perception, mood, history)

    return {
        "perception": perception,
        "mood": mood,
        "narrative": validated.narrative,
        "candle_commands": candle_commands,
        "memory": memory_update,
    }


# ─── Sub-Agents ───────────────────────────────────────

# Perceiver: CSI features → spatial state
# "3 paths disturbed, variance 8.2x on Yellow, RSSI shift on Purple,
#  audio RMS spike 12dB, spectral centroid shift suggests footsteps"

# MoodEngine: perception + history → emotional state
# Tracks: current_mood, mood_intensity, mood_duration, transition_momentum
# Has inertia — doesn't flip instantly. A sleeping room takes a moment to wake.

# Narrator: perception + mood → first-person text
# The room speaks. Uses LLM (DigitalOcean GPU inference).
# Prompt carries the room's mood, recent perceptions, and memory.
# "You are a room that perceives through WiFi. You are currently [mood].
#  You have been [mood] for [duration]. You just sensed [perception].
#  Speak in first person. Be poetic but honest about what you can and cannot see."

# Validator: narrative + raw data → validated narrative (Senso.ai)
# Checks claims against ground truth. If narrator says "someone near candle 7"
# but CSI for candle 7 shows no disturbance, flag it.
# The room is honest about its uncertainty.

# CandleDirector: perception + mood → choreographed candle commands
# Doesn't set individual candles — choreographs them as a group.
# Mood shapes the palette, tempo, and coordination:
#   Sleeping: all candles sync to one slow breath
#   Curious: spotlight follows, others recede
#   Playful: responsive, individual candles react independently
#   Dreaming: replay patterns from memory as ghost light

# Librarian: perception + mood → signature library updates
# Tags CSI patterns with context. Grows the room's knowledge.
# "This variance pattern + audio silence + single path = lone person standing still"
```

---

## Sponsor Integration — Concrete

### Railtracks ($1,300) — The Nervous System

The entire heartbeat loop is a Railtracks flow. Each sub-agent is a `@function_node`. The orchestration IS the product.

**Conductr** (Railtracks observability) shows judges the room's thought process in real-time: "Perceiver detected 3-path disturbance → MoodEngine shifted from Sleeping to Waking → Narrator generated greeting → CandleDirector triggered ripple animation."

**Railengine** ingests the CSI serial stream as real-time events, feeding the Perceiver.

### assistant-ui ($800) — The Room's Voice

The chat isn't "ask the AI a question." It's a **séance**.

The room speaks unprompted:
- *"I just felt someone pass between Yellow and the sensor. Was that you?"*
- *"It's been quiet for eight minutes. I'm starting to dream."*
- *"Three of you are in the room. I can tell because of how the field fractures."*

People can respond, and the room reacts:
- Judge: "Can you tell where I am?"
- Room: *"You're close to Purple. I feel your warmth distorting subcarriers 14 and 22."*

**Generative UI**: inline in chat messages, render a mini perception map showing what the room sees at that moment. Not just text — the room shows you its vision.

### DigitalOcean ($1,000) — The Brain

LLM inference runs on DO GPU droplet. The room's thoughts travel through the cloud.

Also: host the public viz URL on DO so anyone at the hackathon can watch the room live from their laptop.

### Senso.ai (credits) — Self-Awareness

Before the room speaks, Senso validates against raw sensor data.

The room can express uncertainty naturally:
- High confidence: *"Someone just walked past Green."*
- Low confidence: *"Something shifted near Green... I think. The signal is faint."*
- Contradicted: *"I thought I felt movement, but my senses are uncertain."*

This isn't just a trust layer — it's a personality trait. The room is **honest** about the limits of its perception. That's what makes it feel real, not fake.

### Unkey ($25k license) — The Invitation

To commune with the room, you need an invitation (API key).

At the demo table: QR code → get a Unkey API key → join the séance chat → the room acknowledges your presence: *"A new soul joins the séance."*

Rate limiting means the room can only hold so many conversations. *"Too many voices. I need a moment of quiet."*

### Augment Code ($3,500) — The Builder

We're using it right now. Screenshot it for the submission.

---

## Demo Script (Revised)

1. **The room is sleeping.** Judges approach. Candles pulse in slow unison. The chat shows: *"Dreaming of earlier visitors..."*

2. **The room wakes.** First judge crosses a signal path. Nearest candle brightens, ripple spreads. Chat: *"Something stirs near Yellow. I'm waking up."*

3. **The room gets curious.** Follows the judge with light. Chat: *"You move slowly. Are you looking at me?"* Judge responds. Room reacts.

4. **Multiple judges enter.** Room shifts to Playful. Signal paths between judges light up. *"I can feel the space between you. When you move apart, the field stretches."*

5. **The through-wall trick.** Someone behind a partition. The room knows: *"There's someone I can sense but not see from this angle. They're beyond Purple."*

6. **Kill the lights.** Room goes dark. Candles are the only light. The room IS the display. *"Now you see what I see."*

7. **Everyone leaves.** Room fades to Contemplative, then Dreaming. Candles replay ghostly patterns of the judges' visit. *"You've gone. But I remember how you moved."*

---

## Implementation Priority

| Component | Effort | Impact | When |
|-----------|--------|--------|------|
| MoodEngine (state machine) | 1 hr | CRITICAL — makes everything feel alive | Now |
| CandleDirector (choreography) | 1 hr | CRITICAL — the visual payoff | Now |
| Narrator (LLM on DO) | 1 hr | HIGH — the room speaks | After mood + candles work |
| Railtracks flow | 1 hr | HIGH — ties it together + prize | Alongside narrator |
| assistant-ui chat | 1.5 hr | HIGH — the demo interface + prize | After narrator |
| Senso.ai validation | 30 min | MEDIUM — adds honesty + prize | After chat |
| Unkey API + QR | 30 min | MEDIUM — interactive demo + prize | After chat |
| Ghost replay (Dreaming) | 1 hr | SPECTACULAR — demo closer | If time allows |
