#!/usr/bin/env python3
"""DaVinci Timecode Bridge — WebSocket server that broadcasts Resolve timecode over LAN.

Architecture:
  resolve_console_script.py (runs INSIDE Resolve's Py3 console, has native API access)
       | TCP port 9877 (JSON lines)
       v
  server.py (this file, asyncio event loop, WebSocket broadcast)
       | WebSocket port 9876
       v
  browser clients (index.html) — also decode LTC audio locally for live playback
"""

import asyncio
import json
import os

from websockets.asyncio.server import serve

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = os.environ.get("TC_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("TC_BRIDGE_PORT", "9876"))
RESOLVE_HOST = os.environ.get("TC_BRIDGE_RESOLVE_HOST", "localhost")
RESOLVE_PORT = int(os.environ.get("TC_BRIDGE_RESOLVE_PORT", "9877"))
VERSION = "2.0"

# ---------------------------------------------------------------------------
# WebSocket server
# ---------------------------------------------------------------------------

CLIENTS: set = set()
_latest_timeline_info: str | None = None
_latest_timecode: str | None = None
_latest_markers: str | None = None


async def broadcast(message: str) -> None:
    if CLIENTS:
        await asyncio.gather(
            *(client.send(message) for client in CLIENTS),
            return_exceptions=True,
        )


async def handler(ws) -> None:
    CLIENTS.add(ws)
    print(f"[+] Client connected from {ws.remote_address} ({len(CLIENTS)} total)", flush=True)
    try:
        # Send hello + cached state
        await ws.send(json.dumps({"type": "hello", "version": VERSION, "server": "TimecodeBridge"}))
        if _latest_timeline_info:
            await ws.send(_latest_timeline_info)
        if _latest_markers:
            await ws.send(_latest_markers)
        if _latest_timecode:
            await ws.send(_latest_timecode)

        async for _ in ws:
            pass
    except Exception as e:
        print(f"[!] Handler error: {e}", flush=True)
    finally:
        CLIENTS.discard(ws)
        print(f"[-] Client disconnected ({len(CLIENTS)} total)", flush=True)


# ---------------------------------------------------------------------------
# TCP reader — connects to the Resolve console script
# ---------------------------------------------------------------------------

async def read_resolve_tcp() -> None:
    global _latest_timeline_info, _latest_timecode, _latest_markers

    while True:
        try:
            print(f"[resolve] Connecting to {RESOLVE_HOST}:{RESOLVE_PORT}...", flush=True)
            reader, writer = await asyncio.open_connection(RESOLVE_HOST, RESOLVE_PORT)
            print(f"[resolve] Connected!", flush=True)

            while True:
                line = await reader.readline()
                if not line:
                    print("[resolve] Connection closed by Resolve", flush=True)
                    break

                raw = line.decode().strip()
                if not raw:
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Add source tag to timecode messages
                msg_type = data.get("type")
                if msg_type == "timecode":
                    data["source"] = "api"
                    raw = json.dumps(data)
                    _latest_timecode = raw
                elif msg_type == "timeline_info":
                    _latest_timeline_info = raw
                    print(f"[resolve] {data.get('project')} / {data.get('timeline')} @ {data.get('fps')}fps", flush=True)
                elif msg_type == "markers":
                    _latest_markers = raw
                    print(f"[resolve] {len(data.get('markers', []))} markers", flush=True)
                elif msg_type == "error":
                    print(f"[resolve] Error: {data.get('message')}", flush=True)

                await broadcast(raw)

        except (ConnectionRefusedError, OSError) as e:
            print(f"[resolve] Cannot reach Resolve console script ({e}). Retrying in 2s...", flush=True)
        except Exception as e:
            print(f"[resolve] Error: {e}. Retrying in 2s...", flush=True)

        await asyncio.sleep(2)


async def main() -> None:
    print(f"TimecodeBridge v{VERSION}", flush=True)
    print(f"WebSocket: ws://{HOST}:{PORT}", flush=True)
    print(f"Resolve TCP: {RESOLVE_HOST}:{RESOLVE_PORT}", flush=True)

    async with serve(handler, HOST, PORT):
        reader_task = asyncio.create_task(read_resolve_tcp())

        print("Press Ctrl+C to stop.\n", flush=True)

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            reader_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down.")
