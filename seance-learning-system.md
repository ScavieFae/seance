# Seance — Recursive Learning System

## Status: Stretch Goal (may get cut for time)

---

## Core Concept

The agent starts blind and teaches itself what things look like in radio waves over the course of the hackathon. By demo time, it has gone from "I see undifferentiated electromagnetic noise" to "I can identify a person walking through zone A" — and it got there through its own recursive learning loop, not because we pre-trained a model.

---

## The Learning Loop

### Phase 1: Raw Perception (Minute 0)

Agent sees CSI as undifferentiated signal. It can report basic statistics — subcarrier variance, rate of change, spectral energy — but has no semantic understanding. It's born blind.

### Phase 2: Grounded Calibration (Minute 5)

Human teacher provides labeled examples:

- "Right now, nobody is moving." → Agent records CSI signature as `stillness`
- "I'm walking between sensor A and the router." → Agent records as `single_person_crossing_zone_a`
- "Everyone stand up." → Agent records as `crowd_standing`
- "Everyone sit down." → Agent records as `crowd_seated`

This seeds the signature library with a handful of anchor points.

### Phase 3: The Agent Starts Guessing (Minute 15)

Agent compares live CSI features against its library using cosine similarity or KNN. Makes predictions: "I think someone just walked through zone A." Sometimes right, sometimes wrong. Logs confidence scores.

### Phase 4: Cross-Modal Self-Supervision (Minute 30+)

This is the key insight: **the agent's different senses can teach each other.**

- WiFi CSI detects a "person-shaped ripple" on sensor A
- BLE scan simultaneously shows device count near sensor A increased by 1
- Cross-modal agreement → auto-label the CSI pattern as "person entering zone A"
- No human confirmation needed

### Phase 5: Novelty Detection + Active Learning (Ongoing)

- CSI pattern with high similarity to existing label → prediction with confidence
- CSI pattern with low similarity to everything → novel event, flagged
- Novel event with BLE correlation → auto-labeled, new category
- Novel event with no cross-modal signal → agent asks a human

---

## Data Structures

### Signature Library

```python
signature_library = [
    {
        "id": "sig_001",
        "timestamp": "2026-03-28T10:14:32Z",
        "label": "single_person_crossing_zone_a",
        "source": "human_calibration",  # or "cross_modal" or "human_confirmation"
        "features": {
            "csi_variance": 0.74,
            "csi_rate_of_change": 0.62,
            "spectral_energy": 0.88,
            "subcarrier_std_vector": [0.12, 0.45, ...],  # 58-dim (after removing header)
            "duration_ms": 3200
        },
        "confidence": 0.95,
        "times_matched": 14
    },
    ...
]
```

### Observation Log

```python
observation_log = [
    {
        "timestamp": "2026-03-28T14:15:01Z",
        "sensor": "esp32_zone_a",
        "raw_features": { ... },
        "prediction": "single_person_crossing_zone_a",
        "similarity_score": 0.87,
        "matched_signature": "sig_001",
        "outcome": "confirmed",  # confirmed | contradicted | unverified
    },
    ...
]
```

---

## Implementation Priority

Minimum viable learning loop:

1. **Seed calibration** — human labels 3-5 examples (5 min)
2. **Cosine similarity matching** against the library (trivial code)
3. **Growing library** — confirmed observations get added
4. **Timeline visualization** — show the learning journey on dashboard

Skip if time-crunched:
- Active learning (agent asking humans)
- Novelty detection with confidence thresholds
- Cross-modal self-supervision (requires Flipper)
- Fine-grained category splitting

---

## Connection to Broader Research

This approach is conceptually aligned with AM-FM (the WiFi sensing foundation model) but operates at a different scale. AM-FM pre-trains on 9.2M samples across 439 days. We're building an environment-specific signature library through live self-supervision.

The long-term vision: use an AM-FM-style foundation model for general CSI understanding, then layer recursive cross-modal learning on top for rapid environment-specific adaptation.
