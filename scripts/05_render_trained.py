#!/usr/bin/env python3
"""Clean boxes over helios_flood.mp4 -> perception_trained.mp4."""
import argparse
from tqdm import tqdm
from src.boxes import load
from src.video_io import read_frames, write_video, video_meta
from src.overlay import render_clean

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="outputs/helios_flood.mp4")
    ap.add_argument("--boxes", default="data/boxes/waymo_clean.json")
    ap.add_argument("--out",   default="outputs/perception_trained.mp4")
    args = ap.parse_args()

    w, h, fps, n = video_meta(args.video)
    track = load(args.boxes).by_frame()

    with write_video(args.out, w, h, fps) as writer:
        for idx, frame in tqdm(read_frames(args.video), total=n, desc="trained"):
            writer.write(render_clean(frame, track.get(idx, [])))
    print(f"wrote {args.out}")

if __name__ == "__main__":
    main()