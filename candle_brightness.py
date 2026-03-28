#!/usr/bin/env python3
"""
Seance — Signal-inverse brightness
Sets each candle's brightness to the inverse of its WiFi signal strength.
Weak signal = bright, strong signal = dim.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "candles.json")) as f:
    CONFIG = json.load(f)

CANDLES = CONFIG["candles"]
POLL_INTERVAL = 0.5
SIGNAL_MIN = 40
SIGNAL_MAX = 100


def update_candle(candle_id, ip):
    try:
        req = Request(f"http://{ip}/json/info", headers={"Connection": "close"})
        with urlopen(req, timeout=0.8) as resp:
            info = json.loads(resp.read())
        signal = info.get("wifi", {}).get("signal", 0)

        # Invert: low signal → high brightness, high signal → low brightness
        normalized = max(0.0, min(1.0, (signal - SIGNAL_MIN) / (SIGNAL_MAX - SIGNAL_MIN)))
        bri = int((1.0 - normalized) * 255)
        bri = max(1, min(255, bri))

        payload = json.dumps({"bri": bri}).encode()
        req = Request(
            f"http://{ip}/json/state",
            data=payload,
            headers={"Content-Type": "application/json", "Connection": "close"},
            method="POST",
        )
        with urlopen(req, timeout=0.8):
            pass

        return candle_id, signal, bri
    except Exception:
        return candle_id, None, None


def main():
    print(f"Inverse brightness: signal {SIGNAL_MIN}-{SIGNAL_MAX} → brightness 255-1")
    print(f"Polling every {POLL_INTERVAL}s (Ctrl+C to stop)\n")

    try:
        while True:
            with ThreadPoolExecutor(max_workers=13) as pool:
                futures = {
                    pool.submit(update_candle, cid, c["ip"]): cid
                    for cid, c in CANDLES.items()
                }
                results = []
                for future in as_completed(futures):
                    results.append(future.result())

            results.sort(key=lambda r: r[0])
            parts = []
            for cid, signal, bri in results:
                short = cid.replace("candle_", "C")
                if signal is not None:
                    parts.append(f"{short}:sig={signal:>3} bri={bri:>3}")
                else:
                    parts.append(f"{short}:DOWN")
            print("  ".join(parts))

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
