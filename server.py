#!/usr/bin/env python3
"""DaVinci Timecode Bridge — WebSocket server that polls Resolve and broadcasts timecode."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import websockets

# ---------------------------------------------------------------------------
# DaVinci Resolve scripting module discovery
# ---------------------------------------------------------------------------
_RESOLVE_MOD_PATHS = [
    # macOS
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
    # Linux
    "/opt/resolve/Developer/Scripting/Modules",
    # Windows
    r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
]

def _ensure_resolve_path() -> None:
    for p in _RESOLVE_MOD_PATHS:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)

_ensure_resolve_path()

try:
    import DaVinciResolveScript as dvr  # type: ignore[import-untyped]
except ImportError:
    dvr = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = os.environ.get("TC_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("TC_BRIDGE_PORT", "9876"))
POLL_INTERVAL = float(os.environ.get("TC_BRIDGE_POLL_MS", "100")) / 1000.0  # seconds

# ---------------------------------------------------------------------------
# Resolve connection
# ---------------------------------------------------------------------------

def connect_resolve():
    """Connect to the running DaVinci Resolve instance. Returns (resolve, project, timeline) or raises."""
    if dvr is None:
        raise RuntimeError(
            "DaVinciResolveScript module not found. "
            "Make sure DaVinci Resolve is installed and the scripting modules are accessible."
        )
    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError("Could not connect to DaVinci Resolve. Is it running?")
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if project is None:
        raise RuntimeError("No project is open in DaVinci Resolve.")
    timeline = project.GetCurrentTimeline()
    if timeline is None:
        raise RuntimeError("No timeline is open in DaVinci Resolve.")
    return resolve, project, timeline


def get_timeline_fps(timeline) -> float:
    fps_str = timeline.GetSetting("timelineFrameRate")
    return float(fps_str) if fps_str else 24.0


def get_timeline_info(project, timeline) -> dict:
    """Gather static timeline metadata."""
    return {
        "project": project.GetName(),
        "timeline": timeline.GetName(),
        "fps": get_timeline_fps(timeline),
        "startTC": timeline.GetStartTimecode(),
    }

# ---------------------------------------------------------------------------
# WebSocket server
# ---------------------------------------------------------------------------

CLIENTS: set[websockets.WebSocketServerProtocol] = set()


async def register(ws: websockets.WebSocketServerProtocol) -> None:
    CLIENTS.add(ws)
    print(f"[+] Client connected ({len(CLIENTS)} total)")


async def unregister(ws: websockets.WebSocketServerProtocol) -> None:
    CLIENTS.discard(ws)
    print(f"[-] Client disconnected ({len(CLIENTS)} total)")


async def broadcast(message: str) -> None:
    if CLIENTS:
        await asyncio.gather(
            *(client.send(message) for client in CLIENTS),
            return_exceptions=True,
        )


async def handler(ws: websockets.WebSocketServerProtocol, path: str = "") -> None:
    await register(ws)
    try:
        # Send current timeline info on connect
        try:
            _, project, timeline = connect_resolve()
            info = get_timeline_info(project, timeline)
            await ws.send(json.dumps({"type": "timeline_info", **info}))
        except RuntimeError:
            pass

        # Keep connection alive; incoming messages ignored for now
        async for _ in ws:
            pass
    finally:
        await unregister(ws)


async def poll_timecode() -> None:
    """Poll Resolve for the current timecode and broadcast to all clients."""
    last_tc = None
    last_timeline_name = None

    while True:
        try:
            resolve, project, timeline = connect_resolve()
            tc = timeline.GetCurrentTimecode()
            timeline_name = timeline.GetName()

            # Detect timeline switch
            if timeline_name != last_timeline_name:
                last_timeline_name = timeline_name
                info = get_timeline_info(project, timeline)
                await broadcast(json.dumps({"type": "timeline_info", **info}))

            # Only broadcast on change
            if tc != last_tc:
                last_tc = tc
                msg = json.dumps({
                    "type": "timecode",
                    "tc": tc,
                    "ts": time.time(),
                })
                await broadcast(msg)

        except RuntimeError as e:
            # Resolve not connected / no timeline — broadcast status
            if last_tc is not None:
                last_tc = None
                await broadcast(json.dumps({"type": "error", "message": str(e)}))

        await asyncio.sleep(POLL_INTERVAL)


async def main() -> None:
    print(f"TimecodeBridge server starting on ws://{HOST}:{PORT}")
    print(f"Poll interval: {POLL_INTERVAL * 1000:.0f}ms")
    print("Waiting for Resolve connection...")

    server = await websockets.serve(handler, HOST, PORT)

    # Start polling in parallel
    poll_task = asyncio.create_task(poll_timecode())

    print(f"Server running. Connect a browser to http://<this-machine-ip>:{PORT}/")
    print("Press Ctrl+C to stop.\n")

    try:
        await asyncio.Future()  # run forever
    except asyncio.CancelledError:
        pass
    finally:
        poll_task.cancel()
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down.")
