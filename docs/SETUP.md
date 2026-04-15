# TimecodeBridge Setup Guide

## Quick Start (Path A only, no LTC)

1. Open DaVinci Resolve with a project and timeline
2. Open the console: **Workspace > Console**, click the **Py3** tab
3. Paste: `exec(open("/Users/chadlittlepage/Documents/APPs/TimecodeBridge/resolve_console_script.py").read())`
4. Start the server: `python server.py`
5. Open `index.html` in a browser

This gives you timecode that updates when scrubbing or stopped. For real-time timecode during playback, continue below.

## Path B: LTC Audio (real-time playback sync)

### 1. Install BlackHole (virtual audio driver)

```bash
brew install blackhole-2ch
```

After install, "BlackHole 2ch" appears in System Settings > Sound as an output device and in Audio MIDI Setup as an input device.

### 2. Configure Fairlight LTC Output

In DaVinci Resolve:

1. Switch to the **Fairlight** page
2. Open **Fairlight > Patch Input/Output...** (or use the mixer routing)
3. Create a bus or track for LTC output
4. Route the LTC output to **BlackHole 2ch**
5. The Fairlight page has a built-in timecode generator. Add it to the LTC track:
   - **Effects Library > Audio FX > Fairlight FX > Timecode Generator**
   - Set frame rate to match your timeline
   - Set output level to -12dB to -6dB (LTC doesn't need to be loud)

**Alternative if Timecode Generator is unavailable:**
- Use an external LTC generator app that reads system timecode
- Route its audio output to BlackHole 2ch

### 3. Enable LTC in the Browser

1. Open `index.html` (must be served from localhost or HTTPS for mic access)
2. In the **LTC** row at the bottom, click the device dropdown
3. Select "BlackHole 2ch" (virtual devices are marked with *)
4. Click **Enable LTC**
5. Grant microphone permission when prompted
6. Play the timeline in Resolve

The source badge switches from **API** (amber) to **LTC** (green) during playback.

### Serving index.html for mic access

`getUserMedia` requires a secure context. Options:

```bash
# Option A: serve from localhost (simplest)
cd /Users/chadlittlepage/Documents/APPs/TimecodeBridge
python -m http.server 8080
# Open http://localhost:8080

# Option B: Chrome flag for LAN HTTP
# Navigate to chrome://flags/#unsafely-treat-insecure-origin-as-secure
# Add your LAN URL (e.g. http://192.168.1.100:8080)
```

## LAN Setup (SonoBus)

To sync a browser on a second machine across your LAN:

### Audio (LTC via SonoBus)

1. Download [SonoBus](https://sonobus.net) on both machines (free, open source)
2. **Machine 1 (Resolve):**
   - Launch SonoBus
   - Set audio input to **BlackHole 2ch**
   - Create or join a group name (e.g. "studio")
3. **Machine 2 (browser):**
   - Launch SonoBus, join the same group
   - Install BlackHole on this machine too: `brew install blackhole-2ch`
   - Set SonoBus output to **BlackHole 2ch**
   - In the browser, select BlackHole 2ch as the LTC device

For LAN-only use without internet:
- Pick one machine to run the SonoBus connection server
- On all clients, set the server address to `<IP>:10999`

### Metadata (WebSocket)

The browser on machine 2 connects to the WebSocket server on machine 1:
- Enter `ws://<machine-1-ip>:9876` in the WS field

If the connection is refused, allow Python through the macOS firewall:
```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add $(which python3)
```

## Troubleshooting

**"connecting..." but never connects (WebSocket)**
- Is `server.py` running on the target machine?
- Is the port (9876) open in the firewall?
- Is the URL correct? (ws://, not http://)

**LTC badge never turns green**
- Is the timeline actually playing? LTC only generates during playback.
- Check Audio MIDI Setup: is BlackHole volume at maximum?
- Verify the LTC track is not muted in Fairlight
- Try a louder LTC level (-6dB)

**No microphone permission prompt**
- Must serve from localhost or HTTPS
- Check browser settings for blocked microphone permissions

**Timecode shows but doesn't update during playback (API badge only)**
- This is expected without LTC. The Resolve scripting API does not report timecode during playback.
- Set up Path B (LTC) for real-time playback sync.
