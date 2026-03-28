# Seance — Prior Art & Research Reference

---

## Directly Relevant Prior Art

### Radio Tomographic Imaging (RTI)
**Closest architectural match to our project.**

Researchers used a mesh of ESP32 nodes as a radio frequency sensor network, collecting signal strength values across all node pairs to reconstruct tomographic images and localize objects with 92%+ accuracy using a CNN. This is literally our concept — a grid of known-position transmitters (candles) with receivers (ESP32 sensors) measuring signal distortion across every path.

**Key difference:** They used RSSI (crude, single number per link). We're using CSI (64 subcarriers per link, much richer data).

**Pitch framing:** "We're doing radio tomography, but with 64x the signal resolution per path."

- Paper: "Passive localization based on radio tomography images with CNN model utilizing WIFI RSSI" (Scientific Reports, 2025)
- Link: https://www.nature.com/articles/s41598-025-99694-2

---

### Person-in-WiFi (CMU, ICCV 2019)
**Landmark paper for WiFi-based human perception.**

Used WiFi signals to perform body segmentation and pose estimation. Trained against camera ground truth, deployed without cameras.

- Paper: https://www.ri.cmu.edu/app/uploads/2019/09/Person_in_WiFi_ICCV2019.pdf

---

### AM-FM: Foundation Model for Ambient Intelligence Through WiFi
**The "GPT moment" for WiFi sensing.**

First foundation model for WiFi-based ambient perception. Pre-trained on 9.2 million unlabeled CSI samples collected over 439 days. Achieves >0.90 AUROC on all nine classification tasks through parameter-efficient fine-tuning.

- Paper: https://arxiv.org/abs/2602.11200 (February 2026)

---

### ESPectre
**Community WiFi motion detection project.**

Built by Francesco Pace. Motion detection using WiFi CSI spectrum analysis with Home Assistant integration. ~€10 hardware, 4000+ GitHub stars. Key learning: the Part 2 blog documents real-world challenges (signal drift, calibration, subcarrier selection) that we're sidestepping by streaming raw CSI.

- Repo: https://github.com/francescopace/espectre

---

### RuView / WiFi DensePose
Multi-sensor coordination reference. TDM hardware protocol for ESP32 sensing coordination.

- Repo: https://github.com/ruvnet/RuView

---

## Tools & Frameworks

| Tool | Use |
|------|-----|
| [espressif/esp-csi](https://github.com/espressif/esp-csi) | Our primary firmware base. Modified `csi_recv` for promiscuous multi-source capture. |
| [ESP32-CSI-Tool](https://github.com/StevenMHernandez/ESP32-CSI-Tool) | Research-oriented CSI toolkit, supports active and passive modes |
| [CSIKit](https://github.com/Gi-z/CSIKit) | Python CSI parser for multiple hardware formats including ESP32 |
| [csiread](https://github.com/citysu/csiread) | Fast Python CSI parser (Cython, 15x faster than MATLAB) |
| [Awesome-WiFi-CSI-Sensing](https://github.com/Marsrocky/Awesome-WiFi-CSI-Sensing) | Master curated list of papers and code |

---

## Key Standards

### 802.11bf — IEEE Standard for WLAN Sensing
Published September 2025. Formalizes CSI-based sensing, making CSI data consistent across chipmakers. First compatible consumer devices expected 2026.

---

## Pitch Framing for Judges

"Radio tomography has been studied for years using crude RSSI measurements. WiFi CSI gives us 64x the signal resolution per link. Foundation models like AM-FM show that WiFi perception can generalize across environments. The 802.11bf standard is making this an industry reality. We built the system that makes it tangible — you can see the agent seeing you, through candlelight."
