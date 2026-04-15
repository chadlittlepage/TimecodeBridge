# TimecodeBridge

WebSocket server that polls DaVinci Resolve's current timecode and broadcasts it to any connected browser on your LAN.

## Requirements

- Python 3.10+
- DaVinci Resolve (running, with a project and timeline open)
- `websockets` Python package

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Start the server (on the machine running Resolve)

```bash
python server.py
```

The server binds to `0.0.0.0:9876` by default, so any machine on your LAN can connect.

### Open the client

- **Same machine:** open `index.html` in a browser, or navigate to `http://localhost:9876`
- **Another machine on LAN:** open `index.html` and enter `ws://<resolve-machine-ip>:9876` in the connection field

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `TC_BRIDGE_HOST` | `0.0.0.0` | Bind address |
| `TC_BRIDGE_PORT` | `9876` | WebSocket port |
| `TC_BRIDGE_POLL_MS` | `100` | Polling interval in milliseconds |

### macOS firewall

If other machines can't connect, allow the port through macOS firewall:

```bash
# Check if firewall is on
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Add Python to allowed apps (if using system Python)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add $(which python3)
```

Or go to System Settings > Network > Firewall > Options and add Python.

## Architecture

```
DaVinci Resolve
    |
    | (GetCurrentTimecode() polled every 100ms)
    v
server.py  ──WebSocket──>  index.html (browser)
  0.0.0.0:9876              Any machine on LAN
```

The server only broadcasts when the timecode actually changes, so idle playback produces zero traffic.

## What gets broadcast

```json
{"type": "timecode", "tc": "01:02:03:04", "ts": 1713200000.123}
```

On connect or timeline switch:

```json
{"type": "timeline_info", "project": "MyProject", "timeline": "Edit v2", "fps": 23.976, "startTC": "01:00:00:00"}
```
