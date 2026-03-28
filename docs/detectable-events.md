# Detectable Events — What the Room Can Sense

Organized by difficulty. Each event lists what the CSI, audio, and RSSI signals look like, how to detect it, and cross-modal confirmation strategies.

**Hardware:** 3 candles in conference room (Yellow 04, Green 05, Purple 10), 4 ESP32 sensors (A-D), stereo audio (MOTU M6), camera snapshots.

---

## Tier 1 — Should work today

### Person walks through a signal path
- **CSI:** High subcarrier variance (>5x baseline), 2-5s duration, moving temporal profile (ramp up → peak → decay)
- **Audio:** Low-mid band energy spike (footsteps, 200-400Hz)
- **RSSI:** Brief dip on nearest candle(s) during transit
- **Detection:** Variance threshold + duration window. The signature event.
- **Cross-modal:** CSI + footstep audio in same window = high confidence

### Room goes empty
- **CSI:** All paths return to baseline variance (<1.5x) for >60 seconds
- **Audio:** RMS drops to noise floor, no dominant frequency
- **RSSI:** All candles stable, matching original baseline
- **Detection:** All paths below threshold for sustained period
- **Cross-modal:** CSI quiet + audio silent + RSSI stable = confirmed empty

### Someone enters an empty room
- **CSI:** First disturbance after sustained baseline (the "waking" trigger)
- **Audio:** Possible door sound, then footsteps
- **RSSI:** First shift from calibrated baseline
- **Detection:** Transition from empty state to any disturbance
- **Cross-modal:** Critical for the "room wakes up" mood transition

### Person standing still near a candle
- **CSI:** Low but sustained variance on one path (body absorbs/reflects signal statically). Different from walking — less temporal variation.
- **Audio:** May or may not have speech
- **RSSI:** Persistent drop on one candle (strongest proximity indicator)
- **Detection:** RSSI delta > 3dBm on single candle for >10 seconds + low CSI variance on that path
- **Cross-modal:** RSSI drop + low CSI variance = standing still (vs walking which has high CSI variance)

### Crowd / busy room
- **CSI:** Multiple paths disturbed simultaneously, chaotic variance pattern, no clear temporal structure
- **Audio:** High RMS, broadband energy, possibly speech-band dominant
- **RSSI:** Multiple candles show signal drops
- **Detection:** Count of simultaneously disturbed paths > 2 + high aggregate variance
- **Cross-modal:** Many paths + loud audio = crowd confirmed

---

## Tier 2 — Likely detectable with tuning

### Person count (1 vs 2 vs 3+)
- **CSI:** Number of simultaneously active paths. 1 person usually affects 1-2 paths. 2 people on opposite sides affect different paths. 3+ = most paths active.
- **RSSI:** Number of candles with significant signal drop
- **Detection:** Count distinct disturbance clusters in the path activity matrix. Use sensor D (conference room) for local count, sensor C (far side) for range.
- **Notes:** Hardest part is distinguishing 2 nearby people from 1 person between two paths.

### Walking vs standing vs sitting
- **CSI pattern differences:**
  - Walking: high variance, rapid temporal change, sequential path activation
  - Standing: moderate sustained variance, single path, little temporal change
  - Sitting: very low variance (smaller body cross-section when seated), persistent RSSI shift
- **Audio:** Walking has footstep impacts. Standing/sitting distinguished by CSI profile.
- **Detection:** Rate of change of variance (first derivative). Walking = high dv/dt. Standing = low dv/dt. Sitting = near-baseline with subtle static shift.

### Fast vs slow movement
- **CSI:** Sharp, short spike (fast) vs gradual swell (slow)
- **Detection:** Event duration + peak-to-mean ratio. Fast: <2s duration, sharp peak. Slow: 3-8s, rounded profile.
- **Audio:** Fast movement often louder footsteps

### Conversation (people talking, not moving)
- **CSI:** Low variance (people are still)
- **Audio:** Mid-band energy (300-3000Hz), sustained, possibly multiple spectral peaks (multiple speakers)
- **Detection:** Audio speech-band energy > threshold + CSI paths quiet or at low-variance standing pattern
- **Cross-modal:** This is primarily an audio detection confirmed by CSI stillness

### Someone approaches the demo table
- **CSI:** Sequential path activation toward known table location. If table is between Yellow and sensor A, that path activates first, then adjacent paths.
- **Detection:** Requires knowing which paths correspond to the table area. Use sweep calibration data to map.
- **Notes:** This is the "the room watches you approach" moment for demos.

### Applause / clapping
- **Audio:** Broadband transient spikes, repetitive pattern at 3-6Hz
- **CSI:** Minor arm movement artifacts (much weaker than walking)
- **Detection:** Primarily audio. Broadband + periodic + CSI quiet (people are seated/standing) = applause.

---

## Tier 3 — Stretch, needs work

### Specific person recognized on return
- **CSI:** Different bodies distort the signal differently (height, width, water content). The same person walking the same path should produce a more similar CSI signature than different people.
- **Detection:** Store per-event feature vectors. When a new event matches a stored one with high cosine similarity, flag as "same entity." Over the day, build per-entity signature clusters.
- **Research basis:** This is what the AM-FM foundation model does at scale. We're doing it with a hackathon-sized signature library.
- **Honest caveat:** This is hard with 3 candles. More paths = better discrimination. May only work for distinguishing "large person" vs "small person" reliably.

### Door open/close
- **CSI:** Brief RF environment change (line-of-sight paths shift when door moves). Different from person movement — more like a step function than a wave.
- **Audio:** Transient impact sound, possibly mechanical click
- **Detection:** Sudden shift in multiple paths simultaneously + audio transient + then either entry event or return to baseline.

### Gesturing / waving
- **CSI:** Rapid small-scale oscillation at higher frequency than walking. Person is stationary but arms are moving.
- **Detection:** High-frequency CSI variance (>2Hz) + stationary body signature (RSSI stable, low path-switching)
- **Notes:** Only works if gesture is on a signal path. Most useful during calibration: "wave your hand between Yellow and the sensor."

### Breathing detection
- **CSI:** Ultra-low-frequency periodic variance (~0.2-0.3Hz = 12-18 breaths/min). Chest expansion modulates signal.
- **Detection:** FFT of CSI variance time series, look for peak at breathing frequency
- **Requirements:** Very quiet room, person close to a signal path, long observation window (>30s)
- **Research basis:** Proven in literature but requires controlled conditions.

---

## Tier 4 — Demo spectacles

### Ghost replay
- **Not detection — playback.** Replay stored event CSI signatures as candle light patterns when the room is empty. The room "remembers" the judges' visit.
- **Implementation:** Store the last N events with full temporal profiles. When mood = Dreaming, play them back through the CandleDirector at 0.5x speed, dimmed.

### Predict movement direction
- **CSI:** Sequential path activation implies direction. If Yellow fires, then Purple, someone is moving from Yellow toward Purple.
- **Detection:** Track which paths activate in what order. Build path-sequence → direction mapping during calibration.
- **Demo:** "You're walking toward Purple." → room lights the path ahead.

### Through-wall / through-distance sensing
- **CSI:** Sensor D is in the conference room, sensor C is far side of venue. They can detect presence through walls/at distance that cameras can't see.
- **Demo:** Someone stands behind a partition. Room says "I sense something beyond Purple." Judges can't see the person. The room can.
- **Implementation:** Just the normal event detection on a sensor whose signal paths pass through walls. The physics handles it.

---

## Event Feature Vector

Every detected event gets a fixed-length feature vector for matching and clustering:

```python
event_features = {
    # CSI features (per affected path, then aggregated)
    "n_paths_affected": 2,
    "peak_variance_ratio": 12.4,
    "mean_variance_ratio": 5.2,
    "duration_ms": 3600,
    "temporal_slope_up": 3.1,        # how fast it ramped up
    "temporal_slope_down": 1.8,      # how fast it decayed
    "temporal_symmetry": 0.63,       # symmetric = walking, asymmetric = approach/leave
    "dominant_subcarriers": [14, 22, 33],
    "subcarrier_spread": 0.45,       # narrow = specific path, wide = large body
    "path_sequence": ["Yellow", "Purple"],  # order of activation
    "path_overlap": 0.7,             # how much paths were active simultaneously

    # Audio features (during event window)
    "audio_rms_delta": 0.08,
    "audio_dominant_band": "low_mid",  # footstep indicator
    "audio_speech_energy": 0.02,       # speech band
    "audio_transient": False,          # sharp impact?

    # RSSI features
    "rssi_max_delta": -5.2,           # biggest RSSI shift
    "rssi_affected_candles": ["04"],   # which candles
    "rssi_pattern": "single_dip",      # single_dip, multi_dip, sustained

    # Cross-modal
    "csi_audio_correlation": 0.72,    # temporal correlation between CSI and audio
    "modalities_agreeing": 2,         # how many senses detected something
}
```

---

## Priority for Hackathon

| Event | Impact | Effort | Build? |
|-------|--------|--------|--------|
| Person walks through | HIGH — core demo | LOW — already in csi_collector | YES |
| Room empty → someone enters | HIGH — mood trigger | LOW | YES |
| Room goes empty | HIGH — dreaming trigger | LOW | YES |
| Person standing still | MED — demonstrates range | MED | YES |
| Person count (1/2/3+) | HIGH — impressive | MED | YES |
| Conversation (still + talking) | MED — cross-modal showcase | LOW | YES |
| Through-wall detection | HIGH — "wow" factor | LOW — just use sensor C/D | YES |
| Ghost replay | SPECTACULAR — demo closer | MED | IF TIME |
| Approach demo table | HIGH — interactive | MED | IF TIME |
| Walking vs standing vs sitting | MED | MED | STRETCH |
| Same person returns | AMAZING but risky | HIGH | STRETCH |
| Breathing | Cool but fragile | HIGH | SKIP today |
