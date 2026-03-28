# Network Setup — Hackathon Day

## Venue WiFi: Not Usable

WorkOS-Guest is 5GHz only (channel 44). ESP32 CSI requires 2.4GHz, and WLED candles (ESP8266) physically cannot connect to 5GHz networks.

## Active Network: Gentle Thrills

GL-AXT1800 router running as a standalone 2.4GHz network on **channel 11**, with WorkOS-Guest bridged for internet via the router's repeater mode.

- **SSID:** Gentle Thrills
- **Password:** superman
- **Router admin:** 10.9.0.1
- **Subnet:** 10.9.0.0/16
- **Candle IP range:** 10.9.3.101–113 (matches candle number)

## Candle Color Map

All 13 candles are online and set to distinct identification colors:

| Candle | IP | MAC | Color | Hex |
|--------|-----|-----|-------|-----|
| 01 | 10.9.3.101 | 4c752594d210 | Red | #FF0000 |
| 02 | 10.9.3.102 | 08f9e0611bc7 | Orange | #FF6400 |
| 03 | 10.9.3.103 | c8c9a339a907 | Gold | #FFC800 |
| 04 | 10.9.3.104 | 485519ec2f04 | Yellow | #DCFF00 |
| 05 | 10.9.3.105 | 08f9e0690c68 | Green | #00FF00 |
| 06 | 10.9.3.106 | 485519ef0a8d | Teal | #00FF80 |
| 07 | 10.9.3.107 | c8c9a339a779 | Cyan | #00FFFF |
| 08 | 10.9.3.108 | c8c9a338ec00 | Sky Blue | #0080FF |
| 09 | 10.9.3.109 | 485519ee65c7 | Blue | #0000FF |
| 10 | 10.9.3.110 | 485519ecd18e | Purple | #8000FF |
| 11 | 10.9.3.111 | 485519ecd242 | Magenta | #FF00FF |
| 12 | 10.9.3.112 | 08f9e068ea07 | Rose | #FF0064 |
| 13 | 10.9.3.113 | 485519ec2429 | Warm White | #FFB464 |

## WLED Control

```bash
# Set color (must set fx:0 for solid or effects override)
curl -X POST http://10.9.3.101/json/state \
  -H "Content-Type: application/json" \
  -d '{"seg":[{"fx":0,"col":[[255,0,0]]}]}'

# Set brightness (0-255)
curl -X POST http://10.9.3.101/json/state \
  -d '{"bri":128}'

# Get device info
curl http://10.9.3.101/json/info
```

## ESP32 CSI Sensors

| Sensor | Port | Status |
|--------|------|--------|
| esp32_a | /dev/cu.usbserial-1110 | Flashed, channel 11, promiscuous mode |
| esp32_b | — | Needs data cable (tested one charge-only cable) |
| esp32_c | — | Not yet connected |
| esp32_d | — | Not yet connected |

**Firmware:** `~/esp/esp-csi/examples/get-started/csi_recv` (MAC filter removed, gain compensation disabled)

**Flash command:**
```bash
export IDF_PATH=~/esp/esp-idf && source $IDF_PATH/export.sh
cd ~/esp/esp-csi/examples/get-started/csi_recv
idf.py -p /dev/cu.usbserial-XXXX flash
```

**Serial baud rate:** 921600
