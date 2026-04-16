#!/bin/bash
# ============================================================================
# TimecodeBridge — Complete Host Installation
# ============================================================================
#
# Run this script ONCE on the Host machine (the machine running DaVinci Resolve).
# It installs everything needed and walks you through each step.
#
# Usage:
#   cd /path/to/TimecodeBridge
#   ./install.sh
#
# ============================================================================

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║       TimecodeBridge Host Install        ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ---- Step 1: Homebrew ----
echo "Step 1/8: Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    echo ""
    echo "  Homebrew is not installed."
    echo "  Install it by pasting this in Terminal:"
    echo ""
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    echo "  Then run this script again."
    exit 1
fi
echo "  Homebrew: OK"
echo ""

# ---- Step 2: Brew packages ----
echo "Step 2/8: Installing brew packages..."
echo "  (libltc, ltc-tools, ffmpeg)"
brew install libltc ltc-tools ffmpeg 2>/dev/null || true
echo "  Brew packages: OK"
echo ""

# ---- Step 3: BlackHole ----
echo "Step 3/8: Checking BlackHole 2ch..."
if system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole"; then
    echo "  BlackHole 2ch: already installed"
else
    echo ""
    echo "  BlackHole 2ch is NOT installed."
    echo "  This requires your password and a REBOOT after."
    echo ""
    read -p "  Install BlackHole 2ch now? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        brew install blackhole-2ch
        echo ""
        echo "  ┌─────────────────────────────────────────────┐"
        echo "  │  BlackHole installed. REBOOT YOUR MAC NOW.  │"
        echo "  │  After reboot, run ./install.sh again.      │"
        echo "  └─────────────────────────────────────────────┘"
        exit 0
    else
        echo "  Skipping. LTC playback sync will NOT work without BlackHole."
    fi
fi
echo ""

# ---- Step 4: Python dependency ----
echo "Step 4/8: Installing Python dependency (websockets)..."
pip install websockets 2>/dev/null || pip3 install websockets 2>/dev/null || pip install --break-system-packages websockets 2>/dev/null || true
echo "  websockets: OK"
echo ""

# ---- Step 5: Detect BlackHole device index ----
echo "Step 5/8: Detecting BlackHole audio device index..."
BH_LINE=$(ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep "BlackHole" || true)
if [ -n "$BH_LINE" ]; then
    BH_INDEX=$(echo "$BH_LINE" | grep -o '\[[0-9]*\]' | tr -d '[]')
    echo "  Found: $BH_LINE"
    echo "  Device index: $BH_INDEX"
    if [ "$BH_INDEX" != "10" ]; then
        echo ""
        echo "  NOTE: Default device index is 10, yours is $BH_INDEX."
        echo "  Add this to your shell profile (~/.zshrc):"
        echo ""
        echo "    export LTC_AUDIO_DEVICE=$BH_INDEX"
        echo ""
    fi
else
    echo "  WARNING: BlackHole not found. Reboot may be needed."
fi
echo ""

# ---- Step 6: Generate default LTC wav files ----
echo "Step 6/8: Generating default LTC wav files..."
echo "  These cover the most common timeline configurations."
echo ""

generate_if_missing() {
    local file="$1"
    shift
    if [ -f "$DIR/ltc_wavs/$file" ]; then
        echo "  $file: already exists, skipping"
    else
        echo "  Generating $file..."
        python "$DIR/ltc_gen.py" "$@" -o "$DIR/ltc_wavs/$file"
        echo ""
    fi
}

mkdir -p "$DIR/ltc_wavs"

generate_if_missing "LTC_24fps_00h_3hr.wav"    --start 00:00:00:00 --fps 24    --duration 3h
generate_if_missing "LTC_24fps_01h_3hr.wav"    --start 01:00:00:00 --fps 24    --duration 3h
generate_if_missing "LTC_23976fps_00h_3hr.wav" --start 00:00:00:00 --fps 23.976 --duration 3h
generate_if_missing "LTC_23976fps_01h_3hr.wav" --start 01:00:00:00 --fps 23.976 --duration 3h
generate_if_missing "LTC_25fps_01h_3hr.wav"    --start 01:00:00:00 --fps 25    --duration 3h
generate_if_missing "LTC_2997fps_01h_3hr_DF.wav" --start 01:00:00:00 --fps 29.97 --drop --duration 3h
generate_if_missing "LTC_30fps_01h_3hr.wav"    --start 01:00:00:00 --fps 30    --duration 3h

echo "  LTC wav files are in: $DIR/ltc_wavs/"
echo ""

# ---- Step 7: Multi-Output Device ----
echo "Step 7/8: Multi-Output Device setup"
echo ""
echo "  You need a Multi-Output Device in Audio MIDI Setup so that"
echo "  Resolve audio goes to BOTH your speakers AND BlackHole."
echo ""
echo "  If you have NOT already created one:"
echo ""
echo "    1. Open Audio MIDI Setup:"
echo "       Press Cmd+Space, type 'Audio MIDI Setup', press Enter"
echo ""
echo "    2. Click the + button at bottom-left"
echo "       Select 'Create Multi-Output Device'"
echo ""
echo "    3. Check the boxes for:"
echo "       - BlackHole 2ch"
echo "       - MacBook Pro Speakers (or your audio interface)"
echo ""
echo "    4. Click 'BlackHole 2ch' and check 'Drift Correction'"
echo ""
echo "    5. In DaVinci Resolve:"
echo "       Preferences > Video and Audio I/O > Output device"
echo "       Select your Multi-Output Device"
echo ""
read -p "  Press Enter when done (or if already configured)..." -r
echo ""

# ---- Step 8: Summary ----
RESOLVE_CMD="exec(open(\"$DIR/resolve_console_script.py\").read())"

echo "Step 8/8: Installation complete!"
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  SETUP COMPLETE                                     │"
echo "  │                                                     │"
echo "  │  LTC wav files: $DIR/ltc_wavs/"
echo "  │                                                     │"
echo "  │  To start TimecodeBridge:                           │"
echo "  │    cd $DIR"
echo "  │    ./start.sh                                       │"
echo "  │                                                     │"
echo "  │  In Resolve Console (Workspace > Console > Py3):    │"
echo "  │    $RESOLVE_CMD"
echo "  │                                                     │"
echo "  │  Browser (this machine):                            │"
echo "  │    http://localhost:8080                             │"
echo "  │                                                     │"
echo "  │  Browser (other machines on LAN):                   │"
IP=$(ipconfig getifaddr en0 2>/dev/null || echo "<your-ip>")
echo "  │    http://$IP:8080"
echo "  │                                                     │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo "  IMPORTANT: Place an LTC wav file on a Fairlight audio track"
echo "  in your Resolve project. Match the start TC and frame rate"
echo "  to your timeline. Files are in ltc_wavs/"
echo ""
echo "  To generate a custom LTC wav:"
echo "    python ltc_gen.py --start 01:00:00:00 --fps 24 --duration 3h -o my_ltc.wav"
echo ""
