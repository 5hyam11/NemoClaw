#!/usr/bin/env python3
"""Trim a Waymo dashcam clip. Output: outputs/waymo_clean.mp4

  python scripts/01_trim_waymo.py --in clips/raw/segment_front.mp4 --start 12 --duration 5
"""
import argparse, subprocess, sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="src", required=True)
    ap.add_argument("--out", default="outputs/waymo_clean.mp4")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--duration", type=float, default=5.0)
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(args.start), "-i", args.src,
        "-t", str(args.duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "medium",
        "-movflags", "+faststart",
        "-an", args.out,
    ]
    print(" ".join(cmd))
    sys.exit(subprocess.call(cmd))

if __name__ == "__main__":
    main()