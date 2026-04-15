"""
TimecodeBridge Python Client Library

Minimal WebSocket client for consuming timecode from a TimecodeBridge server.
Single file, single dependency (websockets).

Usage:
    from tcbridge import TimecodeBridge

    bridge = TimecodeBridge("ws://localhost:9876")
    bridge.on_timecode = lambda tc, source: print(f"{tc} ({source})")
    bridge.on_timeline = lambda info: print(info["project"])
    bridge.on_markers = lambda markers: print(f"{len(markers)} markers")
    bridge.start()   # background thread
    # ... do other work ...
    bridge.stop()

    # Or blocking:
    bridge.run()
"""

import asyncio
import json
import threading

import websockets


class TimecodeBridge:
    def __init__(self, url: str = "ws://localhost:9876", reconnect_s: float = 2.0):
        self.url = url
        self.reconnect_s = reconnect_s

        # Callbacks
        self.on_timecode = None   # (tc: str, source: str) -> None
        self.on_timeline = None   # (info: dict) -> None
        self.on_markers = None    # (markers: list[dict]) -> None
        self.on_connect = None    # () -> None
        self.on_disconnect = None # () -> None

        # State
        self.timecode: str | None = None
        self.source: str | None = None
        self.timeline: dict | None = None
        self.markers: list[dict] = []
        self.connected: bool = False

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start receiving in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_sync, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def run(self) -> None:
        """Run the event loop (blocking)."""
        asyncio.run(self._loop())

    def _run_sync(self) -> None:
        asyncio.run(self._loop())

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.url) as ws:
                    self.connected = True
                    if self.on_connect:
                        self.on_connect()

                    async for raw in ws:
                        if self._stop_event.is_set():
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        msg_type = data.get("type")
                        if msg_type == "timecode":
                            self.timecode = data.get("tc")
                            self.source = data.get("source", "api")
                            if self.on_timecode:
                                self.on_timecode(self.timecode, self.source)
                        elif msg_type == "timeline_info":
                            self.timeline = data
                            if self.on_timeline:
                                self.on_timeline(data)
                        elif msg_type == "markers":
                            self.markers = data.get("markers", [])
                            if self.on_markers:
                                self.on_markers(self.markers)

            except (ConnectionRefusedError, OSError, websockets.exceptions.ConnectionClosed):
                pass
            finally:
                self.connected = False
                if self.on_disconnect:
                    self.on_disconnect()

            if not self._stop_event.is_set():
                await asyncio.sleep(self.reconnect_s)
