# TimecodeBridge

Real-time DaVinci Resolve timecode over WebSocket for browsers on your LAN.

Two sync paths that work together:
- **Path A (API):** Resolve scripting API polled via console script. Accurate when stopped/scrubbing.
- **Path B (LTC):** Fairlight LTC audio decoded in the browser via WebAssembly. Frame-accurate during playback.

The browser merges both: LTC during playback, API when stopped.

## Architecture

```
PATH A (metadata + stopped TC):
  Resolve Py3 Console ──TCP:9877──> server.py ──WS:9876──> Browser

PATH B (live playback TC):
  Resolve Fairlight LTC ──> BlackHole ──[SonoBus]──> Browser getUserMedia
                                                       └──> LTC.wasm decode
```

## Quick Start

```bash
pip install websockets

# 1. Start the server
python server.py

# 2. In Resolve, open Workspace > Console > Py3, paste:
exec(open("resolve_console_script.py").read())

# 3. Open index.html in a browser
```

For real-time playback sync, install BlackHole and configure Fairlight LTC output. See [docs/SETUP.md](docs/SETUP.md).

## For Developers

Hook into the timecode stream from your own app:

### JavaScript
```html
<script src="lib/tcbridge.js"></script>
<script>
  const bridge = new TimecodeBridge("ws://192.168.1.100:9876");
  bridge.on("timecode", (data) => console.log(data.tc));
  bridge.on("timeline", (info) => console.log(info.project));
  bridge.on("markers", (markers) => console.log(markers));
</script>
```

### Python
```python
from lib.tcbridge import TimecodeBridge

bridge = TimecodeBridge("ws://localhost:9876")
bridge.on_timecode = lambda tc, source: print(tc)
bridge.start()  # background thread
```

See [docs/PROTOCOL.md](docs/PROTOCOL.md) for the full WebSocket protocol spec.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TC_BRIDGE_HOST` | `0.0.0.0` | WebSocket bind address |
| `TC_BRIDGE_PORT` | `9876` | WebSocket port |
| `TC_BRIDGE_RESOLVE_HOST` | `localhost` | Resolve console script hostname |
| `TC_BRIDGE_RESOLVE_PORT` | `9877` | Resolve console script TCP port |

## Project Structure

```
server.py                    WebSocket relay server
resolve_console_script.py    Runs inside Resolve Py3 console
index.html                   Browser client (timecode display + LTC decode)
browser/
  ltc-decoder.js             Web Audio + LTC.wasm integration
  wasm/                      Pre-built LTC decoder (libltc → WebAssembly)
lib/
  tcbridge.js                JS client library (zero deps)
  tcbridge.py                Python client library
docs/
  PROTOCOL.md                WebSocket protocol spec
  SETUP.md                   BlackHole + SonoBus + Fairlight setup
examples/
  example-consumer.html      Minimal JS consumer
  example-consumer.py        Minimal Python consumer
```

## Requirements

- Python 3.10+
- DaVinci Resolve (running, with a project/timeline open)
- `websockets` Python package
- BlackHole 2ch (optional, for LTC path): `brew install blackhole-2ch`
- SonoBus (optional, for LAN LTC): [sonobus.net](https://sonobus.net)
