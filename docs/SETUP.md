# TimecodeBridge Setup Guide

Created by Chad Littlepage
chad.littlepage@gmail.com | 323.974.0444

&copy; 2026 Chad Littlepage

---

## Host Machine (runs DaVinci Resolve)

### Step 1: Open Terminal

Press **Cmd+Space**, type **Terminal**, press **Enter**.

All commands below are pasted into this Terminal window.

### Step 2: Install Homebrew (if not already installed)

Paste this line and press Enter:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the prompts. If Homebrew is already installed, this will tell you.

### Step 3: Install required packages

Paste each line one at a time and press Enter:

```bash
brew install libltc
```

```bash
brew install ltc-tools
```

```bash
brew install ffmpeg
```

```bash
brew install blackhole-2ch
```

BlackHole will ask for your password. After it finishes, **reboot your Mac**. Then come back to this guide and continue from Step 4.

### Step 4: Install Python dependency

Open Terminal again after rebooting. Paste:

```bash
pip install websockets
```

If that gives an error, try this instead:

```bash
pip3 install websockets
```

If that also fails, try:

```bash
pip install --break-system-packages websockets
```

### Step 5: Navigate to the TimecodeBridge folder

If you placed TimecodeBridge in your Documents folder:

```bash
cd ~/Documents/TimecodeBridge
```

If you placed it somewhere else, replace the path. You must be in this folder for all remaining steps.

To verify you're in the right folder, paste:

```bash
ls server.py
```

It should print `server.py`. If it says "No such file", you're in the wrong folder.

### Step 6: Create Multi-Output Device

This lets you hear audio AND send it to BlackHole simultaneously.

1. Press **Cmd+Space**, type **Audio MIDI Setup**, press **Enter**
2. In the bottom-left corner, click the **+** button
3. Select **Create Multi-Output Device**
4. In the right panel, check the boxes for:
   - **BlackHole 2ch**
   - **MacBook Pro Speakers** (or your headphones/audio interface)
5. Click on **BlackHole 2ch** in the list and check **Drift Correction**
6. Optionally, double-click the name "Multi-Output Device" to rename it (e.g. "Multi-Output Blackhole")

### Step 7: Set Resolve audio output

1. Open **DaVinci Resolve**
2. Go to **DaVinci Resolve > Preferences** (or press **Cmd+,**)
3. Click **Video and Audio I/O** in the left sidebar
4. Under **Audio I/O**, change **Output device** to your Multi-Output Device
5. Click **Save**

### Step 8: Generate an LTC audio file

You must be in the TimecodeBridge folder (Step 5). If you're not sure, paste:

```bash
cd ~/Documents/TimecodeBridge
```

Now generate the LTC wav file. Change the start timecode (`--start`) and frame rate (`--fps`) to match YOUR timeline:

```bash
python ltc_gen.py --start 01:00:00:00 --fps 24 --duration 3h -o LTC_24fps_01h00m00s00f.wav
```

This takes about 60 seconds. When it finishes, the wav file will be in the TimecodeBridge folder.

**Other frame rate examples** (paste the one that matches your timeline):

23.976 fps, starting at 01:00:00:00:
```bash
python ltc_gen.py --start 01:00:00:00 --fps 23.976 --duration 3h -o LTC_23976fps_01h00m00s00f.wav
```

23.976 fps, starting at 00:00:00:00:
```bash
python ltc_gen.py --start 00:00:00:00 --fps 23.976 --duration 3h -o LTC_23976fps_00h00m00s00f.wav
```

25 fps (PAL), starting at 01:00:00:00:
```bash
python ltc_gen.py --start 01:00:00:00 --fps 25 --duration 3h -o LTC_25fps_01h00m00s00f.wav
```

29.97 fps drop-frame, starting at 01:00:00:00:
```bash
python ltc_gen.py --start 01:00:00:00 --fps 29.97 --drop --duration 3h -o LTC_2997fps_DF_01h00m00s00f.wav
```

30 fps, starting at 01:00:00:00:
```bash
python ltc_gen.py --start 01:00:00:00 --fps 30 --duration 3h -o LTC_30fps_01h00m00s00f.wav
```

### Step 9: Place LTC audio on your timeline

1. In Resolve, open your project
2. Drag the LTC wav file from Finder into the **Media Pool**
3. Switch to the **Edit** or **Fairlight** page
4. Drag the LTC wav from the Media Pool onto an audio track
5. Position it so it starts at the very beginning of your timeline
6. The start timecode baked into the wav file must match your timeline's start timecode

### Step 10: Find your BlackHole device index

In Terminal (make sure you're in the TimecodeBridge folder), paste:

```bash
ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep BlackHole
```

You'll see something like: `[10] BlackHole 2ch`

The number in brackets is your device index. The default is **10**. If yours is different, paste this (replacing `10` with your number):

```bash
export LTC_AUDIO_DEVICE=10
```

### Step 11: Start TimecodeBridge

Make sure you're in the TimecodeBridge folder, then paste:

```bash
./start.sh
```

You'll see three services start. Leave this Terminal window open and running.

### Step 12: Connect Resolve

1. In Resolve, go to **Workspace > Console**
2. Click the **Py3** tab at the top of the console
3. Paste this line and press Enter (change the path to match where you put TimecodeBridge):

```python
exec(open("/Users/YOURUSERNAME/Documents/TimecodeBridge/resolve_console_script.py").read())
```

Replace `YOURUSERNAME` with your Mac username. For example:

```python
exec(open("/Users/chad/Documents/TimecodeBridge/resolve_console_script.py").read())
```

You should see: `[TCB] Writing state to /tmp/tcb_resolve_state.json`

### Step 13: Open the browser client

Open a web browser (Chrome, Safari, or Firefox) and go to:

```
http://localhost:8080
```

You should see the Timecode Bridge display. Scrub the timeline to verify it works (you should see the timecode update with an **API** badge). Then press play (timecode should update with an **LTC** badge).

### Step 14: Find your Host IP (for client machines)

In a new Terminal tab (Cmd+T), paste:

```bash
ipconfig getifaddr en0
```

Write down this IP address. Client machines will need it.

---

## Client Machine (receives timecode)

The client machine needs **nothing installed**. Just a web browser.

### Option A: Browser (zero install)

1. Open any web browser (Chrome, Safari, Firefox)
2. In the address bar, type the Host machine's IP address with port 8080:

```
http://192.168.1.100:8080
```

Replace `192.168.1.100` with the actual Host IP from Step 14.

3. If the timecode display shows "disconnected", type the WebSocket URL in the bottom-left field:

```
ws://192.168.1.100:9876
```

Replace `192.168.1.100` with the actual Host IP. Click **Connect**.

### Option B: Custom JavaScript app

Copy the file `lib/tcbridge.js` from the TimecodeBridge folder to your project. Then add to your HTML:

```html
<script src="tcbridge.js"></script>
<script>
  const bridge = new TimecodeBridge("ws://192.168.1.100:9876");

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

Replace `192.168.1.100` with the Host IP. Zero dependencies, ~100 lines of code.

### Option C: Custom Python app

Copy the file `lib/tcbridge.py` from the TimecodeBridge folder to your project.

Install the dependency:

```bash
pip install websockets
```

Then in your Python code:

```python
from tcbridge import TimecodeBridge

bridge = TimecodeBridge("ws://192.168.1.100:9876")
bridge.on_timecode = lambda tc, source: print(f"{tc} [{source}]")
bridge.on_timeline = lambda info: print(f"{info['project']} / {info['timeline']}")
bridge.start()  # runs in background thread

# Your app code here...
```

Replace `192.168.1.100` with the Host IP.

### Option D: Any language (raw WebSocket)

Connect a WebSocket to `ws://192.168.1.100:9876` (replace with Host IP). Messages are JSON:

```json
{"type": "timecode", "tc": "01:02:03:04", "ts": 1713200000.123, "source": "ltc"}
{"type": "timeline_info", "project": "MyProject", "timeline": "Edit v2", "fps": 24, "startTC": "01:00:00:00"}
```

See [PROTOCOL.md](PROTOCOL.md) for the full spec.

---

## Every Session Checklist

On the **Host machine**, each time you open Resolve:

1. Open Terminal, navigate to TimecodeBridge folder:
   ```bash
   cd ~/Documents/TimecodeBridge
   ```
2. Start the bridge:
   ```bash
   ./start.sh
   ```
3. In Resolve Console (**Workspace > Console > Py3**), paste the `exec(open(...))` line
4. Verify: scrub the playhead, browser should update (API badge)
5. Press play, browser should show real-time timecode (LTC badge)

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
- Check BlackHole device index:
  ```bash
  ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep BlackHole
  ```
- If device index is not 10, set it before running start.sh:
  ```bash
  export LTC_AUDIO_DEVICE=YOUR_NUMBER
  ```

### Timecode glitches during playback
- Solo the LTC audio track in Fairlight (click S on the track header)
- Make sure the LTC wav frame rate matches your timeline frame rate

### Client can't connect from another machine
- Check the Host IP:
  ```bash
  ipconfig getifaddr en0
  ```
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
  Then run `./start.sh` again.
