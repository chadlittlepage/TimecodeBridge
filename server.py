#!/usr/bin/env python3
"""DaVinci Timecode Bridge v2.1 — WebSocket server.

Reads Resolve state from a file (written by resolve_console_script.py).
Reads LTC timecode from ltc_listener.py via TCP.
Broadcasts both to browser clients via WebSocket.
"""

import asyncio
import json
import os
import time

from websockets.asyncio.server import serve

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = os.environ.get("TC_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("TC_BRIDGE_PORT", "9876"))
LTC_HOST = os.environ.get("TC_BRIDGE_LTC_HOST", "localhost")
LTC_PORT = int(os.environ.get("TC_BRIDGE_LTC_PORT", "9878"))
STATE_FILE = "/tmp/tcb_resolve_state.json"
VERSION = "2.1"

# ---------------------------------------------------------------------------
# WebSocket server
# ---------------------------------------------------------------------------

CLIENTS: set = set()
_latest_timeline_info: str | None = None
_latest_timecode: str | None = None


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
        await ws.send(json.dumps({"type": "hello", "version": VERSION, "server": "TimecodeBridge"}))
        if _latest_timeline_info:
            await ws.send(_latest_timeline_info)
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
# File watcher — reads Resolve state from file
# ---------------------------------------------------------------------------

async def watch_resolve_file() -> None:
    global _latest_timeline_info, _latest_timecode

    last_mtime = 0
    last_tc = None
    last_tl = None

    while True:
        try:
            mtime = os.path.getmtime(STATE_FILE)
            if mtime > last_mtime:
                last_mtime = mtime
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)

                # Timeline info changed
                tl_name = state.get("timeline")
                if tl_name != last_tl:
                    last_tl = tl_name
                    info = json.dumps({
                        "type": "timeline_info",
                        "project": state.get("project", ""),
                        "timeline": tl_name,
                        "fps": state.get("fps", 24),
                        "startTC": state.get("startTC", "00:00:00:00"),
                    })
                    _latest_timeline_info = info
                    print(f"[resolve] {state.get('project')} / {tl_name} @ {state.get('fps')}fps", flush=True)
                    await broadcast(info)

                # Timecode changed
                tc = state.get("tc")
                if tc and tc != last_tc:
                    last_tc = tc
                    msg = json.dumps({
                        "type": "timecode",
                        "tc": tc,
                        "ts": state.get("ts", time.time()),
                        "source": "api",
                    })
                    _latest_timecode = msg
                    await broadcast(msg)

        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError):
            pass

        await asyncio.sleep(0.02)  # check file every 20ms


# ---------------------------------------------------------------------------
# TCP reader — connects to the LTC listener
# ---------------------------------------------------------------------------

async def read_ltc_tcp() -> None:
    global _latest_timecode

    logged_once = False
    while True:
        try:
            if not logged_once:
                print(f"[ltc] Connecting to {LTC_HOST}:{LTC_PORT}...", flush=True)
            reader, writer = await asyncio.open_connection(LTC_HOST, LTC_PORT)
            logged_once = False
            print(f"[ltc] Connected!", flush=True)

            while True:
                line = await reader.readline()
                if not line:
                    print("[ltc] Connection closed", flush=True)
                    break

                raw = line.decode().strip()
                if not raw:
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "timecode":
                    _latest_timecode = raw
                    await broadcast(raw)

        except (ConnectionRefusedError, OSError):
            logged_once = True
        except Exception as e:
            print(f"[ltc] Error: {e}", flush=True)

        await asyncio.sleep(2)


async def main() -> None:
    print(f"TimecodeBridge v{VERSION}", flush=True)
    print(f"WebSocket: ws://{HOST}:{PORT}", flush=True)
    print(f"Resolve state file: {STATE_FILE}", flush=True)
    print(f"LTC TCP: {LTC_HOST}:{LTC_PORT}", flush=True)

    async with serve(handler, HOST, PORT):
        resolve_task = asyncio.create_task(watch_resolve_file())
        ltc_task = asyncio.create_task(read_ltc_tcp())

        print("Press Ctrl+C to stop.\n", flush=True)

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            resolve_task.cancel()
            ltc_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down.")
