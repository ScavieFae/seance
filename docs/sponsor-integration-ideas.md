# Sponsor Integration Ideas — Seance

Beyond Brian's Tier 1/2/3 analysis in the master plan. New angles, surprises, and the elusive obvious ones.

---

## The Big Picture

Seance has an unusual advantage: it's a **physical sensing system with an agent brain, a data pipeline, and a public-facing API surface**. That means almost every sponsor category has a real integration point — not a forced one. The trick is making each integration feel native to the project rather than bolted on.

**Total addressable prize pool if we hit all viable tracks: ~$8,400 cash + $25k Unkey license + credits**

---

## Revised Rankings & New Ideas

### 1. Unkey — The Elusive Obvious ($25k license value)

Brian had this in Tier 2. It should be **Tier 0**.

We're already building a perception API and candle control endpoints. Unkey integration is ~15 lines of Python. But the real play:

**"The Séance API — let the room speak to other apps."**
- Expose `/api/perception` (what does the room see right now?)
- Expose `/api/candles/{id}/state` (read) and `/api/candles/{id}/control` (write)
- Expose `/api/events/stream` (SSE/WebSocket of disturbance events)
- Gate everything with Unkey API keys
- **Print QR codes at the demo table** — other hackathon attendees get an API key and can query the room from their phones or even wire it into THEIR projects
- Rate limit with Unkey so nobody hammers the candles

This makes the demo interactive at scale. Judges walk up, scan a QR code, and their phone shows them what the room perceives. That's memorable. And Unkey's dashboard gives us real-time analytics of who's hitting the API.

**Integration time: 30 min**

---

### 2. Railtracks — The Agent's Nervous System ($1,300)

Brian's instinct is right but the framing can be sharper. Railtracks is Python-native async agents with `@function_node` and `call()`. Our perception loop maps directly:

```python
@function_node
async def perceive(csi_window):
    features = await call(FeatureExtractor, csi_window)
    spatial = await call(SpatialFusion, features)
    narrative = await call(Narrator, spatial)
    commands = await call(CandleController, spatial)
    return {"narrative": narrative, "commands": commands}
```

But the **surprise play**: Railtracks just launched **Railengine** (Jan 2026) — a real-time event-based ingestion engine for streaming data. CSI serial data is literally a stream of events. If we can pipe our serial CSI stream through Railengine, we get:
- Real-time event ingestion (CSI packets as events)
- Agent-ready structured data out the other end
- Built-in observability via their Conductr tool (we can show judges the agent's decision trace)

**Framing for judges: "Railtracks is the agent's nervous system. Railengine ingests the raw electromagnetic signals, Railtracks agents process them into perception, and Conductr lets you watch the agent think."**

**Integration time: 1.5 hours**

---

### 3. assistant-ui — The Séance Circle ($800)

Brian's right: chat interface for judges. But here's the deeper play that ties into the learning system:

**The agent doesn't just answer questions — it asks them.**

assistant-ui supports tool rendering and generative UI. When the agent detects a novel CSI pattern it can't classify, it posts a message in the chat: *"I sense something new between Yellow and Purple. Can someone near those candles tell me what they're doing?"*

The judge types "I'm waving my hand." The agent labels that CSI signature as `hand_wave_zone_yellow_purple` and adds it to its library. **The chat IS the learning interface.**

Components to use:
- Thread for the conversation
- Tool UI to render live perception maps inline in chat messages
- Custom composer with quick-action buttons ("Calibrate room", "What do you see?", "Who's here?")

**Framing for judges: "The chat isn't just a query interface — it's how the agent learns. It asks the room to teach it."**

**Integration time: 1.5 hours**

---

### 4. Augment Code — Free Money ($3,500)

Largest cash prize. Usage-based — just use it while coding. Make sure to:
- Have it visible/running during the hackathon
- Reference it in the Devpost submission
- Screenshot some interactions where it helped build the pipeline

**Integration time: 0 (just use it)**

---

### 5. DigitalOcean — The Cloud Brain ($1,000 + credits)

Brian says run LLM inference there. Yes, but also:

**Host the live visualization on DigitalOcean.** Deploy the React viz as a static site on DO App Platform, with the WebSocket backend on a DO droplet. Now anyone at the hackathon can open a URL and see the room's perception in real time — not just people at our demo table.

Architecture story:
- Edge: ESP32 sensors capture CSI → laptop processes → pushes to cloud
- Cloud (DO): LLM inference + visualization hosting + perception API
- Back to edge: candle control commands flow back down

**Bonus**: Use DO's managed database to persist the learning system's signature library. The agent's knowledge survives restarts.

**Integration time: 1 hour**

---

### 6. Senso.ai — The Trust Layer (up to $3,000 credits)

Brian skipped this for lack of info. Now we know: **Senso.ai is a trust/evaluation layer for AI agents.** They score agent responses against ground truth.

This is actually a great fit because our agent makes claims about physical reality that are verifiable:

**"Senso.ai validates that our agent isn't hallucinating about the room."**

- Agent says "I detect someone near candle 7" → Senso checks against the raw CSI data (ground truth)
- Agent says "The room has been empty for 5 minutes" → Senso evaluates against the sensor log
- Track accuracy over time: the agent's Senso trust score should improve as it learns

This directly addresses the #1 concern with any AI perception system: **is it making things up?** Senso proves it's not.

**Framing for judges: "How do you trust an AI that claims to see through walls? We use Senso.ai to continuously validate the agent's perceptions against raw sensor ground truth."**

**Integration time: 1 hour (depends on their API)**

---

### 7. Nexla — The Data Backbone ($900 + credits)

Brian's framing (CSI as data pipeline problem) is correct. Sharper angle:

**Nexla as the translation layer between modalities.**

We have three data streams that need to be correlated:
- CSI serial stream (921600 baud, custom format)
- Audio features (JSONL, 2Hz)
- Candle state polling (HTTP JSON, 2Hz)

Nexla's "Nexsets" (virtual data products with schemas) could define each stream as a typed data product. Their Express.dev could transform raw CSI into structured perception. Their connectors could route the fused output to the agent, the viz, and the API simultaneously.

**But be honest about priority**: this is the hardest integration to make feel natural in a hackathon timeframe. Only do it if the core pipeline is solid by 1pm.

**Integration time: 1.5 hours**

---

### 8. WorkOS — The Séance Circle (venue partner, no cash prize but goodwill)

Brian says skip. I say consider a **5-minute integration** for venue-partner goodwill:

**"Join the Séance"** — WorkOS SSO to authenticate attendees who want to interact with the agent or get an API key. When someone authenticates:
1. They get a Unkey API key automatically
2. Their name appears in the agent's awareness ("A new participant has joined the séance")
3. They can now chat with the agent and help train it

WorkOS AuthKit has a hosted login page that takes minutes to set up. This ties WorkOS → Unkey → assistant-ui into a single onboarding flow.

Only worth doing if Unkey and assistant-ui are already working.

**Integration time: 30 min**

---

## Priority Execution Order

Given the hackathon timeline (core pipeline must be solid first):

| Priority | Sponsor | When | Effort | Prize |
|----------|---------|------|--------|-------|
| 1 | Augment Code | All day | 0 | $3,500 |
| 2 | Unkey | After core pipeline | 30 min | $25k license |
| 3 | assistant-ui | With agent brain | 1.5 hr | $800 |
| 4 | Railtracks | With agent brain | 1.5 hr | $1,300 |
| 5 | DigitalOcean | After viz works | 1 hr | $1,000 |
| 6 | Senso.ai | After agent works | 1 hr | credits |
| 7 | WorkOS | If time allows | 30 min | goodwill |
| 8 | Nexla | If time allows | 1.5 hr | $900 |

---

## Wild Ideas (if we're ahead of schedule)

**Electromagnetic Portraits**: Over the course of the day, accumulate each person's "WiFi fingerprint" — how their body uniquely distorts the CSI field. At demo time, generate a visual "electromagnetic portrait" of each judge. "This is what you look like in radio waves."

**Candle Personalities via Railtracks**: Each candle gets a micro-agent with a personality derived from its observations. Yellow says "Someone keeps hovering near me, I think they like my warmth." Purple says "It's been lonely on this side of the room." The meta-agent synthesizes them into a room narrative. Theatrical, memorable, maps to Railtracks multi-agent patterns.

**The Hive API**: Other hackathon teams use our Unkey-gated API to add "spatial awareness" to their own projects. A chatbot team wires in our perception feed so their bot knows when someone walks up. We become infrastructure for the whole hackathon. Judges see multiple teams citing us.

**Sound-to-Light Cross-Modal**: When audio spikes (someone claps, laughs), correlate with CSI disturbance in the same window. The agent says "I heard something loud and simultaneously felt a ripple near candle 5 — someone clapped over there." Proves true multimodal fusion. Uses the audio_logger + sensor_logger Brian already built.
