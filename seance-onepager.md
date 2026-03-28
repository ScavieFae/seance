# Seance — Project Summary

## One-Line Description

An AI agent that perceives physical space through WiFi signals bouncing between 13 brass candles, learns what a person looks like in radio waves over the course of a day, and makes its perception visible through the candles themselves — no cameras, no microphones, no wearables.

---

## How It Works

WiFi signals bounce off walls, furniture, and human bodies. Normally, devices discard the signal-distortion data (called Channel State Information / CSI) after using it to decode packets. We capture and analyze that data instead — turning ambient WiFi into a passive spatial sensing layer.

Thirteen WLED-based brass "candles" (PartyPi hardware) are scattered around the room. Each one is a known-position WiFi transmitter. ESP32-S3 sensor boards in promiscuous mode extract CSI from every packet the candles send — creating defined signal paths through the space. When a person walks between a candle and a sensor, that specific signal path distorts. The agent perceives the room as a tomographic grid made of candlelight.

The candles also serve as the agent's visual output — brightening, shifting color, and animating in response to what the agent perceives. The room becomes both the sensor and the display.

---

## Hardware

| Component | Count | Role |
|-----------|-------|------|
| PartyPi candles (WLED, ESP8266-based) | 13 | Known-position WiFi transmitter + visual indicator |
| ESP32-S3-DevKitC boards | 4 | CSI extraction in promiscuous mode |
| Laptop | 1 | Python pipeline, LLM agent, candle HTTP control |
| GL-AXT1800 router ("Gentle Thrills") | 1 | Fallback network — candles pre-configured to join |
| Flipper Zero (optional) | 1 | BLE device scanning for cross-modal learning |

---

## Sensing Architecture

### Passive Mode
ESP32s in promiscuous mode sniff all WiFi traffic on the 2.4GHz channel. CSI is extracted from every packet — candle transmissions, router beacons, venue devices. The candles don't need to do anything special; ambient WiFi traffic from being connected to the network is enough to generate continuous CSI data. No cooperation required from any transmitter.

### Active Mode (Echolocation)
The agent pings each candle on demand via HTTP (`GET http://{ip}/json/state`), triggering a response packet with extractable CSI. Sweep all candles in sequence for a full spatial scan with predictable, timed samples on each path. Use sparingly to preserve candle battery.

### Data Pipeline

```
[Candle WiFi transmissions + ambient venue traffic]
    → [ESP32-S3 promiscuous CSI capture @ 921600 baud]
    → [Serial to laptop]
    → [Python: per-path feature extraction]
    → [Structured spatial perception JSON]
    → [LLM agent with spatial context]
    → [Actions: candle visuals, alerts, agent responses]
```

---

## Validated Findings (Friday Night Prep)

### What Works
- **CSI extraction from candle traffic**: ESP32-S3 in promiscuous mode successfully extracts CSI from WLED candle WiFi packets. ~80 CSI packets in 5 seconds from a single candle when actively pinged.
- **Motion detection via per-subcarrier variance**: Hand motion between candle and sensor produces 19x signal-to-noise ratio on per-subcarrier CSI variance (baseline ~1, motion peak ~19.4).
- **RSSI-based proximity tracking**: Monitoring RSSI drop from baseline per candle successfully identifies which candle a person is nearest to. Drove real-time candle color changes (red → blue for closest candle).
- **Ambient traffic is sufficient**: Router, laptops, phones all generate CSI-extractable traffic without any active pinging. 9 unique MACs seen in 5 seconds on a home network.
- **WLED control**: `POST /json/state` with `{"seg":[{"fx":0,"col":[[R,G,B]]}]}` — must set `fx:0` (solid) or active effects override the color.

### Key Technical Details
- **Baud rate**: 921600 (not 115200 — the default sdkconfig sets this high)
- **CSI data format**: 128 values per packet (64 I/Q subcarrier pairs). First 12 values are header/padding zeros.
- **Gain compensation**: The stock `csi_recv` firmware applies gain compensation that crushes weak signals to zero. We disabled it to get raw CSI values — essential for promiscuous multi-source sensing.
- **MAC filter**: Stock firmware filters to a single paired sender MAC. We removed this to accept CSI from all sources on the channel.
- **Channel**: Currently hardcoded to channel 11 in firmware. Must match the WiFi network channel.
- **Board connection**: Micro-USB (not USB-C). Need data cables, not charge-only.
- **Candle placement**: Keep away from large metal surfaces (signal absorption).

### What Needs Work
- **Proximity vs. path disturbance**: CSI variance detects motion *on the signal path between candle and sensor*, not proximity to the candle. With one sensor, geometry determines which paths get disturbed. Multiple sensors solve this.
- **RSSI proximity**: Works but is coarse — RSSI values fluctuate ±2-3 dBm naturally. Need the baseline calibration step (5 seconds, no one near candles).
- **Candle WiFi reconfiguration**: Each candle must be individually reconfigured to join a new network via WLED AP mode. ~1-2 min per candle. Parallelize by configuring one while previous reboots.

---

## CSI Data Format

From serial output:
```
CSI_DATA,{id},{mac},{rssi},{rate},{sig_mode},{mcs},{bandwidth},{smoothing},{not_sounding},{aggregation},{stbc},{fec_coding},{sgi},{noise_floor},{ampdu_cnt},{channel},{secondary_channel},{timestamp},{ant},{sig_len},{rx_state},{len},{first_word},"[{csi_values}]"
```

CSI values are interleaved I/Q pairs: `[imag_1, real_1, imag_2, real_2, ...]`
Amplitude per subcarrier: `sqrt(imag² + real²)`

---

## Relevant Research & Resources

- [espressif/esp-csi](https://github.com/espressif/esp-csi) — Official ESP32 CSI toolkit
- [AM-FM](https://arxiv.org/abs/2602.11200) — First foundation model for WiFi-based ambient perception
- [CSI-Bench](https://arxiv.org/abs/2505.21866) — Large-scale in-the-wild WiFi sensing benchmark
- [EHUNAM](https://www.nature.com/articles/s41597-025-06238-4) — CSI dataset for human + machine sensing
- [CSI2PointCloud](https://arxiv.org/abs/2410.16303) — 3D point cloud generation from WiFi CSI
- [802.11bf](https://standards.ieee.org/standard/802_11bf-2024.html) — IEEE WiFi Sensing standard (Sept 2025)

---

*Team: Mattie & Brian | Hackathon: Multimodal Frontier Hackathon, March 28 2026, SF*
