# Séance — What We Learned

## WiFi CSI Sensing

### How It Works
- ESP32-S3 boards in **promiscuous mode** capture Channel State Information (CSI) from every WiFi frame on channel 11
- CSI = 64 complex I/Q pairs per packet, representing how the signal propagated through space (multipath, reflections, attenuation)
- We extract **amplitude** from each I/Q pair: `amp = sqrt(I² + Q²)`
- First 12 values (6 I/Q pairs) are padding — skip them

### What the Sensors See
- **Every device on channel 11**, not just devices on our network (Gentle Thrills)
- This includes:
  - Our 13 WLED candles (known MACs, fixed positions = reference grid)
  - Phones doing WiFi probe requests (scanning for networks, hitting ch11 periodically)
  - Laptops, watches, anything with WiFi that transmits on ch11
  - Other access points' beacon frames
- Devices do NOT need to be connected to Gentle Thrills — promiscuous mode captures all frames on the channel

### What We Can Detect
- **Presence**: unknown MACs appearing = someone's device is nearby
- **Movement**: variance in CSI amplitude over time = something is moving between transmitter and sensor
- **Rough position**: RSSI from multiple sensors → triangulation via gradient descent on distance estimates
- **Disturbance zones**: which candle→sensor paths are disrupted tells you where in the room movement is happening

### Disturbance Detection
- Compute rolling variance of amplitude across a window of packets
- Compare to a calibrated baseline (captured during first 5 seconds of quiet)
- Variance ratio > 3.0 = disturbance (someone moved through that signal path)
- Per-sensor-per-candle variance gives **spatial specificity** — you can tell which specific path between which candle and which board is disrupted

### Triangulation
- Convert RSSI to rough distance: `d = 10^((-40 - rssi) / 25)` (log-distance path loss, n≈2.5 indoors)
- With 4 sensors at known positions, use gradient descent to find the point that minimizes distance errors
- This naturally places devices **outside** the sensor grid when appropriate
- RSSI jitters ±5-10 dB even when stationary — need heavy smoothing + deadzone to prevent position bouncing
- Known presences (labeled people) get extra smoothing

## The Candle Grid

### Why It's Useful
- WLED candles are fixed-position WiFi devices with known MACs
- They form a **reference grid** — when CSI on a candle→sensor path changes, you know something happened in the physical space between those two points
- 9 candles in a 3×3 grid + 4 sensors in corners = dense coverage of the conference room
- 2 candles on our table + 2 sensors = coverage of the work area

### Keeping Candles Visible
- WLED devices are quiet when idle — they only transmit when responding to HTTP requests
- Solution: **pinger** that hits each candle every 2 seconds via `GET /json/state`
- This forces a response packet that the sensors capture as CSI
- Without the pinger, sensors only see a candle when it happens to do network housekeeping (ARP, mDNS, etc.)

### Candle Control
- WLED API: `POST http://{ip}/json/state` with `{"seg":[{"fx":0,"col":[[R,G,B]]}],"bri":N}`
- Can change colors reactively based on CSI (reactor mode)
- Solo mode: light one candle, darken others — useful for calibration sweeps

## The Data

### What We Log
- Every CSI packet as JSONL: `{"t": timestamp, "sensor": ip, "mac": mac, "rssi": rssi, "candle": id_or_null}`
- ~100 packets/sec across all sensors
- ~50 MB/hour of raw JSONL
- Unknown MACs (candle: null) are **the people** — the most interesting data

### MAC Addresses
- Candle MACs are fixed (Espressif OUI: `48:55:19`, `08:f9:e0`, `c8:c9:a3`, `4c:75:25`)
- Phone MACs are randomized per-network (locally administered bit set — second hex char is 2, 6, A, or E)
- iOS rotates randomized MAC roughly every 24 hours, or on network rejoin
- The MAC shown in iOS Settings → WiFi → (i) should match what's on the wire
- Phones are intermittently visible — they only transmit when actively sending data, doing probes, or keepalives

### Data Format from API
- `paths`: per-candle aggregated data (max variance across all sensors)
- `sensor_paths`: per-sensor-per-candle data (the real spatial info — each candle→board pair has its own variance)
- `presences`: unknown MACs with per-sensor RSSI for triangulation
- `meta`: packets/sec, unique MACs, uptime, active sensor count

## Architecture

### Hardware
- 13 WLED brass candles on Gentle Thrills network (10.9.0.0/16, channel 11)
- 4 ESP32-S3 sensor boards in promiscuous mode, forwarding CSI over UDP port 5500
- Serial connection at 921600 baud for local board, UDP for remote boards

### Software
- `api.py` — FastAPI server: collects UDP from all sensors, REST + WebSocket API, candle control, pinger, data logging
- `frontend/` — React + Vite + React Three Fiber: 3D room viz, per-sensor signal paths, presence triangulation
- `viz/ws_bridge.py` — original standalone bridge (serial → WebSocket), still works for single-board setups

### Gotchas
- CSI packets can have **inconsistent subcarrier counts** across different transmitters — normalize amplitude array length or numpy will crash on `np.array()`
- The API's UDP listener can silently die if the process is killed and restarted badly — always verify sensors are flowing after restart
- `candles.json` uses MACs without colons, API uses MACs with colons — mismatch caused invisible candles until we normalized
- Vite 8 requires Node 20+ — use nvm to switch
- `@assistant-ui/react` v0.12 has deep internal dependencies that crash without full setup — replaced with simple custom chat

### Network Notes
- Candle IPs: 10.9.3.101–113 (static DHCP)
- Sensor IPs: 10.9.0.110, 10.9.0.199, 10.9.0.237, 10.9.0.242
- Some candles go unreachable intermittently — retry or power cycle
- 4 of 13 candles were down at various points (Gold 03, Mint 06, White 07, Violet 10)

## Challenges at the Venue

### Signal Strength
- 2.4 GHz indoor path loss is significant — every wall or human body between candle and sensor eats 3-10 dB
- At conference room distances we were already in the -70s to -80s dBm, where SNR gets rough
- The venue's portable router (Gentle Thrills) was underpowered — low TX power compounded the distance issue
- Candles' WLED response packets were weaker than needed at the margins

### What Would Help (Same Hardware)
- **Channel selection** — ch11 may have been congested with other hackathon networks overlapping on ch9-13. Scanning for the least crowded channel could improve SNR significantly
- **Antenna orientation** — ESP32-S3 PCB antennas are somewhat directional. Rotating boards 90° can make a real difference
- **More boards, closer spacing** — 6-8 ESP32s covering a smaller area gives redundancy. At $8/board the marginal cost is just flashing firmware
- **External antennas** — some ESP32-S3 boards have IPEX connectors. A $2 external antenna with modest gain helps at the margins
- **Higher TX power on candles** — WLED runs on ESP32s internally. Tweaking WiFi TX power from default toward max adds a few dB of headroom
- **Better router** — the single biggest improvement. A decent AP with proper TX power and channel management would lift everything downstream

## Hardware Upgrade Path

### 5 GHz CSI — Why and How
- The ESP32 limitation is hardware: its radio only does 2.4 GHz. Nothing intrinsic about 5 GHz prevents CSI.
- 5 GHz would give **better spatial resolution** — shorter wavelengths are more sensitive to small movements and multipath
- 80 MHz channels give 256 subcarriers (vs 64 on ESP32) — much finer-grained channel information

### Options (Cheapest to Most Capable)

| Setup | Cost/node | Bands | Subcarriers | Pain Level |
|-------|-----------|-------|-------------|------------|
| ESP32-S3 (current) | $8 | 2.4 GHz | 64 | Low |
| Raspberry Pi 4 + USB AX210 | $55-70 | 2.4/5/6 GHz | 256+ | High (USB adapter issues, ARM driver pain) |
| Used mini PC (ThinkCentre Tiny) + AX210 | $80-100 | 2.4/5/6 GHz | 256+ | Medium (x86, tools just work) |
| HackRF / USRP SDR | $300-1500 | Anything | Unlimited | Very high (you're demodulating WiFi yourself) |

**Recommendation:** Skip the Pi route — USB M.2 enclosures are flaky, PicoScenes on ARM is spotty. A used mini PC is $20-30 more and saves hours of driver debugging. The ESP32s proved the concept; the upgrade should be robust, not another hack.

### CSI Software Tools
- **PicoScenes** — most capable, supports AX210, closed-source with free academic license
- **Linux CSI Tool** — open-source but only works with older Intel 5300 chips
- **Nexmon** — open-source, patches Broadcom firmware, limited 5 GHz support
- All the academic tools assume x86 Linux — another reason to use mini PCs over Pis

## Alternative Architecture: Piggyback on Venue WiFi

### The Idea
Instead of running our own weak router, use the venue's enterprise-grade WiFi as the signal source. The ESP32 sensors in promiscuous mode don't care whose network the traffic is on — they just listen to a channel.

### How It Works
1. Identify the venue AP's 2.4 GHz channel (e.g. channel 6)
2. Flash ESP32 sensors to listen on that channel
3. Every device at the hackathon — every phone, laptop, watch — becomes a signal source
4. The venue AP has high TX power, good antennas, optimized channel management — all free infrastructure
5. Hundreds of devices transmitting constantly = dense sensing data without a pinger

### Tradeoffs
- **Candle control** — if candles move to venue network, you might lose WLED API access (network isolation, client isolation, firewall). Could keep candles on a separate SSID or use them on both.
- **Channel coordination** — need to know the venue AP's channel, and some APs do dynamic channel selection (DFS). Sensors must match.
- **Way more noise** — hundreds of MACs vs 13. But that's also way more data. The challenge shifts from "not enough signal" to "filtering signal from noise."
- **No pinger needed** — venue traffic IS the pinger. Every HTTP request, Slack message, Zoom call from every attendee generates frames.

### Dual-Layer Sensing (Best of Both)
Keep candles on our own network (Gentle Thrills, channel 11) as labeled reference points. Run a SECOND set of sensors on the venue WiFi channel. Two sensing layers:

1. **Structured layer** — candle grid on ch11, gives calibrated reference paths with known geometry
2. **Ambient layer** — venue traffic on ch6 (or whatever), captures all human devices, massive coverage

The structured layer tells you "something moved between Gold and Board D." The ambient layer tells you "there are 40 phones in the room and here's roughly where each one is." Together they give you both precision and coverage.

### What You'd Need
- 4 more ESP32 boards (~$32) flashed to the venue channel
- Or reconfigure 2 of the existing 4 boards if you can sacrifice some structured coverage
- Firmware change is one line: the channel number in the CSI receiver config
- API already handles multiple sensors — just more UDP sources
