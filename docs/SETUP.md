# TimecodeBridge Setup Guide

## 1. Install Dependencies

```bash
brew install libltc ltc-tools ffmpeg
brew install blackhole-2ch  # requires sudo password + reboot
pip install websockets
```

## 2. Configure Multi-Output Device

BlackHole routes audio silently. To hear audio AND send it to BlackHole:

1. Open **Audio MIDI Setup** (Applications > Utilities)
2. Click **+** at bottom left > **Create Multi-Output Device**
3. Check both **BlackHole 2ch** and your speakers/headphones
4. Enable **Drift Correction** for BlackHole (not the master device)
5. In Resolve: **Preferences > Video and Audio I/O > Output device** > select **Multi-Output Blackhole**

## 3. Generate LTC WAV Files

Generate LTC audio files to place on the Fairlight timeline:

```bash
python /path/to/TimecodeBridge/ltc_gen.py  # generates 3-hour files at 23.976 and 24fps
```

Or use the pre-generated files if available. Match the frame rate to your timeline.

## 4. Set Up Fairlight LTC Track

1. In Resolve, switch to the **Edit** or **Fairlight** page
2. Import the matching LTC wav file into the Media Pool
3. Place it on an audio track starting at frame 0 of your timeline
4. The LTC track should be the only audio (or solo it)

## 5. Run the Bridge

Three processes, in order:

```bash
# Terminal 1: WebSocket server
python server.py

# Terminal 2: LTC listener
python ltc_listener.py

# Terminal 3: HTTP server for browser
python -m http.server 8080
```

Then in Resolve's **Workspace > Console > Py3** tab:
```python
exec(open("/path/to/TimecodeBridge/resolve_console_script.py").read())
```

Open **http://localhost:8080** in a browser.

## 6. LAN Setup

For a browser on a second machine:
- Change the WS URL in the browser to `ws://<resolve-machine-ip>:9876`
- Open port 9876 in macOS firewall if needed

## Troubleshooting

**Browser shows "disconnected"**
- Is `server.py` running?
- Refresh the browser page

**No timecode during playback**
- Is `ltc_listener.py` running?
- Is the timeline playing with the LTC wav on it?
- Is Resolve output set to Multi-Output Blackhole?
- Check: `ffmpeg -f avfoundation -list_devices true -i ""` to find BlackHole device index
- Set `LTC_AUDIO_DEVICE` env var if it's not index 10

**No timecode when scrubbing**
- Re-exec the console script in Resolve
- Check for `[TCB]` messages in the Py3 console

**Timecode jumps/glitches during playback**
- Make sure the LTC track is the only audio, or solo it
- Check the LTC wav matches your timeline frame rate
