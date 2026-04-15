#!/usr/bin/env python3
"""LTC listener — captures audio from BlackHole via ffmpeg, decodes with libltc
via ctypes (no FIFO, no buffering), pushes frame-accurate timecode via TCP.

Requires: brew install libltc ffmpeg blackhole-2ch
"""

import ctypes
import ctypes.util
import json
import os
import socket
import struct
import subprocess
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEVICE_INDEX = os.environ.get("LTC_AUDIO_DEVICE", "10")  # BlackHole 2ch
SAMPLE_RATE = 48000
BRIDGE_PORT = int(os.environ.get("TC_BRIDGE_LTC_PORT", "9878"))

# ---------------------------------------------------------------------------
# libltc ctypes bindings
# ---------------------------------------------------------------------------

_ltc_path = ctypes.util.find_library("ltc") or "/opt/homebrew/lib/libltc.dylib"
_ltc = ctypes.cdll.LoadLibrary(_ltc_path)

# LTCDecoder* ltc_decoder_create(int apv, int queue_size)
_ltc.ltc_decoder_create.restype = ctypes.c_void_p
_ltc.ltc_decoder_create.argtypes = [ctypes.c_int, ctypes.c_int]

# void ltc_decoder_write_float(LTCDecoder*, float*, size_t, ltc_off_t)
_ltc.ltc_decoder_write_float.restype = None
_ltc.ltc_decoder_write_float.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_longlong
]

# int ltc_decoder_read(LTCDecoder*, LTCFrameExt*)
_ltc.ltc_decoder_read.restype = ctypes.c_int
_ltc.ltc_decoder_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

# void ltc_frame_to_time(SMPTETimecode*, LTCFrame*, int)
_ltc.ltc_frame_to_time.restype = None
_ltc.ltc_frame_to_time.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]

# void ltc_decoder_free(LTCDecoder*)
_ltc.ltc_decoder_free.restype = None
_ltc.ltc_decoder_free.argtypes = [ctypes.c_void_p]


class SMPTETimecode(ctypes.Structure):
    _fields_ = [
        ("timezone", ctypes.c_char * 6),
        ("years", ctypes.c_ubyte),
        ("months", ctypes.c_ubyte),
        ("days", ctypes.c_ubyte),
        ("hours", ctypes.c_ubyte),
        ("mins", ctypes.c_ubyte),
        ("secs", ctypes.c_ubyte),
        ("frame", ctypes.c_ubyte),
    ]


class LTCFrame(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.c_ubyte * 10),  # 80 bits
    ]


class LTCFrameExt(ctypes.Structure):
    _fields_ = [
        ("ltc", LTCFrame),
        ("off_start", ctypes.c_longlong),
        ("off_end", ctypes.c_longlong),
        ("reverse", ctypes.c_int),
        ("biphase_tics", ctypes.c_float * 80),
        ("sample_min", ctypes.c_float),
        ("sample_max", ctypes.c_float),
        ("volume", ctypes.c_double),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_ltc_listener():
    print(f"LTC Listener (libltc native) starting", flush=True)
    print(f"Audio device: index {DEVICE_INDEX}", flush=True)
    print(f"TCP port: {BRIDGE_PORT}", flush=True)

    # TCP server
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", BRIDGE_PORT))
    srv.listen(5)
    srv.settimeout(0.01)

    clients = []

    # Create libltc decoder
    apv = SAMPLE_RATE / 25  # audio frames per video frame (approx)
    decoder = _ltc.ltc_decoder_create(int(apv), 32)
    total_samples = 0

    # Start ffmpeg — raw float32 to stdout, minimal buffering
    cmd = [
        "ffmpeg",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-f", "avfoundation",
        "-i", f":{DEVICE_INDEX}",
        "-f", "f32le",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-loglevel", "error",
        "pipe:1",
    ]
    print(f"Starting: {' '.join(cmd)}", flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    last_tc = None
    last_tc_frames = -1
    last_decode_time = 0
    chunk_samples = 1024
    chunk_bytes = chunk_samples * 4  # float32
    frame_ext = LTCFrameExt()
    stime = SMPTETimecode()

    # Add flush function binding
    try:
        _ltc.ltc_decoder_queue_flush.restype = None
        _ltc.ltc_decoder_queue_flush.argtypes = [ctypes.c_void_p]
        has_flush = True
    except AttributeError:
        has_flush = False

    print(f"Decoding LTC... (play the timeline)\n", flush=True)

    try:
        while True:
            # Accept TCP clients
            try:
                conn, addr = srv.accept()
                clients.append(conn)
                print(f"\n[+] Client: {addr}", flush=True)
            except socket.timeout:
                pass

            # If no decode in >1 second, flush pipe buffer and reset decoder
            now = time.time()
            if last_decode_time > 0 and (now - last_decode_time) > 1.0:
                # Drain any stale buffered audio
                import select
                while select.select([proc.stdout], [], [], 0)[0]:
                    discarded = proc.stdout.read(chunk_bytes)
                    if not discarded:
                        break
                # Reset decoder state
                _ltc.ltc_decoder_free(decoder)
                decoder = _ltc.ltc_decoder_create(int(apv), 32)
                total_samples = 0
                last_tc_frames = -1
                last_decode_time = 0

            # Read audio chunk from ffmpeg stdout
            raw = proc.stdout.read(chunk_bytes)
            if not raw or len(raw) < chunk_bytes:
                if proc.poll() is not None:
                    print("[!] ffmpeg exited", flush=True)
                    break
                continue

            # Convert to float array
            n = len(raw) // 4
            float_array = (ctypes.c_float * n)()
            ctypes.memmove(float_array, raw, len(raw))

            # Feed to libltc
            _ltc.ltc_decoder_write_float(
                decoder, float_array, n, total_samples
            )
            total_samples += n

            # Read decoded frames
            while _ltc.ltc_decoder_read(decoder, ctypes.byref(frame_ext)):
                _ltc.ltc_frame_to_time(
                    ctypes.byref(stime), ctypes.byref(frame_ext.ltc), 1
                )

                # Check drop frame bit (bit 10 of the 80-bit frame)
                dfbit = (frame_ext.ltc.data[1] >> 2) & 1
                sep = "." if dfbit else ":"

                tc = f"{stime.hours:02d}:{stime.mins:02d}:{stime.secs:02d}{sep}{stime.frame:02d}"

                # Sanity check (24fps max frame = 23)
                if stime.hours > 23 or stime.mins > 59 or stime.secs > 59 or stime.frame > 23:
                    continue

                # Continuity filter: reject jumps > 2 seconds
                current_frames = ((stime.hours * 60 + stime.mins) * 60 + stime.secs) * 24 + stime.frame
                if last_tc_frames >= 0:
                    jump = abs(current_frames - last_tc_frames)
                    if jump > 48 and jump < (24 * 3600 * 24 - 48):
                        continue
                last_tc_frames = current_frames
                last_decode_time = time.time()

                if tc != last_tc:
                    last_tc = tc
                    msg = json.dumps({
                        "type": "timecode",
                        "tc": tc,
                        "ts": time.time(),
                        "source": "ltc",
                    }) + "\n"

                    dead = []
                    for c in clients:
                        try:
                            c.sendall(msg.encode())
                        except Exception:
                            dead.append(c)
                    for c in dead:
                        clients.remove(c)
                        try:
                            c.close()
                        except Exception:
                            pass

                    print(f"\r  {tc}", end="", flush=True)

    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        _ltc.ltc_decoder_free(decoder)
        proc.terminate()
        proc.wait()
        srv.close()


if __name__ == "__main__":
    # Verify ffmpeg exists
    result = subprocess.run(["which", "ffmpeg"], capture_output=True)
    if result.returncode != 0:
        print("ERROR: ffmpeg not found. Install: brew install ffmpeg")
        exit(1)

    # Show device
    print("Audio devices:", flush=True)
    result = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True, text=True,
    )
    for line in result.stderr.split("\n"):
        if "BlackHole" in line:
            print(f"  {line.strip()}", flush=True)

    run_ltc_listener()
