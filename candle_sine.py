#!/usr/bin/env python3
"""
Seance — Candle-driven saw wave
Outputs a saw wave whose pitch glides to track candle 02's WiFi signal strength.
"""

import json
import threading
import time
from urllib.request import urlopen, Request

import numpy as np
import sounddevice as sd

CANDLE_IP = "10.9.3.102"
AMPLITUDE = 0.3
FREQ_MIN = 220.0
FREQ_MAX = 1000.0
SAMPLE_RATE = 44100
POLL_INTERVAL = 0.3
GLIDE_SPEED = 4.0  # octaves per second — controls how fast pitch slides

# Shared state
target_freq = FREQ_MIN
current_freq = FREQ_MIN
phase = 0.0
lock = threading.Lock()


def poll_candle():
    global target_freq
    while True:
        try:
            req = Request(f"http://{CANDLE_IP}/json/info", headers={"Connection": "close"})
            with urlopen(req, timeout=0.5) as resp:
                info = json.loads(resp.read())
            signal = info.get("wifi", {}).get("signal", 0)
            # Map signal 60-100 to full frequency range
            normalized = max(0.0, min(1.0, (signal - 60) / 40.0))
            freq = FREQ_MIN + normalized * (FREQ_MAX - FREQ_MIN)
            with lock:
                target_freq = freq
            print(f"signal={signal:>3}  freq={freq:>7.1f}Hz")
        except Exception as e:
            print(f"poll error: {e}")
        time.sleep(POLL_INTERVAL)


def audio_callback(outdata, frames, time_info, status):
    global current_freq, phase

    with lock:
        target = target_freq

    samples = np.empty(frames, dtype=np.float32)
    for i in range(frames):
        # Glide current_freq toward target exponentially
        if current_freq < target:
            current_freq *= 2.0 ** (GLIDE_SPEED / SAMPLE_RATE)
            if current_freq > target:
                current_freq = target
        elif current_freq > target:
            current_freq /= 2.0 ** (GLIDE_SPEED / SAMPLE_RATE)
            if current_freq < target:
                current_freq = target

        # Saw wave: phase wraps 0-1, output is -1 to 1
        phase += current_freq / SAMPLE_RATE
        phase -= int(phase)
        samples[i] = 2.0 * phase - 1.0

    outdata[:, 0] = AMPLITUDE * samples


def main():
    print(f"Saw wave: {FREQ_MIN}-{FREQ_MAX}Hz, pitch tracking candle 02 ({CANDLE_IP})")
    print("Ctrl+C to stop\n")

    poller = threading.Thread(target=poll_candle, daemon=True)
    poller.start()

    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback):
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
