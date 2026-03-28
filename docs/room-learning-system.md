# Room Learning System — How the Room Learns About Itself

## The Problem

We have rich sensor data flowing:
- **CSI** — 52 subcarrier amplitudes per packet, per candle-sensor path (~80 pkt/s)
- **Audio** — stereo spectral features at 2Hz (RMS, centroid, 6-band energy)
- **Camera** — annotated snapshots at 2Hz (JPEG + audio features JSONL)
- **Candle state** — RSSI, signal %, brightness, power draw from all 13 candles at 2Hz

The question: how does raw sensor noise become **understanding**?

---

## The Learning Stack

Five layers, each builds on the one below. You can stop at any layer and have something useful.

### Layer 0: Raw Streams
Everything Brian and the pipeline produce. No processing. Just timestamped sensor data flowing to disk.

```
snapshot_logger.py → data/snapshots/ (JPEG + JSONL)
sensor_logger.py  → data/sensor_log.jsonl
csi_collector.py  → data/csi/ (raw CSI JSONL)
```

All timestamps are ISO UTC. Everything correlatable by time.

### Layer 1: Baseline — "What does empty feel like?"

**Input:** 30-60 seconds of sensor data with confirmed empty room.
**Output:** Per-path statistical fingerprint of "nothing."

```python
baseline = {
    "computed_at": "2026-03-28T10:15:00Z",
    "duration_s": 30,
    "paths": {
        "485519ec2f04": {  # Yellow candle
            "rssi_mean": -42.3,
            "rssi_std": 1.1,
            "amp_mean_per_sc": [12.1, 8.4, ...],      # 52 values
            "amp_var_per_sc": [0.8, 0.3, ...],         # 52 values
            "amp_covariance_top10": [...],              # subcarrier correlations
        },
        ...
    },
    "audio": {
        "rms_mean": 0.001,
        "rms_std": 0.0003,
        "dominant_freq_mean": 0,
        "band_energy_mean": {...},
    },
    "candle_signal_mean": { "04": 72, "05": 68, "10": 65 },
}
```

**Why this matters:** Everything above this layer is measured as deviation FROM baseline. Without it, you're measuring absolute values that drift with temperature, device state, and RF environment.

**Auto-recalibration:** Re-compute baseline whenever the room has been quiet for >5 minutes. Track baseline drift over time — that's interesting data too.

### Layer 2: Event Detection — "Something happened"

**Input:** Live sensor streams + baseline.
**Output:** Discrete "events" — bounded time periods where something deviates from baseline.

No labels. No classification. Just: something changed, here's when, how much, and on which paths.

```python
event = {
    "id": "evt_00042",
    "start": "2026-03-28T14:15:01.200Z",
    "end": "2026-03-28T14:15:04.800Z",
    "duration_ms": 3600,

    # CSI signature
    "paths_affected": ["485519ec2f04", "485519ecd18e"],  # Yellow, Purple
    "peak_variance_ratio": 12.4,
    "mean_variance_ratio": 5.2,
    "hottest_subcarriers": [14, 22, 33],
    "temporal_profile": [1.0, 3.2, 8.1, 12.4, 9.0, 5.1, 2.3, 1.1],  # variance over event lifetime

    # Cross-modal
    "audio_rms_delta": 0.08,          # audio change during event
    "audio_band_signature": {...},     # which frequency bands changed
    "candle_signal_deltas": {"04": -3, "10": -5},  # RSSI shifts

    # Feature vector (for clustering/matching)
    "feature_vector": [...]  # normalized, fixed-length embedding of the above
}
```

**Detection algorithm:**
1. Compute rolling variance ratio per path (already in csi_collector.py)
2. When ANY path exceeds threshold (3x baseline variance) → event starts
3. When ALL paths return to <1.5x baseline for >1 second → event ends
4. Extract features from the event window
5. Cross-reference with audio features in the same time window

**Key insight:** Events are the atoms of the room's experience. Everything else operates on events.

### Layer 3: Clustering — "I've seen this kind of thing before"

**Input:** Collection of events.
**Output:** Discovered categories (unlabeled clusters).

```python
cluster = {
    "id": "cluster_A",
    "n_events": 47,
    "centroid": [...],           # mean feature vector
    "radius": 0.34,             # spread
    "exemplar_events": ["evt_00003", "evt_00019", "evt_00042"],
    "properties": {
        "typical_duration_ms": 3200,
        "typical_paths": ["Yellow", "Purple"],
        "typical_peak_ratio": 8.5,
        "has_audio_correlation": True,
        "frequency": "common",  # how often this type occurs
    },
    "label": null,               # no label yet — just a pattern
}
```

**Algorithm:** HDBSCAN (handles varying density, doesn't need k specified). Run incrementally as new events come in.

**The room's self-knowledge at this point:**
- "I experience about 5 distinct types of disturbance"
- "Type A happens often and involves Yellow+Purple paths for ~3 seconds"
- "Type B is rare, affects all paths simultaneously, and has a strong audio correlation"
- "Type C is subtle — low variance, long duration, only on one path"

Still no human labels. The room has organized its own experience.

### Layer 4: Grounding — "That thing I keep seeing? It's a person walking."

**Input:** Human annotations on a few events.
**Output:** Labeled clusters → the room can now name what it sees.

**Annotation interface:**
The séance chat. When the room detects an event it can't classify:

> *Room: "I feel something between Yellow and Purple. It's been there for 12 seconds, barely moving. I've seen this pattern 8 times today but I don't know what it is. Can you tell me what's happening?"*
>
> *Human: "Someone is standing at the demo table."*
>
> *Room: "Standing at the table. I'll remember that — low variance, single path, long duration."*

Now the entire cluster gets labeled. One annotation labels 47 events retroactively.

**Grounding rules:**
- Label propagates to all events in the same cluster
- If a cluster has mixed labels (ambiguous), split it or flag for more data
- Confidence = (labeled events in cluster) / (total events in cluster)
- High-confidence labels auto-apply to new events; low-confidence → ask again

### Layer 5: Cross-Modal Self-Supervision — "My senses agree, so I trust this"

**Input:** Events with multi-modal features.
**Output:** Auto-labeled events where modalities agree.

This is the real magic. The room's different senses teach each other:

```
CSI detects: sudden 3-path disturbance, 4 seconds, moving pattern
Audio detects: footstep-frequency energy spike (200-400Hz) at same time
Camera snapshot: shows person walking (if snapshot_logger is running)

→ All three agree → auto-label as "person_walking" with high confidence
→ No human needed
```

**Agreement matrix:**

| CSI says | Audio says | Camera says | Result |
|----------|-----------|-------------|--------|
| motion | footsteps | person visible | Auto-label: walking (high conf) |
| motion | silence | person visible | Label: silent movement (med conf) |
| motion | loud | empty frame | Flag: investigate (CSI+audio agree, camera disagrees) |
| still | silence | empty frame | Baseline confirmation |
| still | loud sound | empty frame | Audio-only event (not spatial) |
| motion | silence | no camera | CSI-only event (label if cluster match) |

**Over time:** The room builds a correlation model — which sensor combinations are reliable for which event types. CSI is great for movement. Audio is great for impacts and speech. Camera is ground truth but privacy-invasive. The goal: get good enough at CSI+audio that the camera becomes unnecessary.

---

## Data Structures

### Signature Library

The room's accumulated knowledge. Persists across restarts.

```python
{
    "version": 2,
    "baseline": { ... },  # Layer 1
    "signatures": [
        {
            "id": "sig_001",
            "label": "person_walking_zone_yellow_purple",
            "source": "cross_modal",  # or "human", "cluster_propagation"
            "created_at": "2026-03-28T11:30:00Z",
            "times_matched": 47,
            "confidence": 0.92,
            "feature_centroid": [...],
            "feature_radius": 0.28,
            "properties": {
                "typical_duration_ms": [2000, 5000],
                "typical_paths": ["Yellow", "Purple"],
                "typical_peak_ratio": [6, 15],
                "audio_correlation": "footsteps",
            },
        },
        ...
    ],
    "clusters": [ ... ],  # Layer 3
    "observations": [ ... ],  # prediction log
    "learning_curve": [
        {"timestamp": "...", "total_events": 50, "classifiable": 12, "confidence_mean": 0.4},
        {"timestamp": "...", "total_events": 200, "classifiable": 150, "confidence_mean": 0.78},
    ],
}
```

### The Learning Curve

Track and display the room's growth over time:

```
10:00  ████░░░░░░  12/50 events classifiable (24%)   "I'm mostly confused"
11:00  ██████░░░░  45/120 events classifiable (38%)  "I'm starting to see patterns"
13:00  ████████░░  150/200 events classifiable (75%) "I know this room"
15:00  █████████░  280/310 events classifiable (90%) "I see everything"
```

This IS the demo. Show judges the room's learning curve in the viz — how it went from blind to seeing over the course of the day.

---

## Implementation Plan

### What exists now
- `csi_collector.py` — raw CSI capture + basic variance detection (Layer 0 + partial Layer 2)
- `snapshot_logger.py` — camera + audio snapshots (Layer 0)
- `sensor_logger.py` — candle state + audio features (Layer 0)
- `snapshot_dashboard.py` — audio-feature similarity matching (proto-Layer 3)

### What to build

**1. Event Detector** (`event_detector.py`)
- Reads from CSI stream (serial or JSONL replay)
- Detects events using variance threshold + temporal windowing
- Correlates with audio features from sensor_logger
- Outputs events to `data/events.jsonl`
- ~100 lines. Core algorithm already exists in csi_collector.py.

**2. Signature Library** (`signature_library.py`)
- In-memory library with JSON persistence
- Add signatures from: human labels, cluster propagation, cross-modal agreement
- Match new events against library (cosine similarity on feature vectors)
- Track confidence, match counts, learning curve
- ~150 lines.

**3. Clustering** (in signature_library.py or separate)
- Run HDBSCAN on accumulated events periodically
- Auto-discover categories
- Propagate labels from any labeled event to its cluster
- ~80 lines with scikit-learn.

**4. Learning API** (extend ws_bridge.py or new endpoint)
- `POST /api/label` — human labels a current event via chat
- `GET /api/library` — current signature library state
- `GET /api/learning-curve` — the room's growth over time
- `GET /api/events/recent` — recent events for the viz

**5. Viz integration**
- Learning curve chart in the stats panel
- Events appear as pulses on the 3D room view
- Cluster visualization (optional stretch)

---

## The Philosophical Bit

The snapshot_dashboard already does something profound: it takes an audio fingerprint and retrieves the most similar visual memory. That's a room remembering what it saw when it last heard this sound. That's cross-modal memory.

Our CSI system does the same thing but with electromagnetic perception instead of vision. When the room feels a familiar CSI pattern, it retrieves the label from its library. "I've felt this before. Last time, someone told me it was a person walking."

The difference between a sensor system and a learning system: a sensor system reports numbers. A learning system says "I've seen this before, and here's what it means." The room starts as a sensor system and evolves into a learning system over the course of the hackathon.

That evolution — from blind to seeing — is the story we're telling.
