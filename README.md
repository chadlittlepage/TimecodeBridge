# TimecodeBridge

Real-time DaVinci Resolve timecode over WebSocket for browsers on your LAN.

Two sync paths that work together:
- **API (stopped/scrubbing):** Resolve scripting API polled via console script, written to a state file.
- **LTC (playback):** Fairlight LTC audio decoded server-side via libltc + ffmpeg from BlackHole. Frame-accurate.

The browser merges both: LTC during playback, API when stopped.

## Architecture

```
PATH A (metadata + stopped TC):
  Resolve Py3 Console ──> /tmp/tcb_resolve_state.json ──> server.py ──WS:9876──> Browser

PATH B (live playback TC):
  Resolve Fairlight LTC ──> BlackHole 2ch ──> ffmpeg ──> ltc_listener.py (libltc)
  ──TCP:9878──> server.py ──WS:9876──> Browser
```

## Requirements

- Python 3.10+
- DaVinci Resolve (running, with a project/timeline open)
- `websockets` Python package
- `libltc` and `ltc-tools`: `brew install libltc ltc-tools`
- `ffmpeg`: `brew install ffmpeg`
- `BlackHole 2ch`: `brew install blackhole-2ch` (requires sudo + reboot)
- Multi-Output Device in Audio MIDI Setup (BlackHole + speakers)
- LTC wav file on a Fairlight audio track (see Setup)

## Quick Start

```bash
pip install websockets

# 1. Start the WebSocket server
python server.py

# 2. Start the LTC listener
python ltc_listener.py

# 3. In Resolve, open Workspace > Console > Py3, paste:
exec(open("/path/to/TimecodeBridge/resolve_console_script.py").read())

# 4. Serve and open the browser client
python -m http.server 8080
# Open http://localhost:8080
```

See [docs/SETUP.md](docs/SETUP.md) for BlackHole, Multi-Output Device, and Fairlight LTC track setup.

## For Developers

Hook into the timecode stream from your own app:

### JavaScript
```html
<script src="lib/tcbridge.js"></script>
<script>
  const bridge = new TimecodeBridge("ws://192.168.1.100:9876");
  bridge.on("timecode", (data) => console.log(data.tc, data.source));
  bridge.on("timeline", (info) => console.log(info.project));
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
| `TC_BRIDGE_LTC_HOST` | `localhost` | LTC listener hostname |
| `TC_BRIDGE_LTC_PORT` | `9878` | LTC listener TCP port |
| `LTC_AUDIO_DEVICE` | `10` | ffmpeg audio device index for BlackHole |

## Known Limitations

\* LTC reverse playback is choppy — libltc decodes approximately half the frames when playing backwards. This is inherent to the LTC format (Manchester biphase encoding is designed for forward reading). Forward playback is frame-accurate. This matches the behavior of hardware LTC readers playing tape in reverse.

## Author

Created by Chad Littlepage
chad.littlepage@gmail.com
323.974.0444

&copy; 2026 Chad Littlepage

## Project Structure

```
server.py                    WebSocket relay (file watcher + LTC TCP reader)
ltc_listener.py              LTC decoder (ffmpeg + libltc via ctypes)
resolve_console_script.py    Runs inside Resolve Py3 console (file writer)
index.html                   Browser client
lib/
  tcbridge.js                JS client library (zero deps)
  tcbridge.py                Python client library
docs/
  PROTOCOL.md                WebSocket protocol spec
  SETUP.md                   BlackHole + Fairlight setup guide
examples/
  example-consumer.html      Minimal JS consumer
  example-consumer.py        Minimal Python consumer
```
