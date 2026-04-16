# TimecodeBridge Setup Guide

Created by Chad Littlepage
chad.littlepage@gmail.com | 323.974.0444

&copy; 2026 Chad Littlepage

## Host Machine (runs DaVinci Resolve)

### Step 1: Install Homebrew (if not already installed)

Open Terminal and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install dependencies

```bash
brew install libltc ltc-tools ffmpeg
```

```bash
brew install blackhole-2ch
```

BlackHole requires your password. After install, **reboot your Mac** for the audio driver to load.

### Step 3: Install Python dependency

```bash
pip install websockets
```

If that fails, try:

```bash
pip install --break-system-packages websockets
```

### Step 4: Download TimecodeBridge

```bash
cd ~/Documents
git clone https://github.com/chadlittlepage/TimecodeBridge.git
cd TimecodeBridge
```

Or if you already have it, navigate to the project folder:

```bash
cd /path/to/TimecodeBridge
```

### Step 5: Create Multi-Output Device

This lets you hear audio AND send it to BlackHole simultaneously.

1. Open **Audio MIDI Setup** (press Cmd+Space, type "Audio MIDI Setup", hit Enter)
2. In the bottom-left corner, click the **+** button
3. Select **Create Multi-Output Device**
4. In the right panel, check the boxes for:
   - **BlackHole 2ch**
   - **MacBook Pro Speakers** (or your headphones/interface)
5. Click on **BlackHole 2ch** in the list and check **Drift Correction**
6. Optionally, double-click the name "Multi-Output Device" to rename it (e.g. "Multi-Output Blackhole")

### Step 6: Set Resolve audio output

1. Open DaVinci Resolve
2. Go to **DaVinci Resolve > Preferences** (Cmd+,)
3. Click **Video and Audio I/O** in the left sidebar
4. Under **Audio I/O**, set **Output device** to your Multi-Output Device
5. Click **Save**

### Step 7: Generate an LTC audio file

Match the start timecode and frame rate to your timeline:

```bash
python ltc_gen.py --start 01:00:00:00 --fps 24 --duration 3h -o LTC_24fps_01h.wav
```

Other examples:

```bash
# 23.976 fps, starting at 00:00:00:00
python ltc_gen.py --start 00:00:00:00 --fps 23.976 --duration 3h -o LTC_23976.wav

# 29.97 drop-frame
python ltc_gen.py --start 01:00:00:00 --fps 29.97 --drop --duration 2h -o LTC_2997df.wav

# 25 fps (PAL)
python ltc_gen.py --start 10:00:00:00 --fps 25 --duration 4h -o LTC_25fps.wav
```

### Step 8: Place LTC audio on your timeline

1. In Resolve, open your project
2. Import the LTC wav file into the **Media Pool** (drag it in or File > Import Media)
3. Switch to the **Edit** or **Fairlight** page
4. Drag the LTC wav onto an audio track
5. Position it so it starts at the beginning of your timeline
6. The timecode baked into the wav must match your timeline's start timecode

### Step 9: Find your BlackHole device index

```bash
ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep BlackHole
```

Look for the number in brackets, e.g. `[10] BlackHole 2ch`. The default is 10. If yours is different, you'll need to set it:

```bash
export LTC_AUDIO_DEVICE=10
```

Replace `10` with your actual device number.

### Step 10: Start TimecodeBridge

```bash
./start.sh
```

This starts three services:
- WebSocket server on port 9876
- LTC listener (captures BlackHole audio and decodes timecode)
- HTTP server on port 8080 (serves the browser client)

### Step 11: Connect Resolve

1. In Resolve, go to **Workspace > Console**
2. Click the **Py3** tab
3. Paste this line and press Enter:

```python
exec(open("/path/to/TimecodeBridge/resolve_console_script.py").read())
```

Replace `/path/to/TimecodeBridge` with your actual path. For example:

```python
exec(open("/Users/yourname/Documents/TimecodeBridge/resolve_console_script.py").read())
```

You should see: `[TCB] Writing state to /tmp/tcb_resolve_state.json`

### Step 12: Open the browser client

Open a browser and go to:

```
http://localhost:8080
```

You should see the Timecode Bridge display. Scrub the timeline to verify it works, then press play.

### Step 13: Find your Host IP (for client machines)

```bash
ipconfig getifaddr en0
```

Note this IP address — client machines will need it.

---

## Client Machine (receives timecode)

The client machine needs **nothing installed**. Just a web browser.

### Option A: Browser (zero install)

1. Open any web browser (Chrome, Safari, Firefox)
2. Navigate to:

```
http://<HOST-IP>:8080
```

Replace `<HOST-IP>` with the Host machine's IP address from Step 13 above. For example:

```
http://192.168.1.100:8080
```

3. If the WebSocket URL doesn't auto-connect, type in the bottom-left field:

```
ws://<HOST-IP>:9876
```

And click **Connect**.

### Option B: Custom JavaScript app

Add one script tag to your HTML:

```html
<script src="http://<HOST-IP>:8080/lib/tcbridge.js"></script>
<script>
  const bridge = new TimecodeBridge("ws://<HOST-IP>:9876");

  bridge.on("timecode", (data) => {
    console.log(data.tc);      // "01:02:03:04"
    console.log(data.source);  // "ltc" or "api"
  });

  bridge.on("timeline", (info) => {
    console.log(info.project);   // "My Project"
    console.log(info.timeline);  // "Edit v2"
    console.log(info.fps);       // 24
  });
</script>
```

Or copy `lib/tcbridge.js` to your project (zero dependencies, ~100 lines).

### Option C: Custom Python app

Copy `lib/tcbridge.py` to your project, then:

```bash
pip install websockets
```

```python
from tcbridge import TimecodeBridge

bridge = TimecodeBridge("ws://<HOST-IP>:9876")
bridge.on_timecode = lambda tc, source: print(f"{tc} [{source}]")
bridge.on_timeline = lambda info: print(f"{info['project']} / {info['timeline']}")
bridge.start()  # runs in background thread

# Your app code here...
```

### Option D: Any language (raw WebSocket)

Connect a WebSocket to `ws://<HOST-IP>:9876`. Messages are JSON:

```json
{"type": "timecode", "tc": "01:02:03:04", "ts": 1713200000.123, "source": "ltc"}
{"type": "timeline_info", "project": "MyProject", "timeline": "Edit v2", "fps": 24, "startTC": "01:00:00:00"}
```

See [PROTOCOL.md](PROTOCOL.md) for the full spec.

---

## Every Session Checklist

On the **Host machine**, each time you open Resolve:

1. Start TimecodeBridge: `./start.sh`
2. In Resolve Console (Py3), paste the `exec(open(...))` line
3. Verify: scrub the playhead, browser should update
4. Press play, browser should show LTC (green badge)

On **Client machines**: just open the browser URL. It auto-reconnects.

---

## Troubleshooting

### Browser shows "disconnected"
- Is `start.sh` running on the Host?
- Refresh the browser page
- Check the WebSocket URL matches the Host IP

### No timecode when scrubbing (stopped)
- Re-paste the `exec(open(...))` line in Resolve Console
- You should see `[TCB] Writing state to /tmp/tcb_resolve_state.json`

### No timecode during playback
- Is the LTC wav on the timeline and covering the current playhead position?
- Is Resolve's output device set to the Multi-Output Device?
- Check BlackHole device index: `ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep BlackHole`
- If device index is not 10: `export LTC_AUDIO_DEVICE=<your-index>` before running `./start.sh`

### Timecode glitches during playback
- Solo the LTC audio track in Fairlight (click S on the track header)
- Make sure the LTC wav frame rate matches your timeline frame rate

### Client can't connect from another machine
- Check the Host IP: `ipconfig getifaddr en0`
- Allow Python through the firewall:
  ```bash
  sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add $(which python3)
  ```
- Make sure both machines are on the same network

### "Address already in use" error
- A previous instance is still running. Kill it:
  ```bash
  pkill -f "python.*server\.py"
  pkill -f "python.*ltc_listener\.py"
  ```
