# TimecodeBridge WebSocket Protocol v2.0

Connect to `ws://<host>:9876`. All messages are JSON, one per WebSocket frame.

## Server → Client Messages

### hello
Sent once on connect.
```json
{"type": "hello", "version": "2.0", "server": "TimecodeBridge"}
```

### timecode
Current playhead position. Only sent when the value changes.
```json
{"type": "timecode", "tc": "01:02:03:04", "ts": 1713200000.123, "source": "api"}
```
- `tc` — SMPTE timecode string (HH:MM:SS:FF)
- `ts` — Unix timestamp when the timecode was read
- `source` — `"api"` (from Resolve scripting API, accurate when stopped/scrubbing) or `"ltc"` (from LTC audio decode, accurate during playback). Note: LTC timecode is decoded client-side in the browser and does not flow through the server. Server-sent timecode messages always have `source: "api"`.

### timeline_info
Sent on connect and when the active timeline changes.
```json
{
  "type": "timeline_info",
  "project": "MyProject",
  "timeline": "Edit v2",
  "fps": 23.976,
  "startTC": "01:00:00:00"
}
```

### markers
Sent after timeline_info when markers are available.
```json
{
  "type": "markers",
  "markers": [
    {"frame": 240, "color": "Blue", "name": "VFX Shot 1", "note": "", "duration": 120, "customData": ""},
    {"frame": 1440, "color": "Green", "name": "Act 2", "note": "Key scene", "duration": 1, "customData": ""}
  ]
}
```
- `frame` — frame offset from timeline start (0-based)

### error
Sent when Resolve connection is lost.
```json
{"type": "error", "message": "No timeline is open in DaVinci Resolve."}
```

## Client Libraries

### JavaScript
```html
<script src="lib/tcbridge.js"></script>
<script>
  const bridge = new TimecodeBridge("ws://192.168.1.100:9876");
  bridge.on("timecode", (data) => console.log(data.tc, data.source));
  bridge.on("timeline", (info) => console.log(info.project));
  bridge.on("markers", (markers) => console.log(markers));
</script>
```

### Python
```python
from lib.tcbridge import TimecodeBridge

bridge = TimecodeBridge("ws://192.168.1.100:9876")
bridge.on_timecode = lambda tc, source: print(tc, source)
bridge.start()  # background thread
```

## Notes

- The server only broadcasts when values change. A paused timeline produces zero traffic.
- No authentication. Intended for trusted LANs.
- Client → server messages are currently ignored (protocol is unidirectional).
