#!/usr/bin/env python3
"""Minimal example: print live timecode from a TimecodeBridge server."""

import sys
sys.path.insert(0, "..")

from lib.tcbridge import TimecodeBridge

bridge = TimecodeBridge("ws://localhost:9876")

bridge.on_timecode = lambda tc, source: print(f"\r{tc}  [{source}]", end="", flush=True)
bridge.on_timeline = lambda info: print(f"\n{info['project']} / {info['timeline']} @ {info['fps']}fps")
bridge.on_markers = lambda markers: print(f"\n{len(markers)} markers loaded")
bridge.on_connect = lambda: print("Connected to TimecodeBridge")
bridge.on_disconnect = lambda: print("\nDisconnected, reconnecting...")

print("Listening for timecode... (Ctrl+C to stop)")

try:
    bridge.run()  # blocking
except KeyboardInterrupt:
    print("\nDone.")
