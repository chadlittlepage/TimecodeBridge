#!/usr/bin/env python3
"""Generate LTC (Linear Timecode) WAV files for use with TimecodeBridge.

Usage:
  python ltc_gen.py --start 01:00:00:00 --fps 23.976 --duration 3h -o LTC_output.wav
  python ltc_gen.py --start 00:00:00:00 --fps 24 --duration 1h30m
  python ltc_gen.py --fps 29.97 --drop  # 29.97 drop-frame

Options:
  --start TC       Start timecode (default: 00:00:00:00)
  --fps RATE       Frame rate: 23.976, 24, 25, 29.97, 30, 48, 59.94, 60 (default: 24)
  --drop           Enable drop-frame (only valid for 29.97 and 59.94)
  --duration DUR   Duration: e.g. 3h, 1h30m, 90m, 5400s (default: 3h)
  --sample-rate HZ Audio sample rate (default: 48000)
  --level DB       LTC signal level in dB (default: -12)
  -o, --output     Output filename (default: auto-generated)
"""

import argparse
import math
import os
import struct
import sys
import wave


def parse_timecode(tc_str):
    """Parse HH:MM:SS:FF string to tuple."""
    parts = tc_str.replace(";", ":").replace(".", ":").split(":")
    if len(parts) != 4:
        raise ValueError(f"Invalid timecode: {tc_str} (expected HH:MM:SS:FF)")
    return int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])


def parse_duration(dur_str):
    """Parse duration string like '3h', '1h30m', '90m', '5400s' to seconds."""
    dur_str = dur_str.strip().lower()
    total = 0
    current = ""
    for ch in dur_str:
        if ch.isdigit() or ch == ".":
            current += ch
        elif ch == "h":
            total += float(current) * 3600
            current = ""
        elif ch == "m":
            total += float(current) * 60
            current = ""
        elif ch == "s":
            total += float(current)
            current = ""
    if current:
        total += float(current)
    if total <= 0:
        raise ValueError(f"Invalid duration: {dur_str}")
    return int(total)


def encode_ltc_frame(hours, mins, secs, frame, drop_frame=False):
    """Encode one LTC frame as 80 bits per SMPTE 12M."""
    bits = []

    frame_units = frame % 10
    frame_tens = frame // 10
    secs_units = secs % 10
    secs_tens = secs // 10
    mins_units = mins % 10
    mins_tens = mins // 10
    hours_units = hours % 10
    hours_tens = hours // 10

    def add_bits(val, count):
        for i in range(count):
            bits.append((val >> i) & 1)

    add_bits(frame_units, 4)
    add_bits(0, 4)
    add_bits(frame_tens, 2)
    bits.append(1 if drop_frame else 0)
    bits.append(0)
    add_bits(0, 4)
    add_bits(secs_units, 4)
    add_bits(0, 4)
    add_bits(secs_tens, 3)
    bits.append(0)  # polarity correction (set below)
    add_bits(0, 4)
    add_bits(mins_units, 4)
    add_bits(0, 4)
    add_bits(mins_tens, 3)
    bits.append(0)
    add_bits(0, 4)
    add_bits(hours_units, 4)
    add_bits(0, 4)
    add_bits(hours_tens, 2)
    bits.append(0)
    bits.append(0)
    add_bits(0, 4)

    # Polarity correction: make total 1s even
    ones = sum(bits)
    bits[27] = 1 if (ones % 2) == 1 else 0

    # Sync word (0xBFFC, LSB first)
    sync = 0xBFFC
    for i in range(16):
        bits.append((sync >> i) & 1)

    return bits


def manchester_encode(bits, samples_per_bit):
    """Manchester biphase-mark encoding."""
    audio = []
    level = 1.0
    half = samples_per_bit // 2

    for bit in bits:
        level = -level
        if bit == 0:
            audio.extend([level] * samples_per_bit)
        else:
            audio.extend([level] * half)
            level = -level
            audio.extend([level] * (samples_per_bit - half))

    return audio


def advance_tc(h, m, s, f, nominal_fps, drop_frame=False):
    """Advance timecode by one frame, handling drop-frame if needed."""
    f += 1
    if f >= nominal_fps:
        f = 0
        s += 1
        if s >= 60:
            s = 0
            m += 1
            # Drop-frame: skip frames 0 and 1 at the start of each minute,
            # except every 10th minute
            if drop_frame and m % 10 != 0:
                f = 2
            if m >= 60:
                m = 0
                h += 1
    return h, m, s, f


def generate_ltc_wav(filename, fps, duration_seconds, sample_rate, start_tc, drop_frame, level_db):
    """Generate a WAV file containing LTC audio."""
    nominal_fps = round(fps)
    samples_per_frame = sample_rate / fps
    samples_per_bit = round(samples_per_frame / 80)
    total_frames = int(duration_seconds * fps)
    amplitude = 10 ** (level_db / 20)

    h, m, s, f = start_tc

    dur_str = ""
    hours = duration_seconds // 3600
    mins = (duration_seconds % 3600) // 60
    if hours:
        dur_str += f"{int(hours)}h"
    if mins:
        dur_str += f"{int(mins)}m"
    if not dur_str:
        dur_str = f"{duration_seconds}s"

    print(f"Generating: {filename}")
    print(f"  Frame rate: {fps} fps {'(drop-frame)' if drop_frame else ''}")
    print(f"  Start TC:   {h:02d}:{m:02d}:{s:02d}:{f:02d}")
    print(f"  Duration:   {dur_str} ({total_frames} frames)")
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"  Level:      {level_db} dB")
    print(f"  Output:     {filename}")

    with wave.open(filename, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)

        for i in range(total_frames):
            bits = encode_ltc_frame(h, m, s, f, drop_frame)
            samples = manchester_encode(bits, samples_per_bit)
            pcm = struct.pack(
                f"<{len(samples)}h",
                *[int(x * amplitude * 32767) for x in samples],
            )
            wav.writeframes(pcm)

            h, m, s, f = advance_tc(h, m, s, f, nominal_fps, drop_frame)

            if total_frames > 100 and i % (total_frames // 20) == 0:
                pct = i * 100 // total_frames
                print(f"  {pct}%", flush=True)

    file_size = os.path.getsize(filename)
    print(f"  Done: {file_size / 1024 / 1024:.1f} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Generate LTC (Linear Timecode) WAV files for TimecodeBridge."
    )
    parser.add_argument("--start", default="00:00:00:00", help="Start timecode (HH:MM:SS:FF)")
    parser.add_argument("--fps", type=float, default=24.0, help="Frame rate (default: 24)")
    parser.add_argument("--drop", action="store_true", help="Enable drop-frame (29.97/59.94 only)")
    parser.add_argument("--duration", default="3h", help="Duration (e.g. 3h, 1h30m, 90m)")
    parser.add_argument("--sample-rate", type=int, default=48000, help="Sample rate (default: 48000)")
    parser.add_argument("--level", type=float, default=-12, help="Signal level in dB (default: -12)")
    parser.add_argument("-o", "--output", help="Output filename (auto-generated if omitted)")

    args = parser.parse_args()

    start_tc = parse_timecode(args.start)
    duration = parse_duration(args.duration)

    if args.drop and args.fps not in (29.97, 59.94):
        parser.error("Drop-frame is only valid for 29.97 and 59.94 fps")

    if not args.output:
        fps_str = str(args.fps).replace(".", "")
        start_str = f"{start_tc[0]:02d}h{start_tc[1]:02d}m{start_tc[2]:02d}s{start_tc[3]:02d}f"
        df = "_DF" if args.drop else ""
        args.output = f"LTC_{fps_str}fps_{start_str}{df}_{args.duration}.wav"

    generate_ltc_wav(
        filename=args.output,
        fps=args.fps,
        duration_seconds=duration,
        sample_rate=args.sample_rate,
        start_tc=start_tc,
        drop_frame=args.drop,
        level_db=args.level,
    )


if __name__ == "__main__":
    main()
