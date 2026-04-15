#!/bin/bash
# TimecodeBridge Host Installation
# Run: ./install.sh

set -e

echo "TimecodeBridge Host Installation"
echo "================================"
echo ""

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo "ERROR: Homebrew not found. Install from https://brew.sh"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
brew install libltc ltc-tools ffmpeg 2>/dev/null || true

# Check for BlackHole
if ! system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole"; then
    echo ""
    echo "BlackHole 2ch is not installed."
    echo "Installing requires your password and a reboot after."
    read -p "Install BlackHole 2ch now? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install blackhole-2ch
        echo ""
        echo "BlackHole installed. You MUST reboot before continuing."
        echo "After reboot, run this script again to finish setup."
        exit 0
    else
        echo "Skipping BlackHole. LTC playback sync will not work without it."
    fi
else
    echo "BlackHole 2ch: already installed"
fi

# Python dependencies
echo "Installing Python dependencies..."
pip install websockets 2>/dev/null || pip install --break-system-packages websockets 2>/dev/null

# Check for Multi-Output Device
if system_profiler SPAudioDataType 2>/dev/null | grep -qi "multi-output.*blackhole\|multi-output blackhole"; then
    echo "Multi-Output Blackhole device: found"
else
    echo ""
    echo "IMPORTANT: You need a Multi-Output Device in Audio MIDI Setup."
    echo "  1. Open Audio MIDI Setup (Applications > Utilities)"
    echo "  2. Click + at bottom left > Create Multi-Output Device"
    echo "  3. Check both BlackHole 2ch and your speakers"
    echo "  4. Enable Drift Correction for BlackHole"
    echo "  5. In Resolve: Preferences > Video and Audio I/O > Output > Multi-Output Device"
    echo ""
fi

# Detect BlackHole device index for ffmpeg
echo ""
echo "Detecting BlackHole audio device index..."
BH_INDEX=$(ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep "BlackHole" | grep -o '\[[0-9]*\]' | tr -d '[]')
if [ -n "$BH_INDEX" ]; then
    echo "BlackHole 2ch is device index: $BH_INDEX"
    if [ "$BH_INDEX" != "10" ]; then
        echo "NOTE: Default is 10. Set LTC_AUDIO_DEVICE=$BH_INDEX when running ltc_listener.py"
    fi
else
    echo "WARNING: BlackHole not found in audio devices. Reboot may be needed."
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Generate an LTC wav file:"
echo "     python ltc_gen.py --start 01:00:00:00 --fps 24 --duration 3h"
echo ""
echo "  2. In Resolve, place the LTC wav on a Fairlight audio track"
echo ""
echo "  3. Start the bridge:"
echo "     ./start.sh"
echo ""
echo "  4. In Resolve Console (Workspace > Console > Py3), paste:"
echo "     exec(open(\"$(pwd)/resolve_console_script.py\").read())"
