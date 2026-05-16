#!/usr/bin/env python3
"""YOLO-based 2D bbox extraction with tracking. Fallback when Cosmos
isn't extracting boxes for us. Produces the same JSON schema as the
Cosmos path so the overlay scripts don't care about source.

  python scripts/02_detect_boxes_yolo.py \
      --video outputs/waymo_clean.mp4 \
      --out   data/boxes/waymo_clean.json
"""
import argparse
from ultralytics import YOLO
from src.boxes import Box, FrameBoxes, BoxTrack, save
from src.video_io import video_meta

# COCO -> our label set
COCO_KEEP = {
    2: "car", 3: "motorcycle", 5: "bus", 7: "truck",
    0: "ped", 1: "cyclist",
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out",   required=True)
    ap.add_argument("--model", default="yolov8m.pt")
    ap.add_argument("--conf",  type=float, default=0.35)
    args = ap.parse_args()

    w, h, fps, _ = video_meta(args.video)
    model = YOLO(args.model)
    results = model.track(args.video, conf=args.conf, persist=True, verbose=False)

    frames: list[FrameBoxes] = []
    for i, r in enumerate(results):
        if r.boxes is None or len(r.boxes) == 0:
            frames.append(FrameBoxes(idx=i, boxes=[])); continue
        xyxy = r.boxes.xyxy.cpu().numpy().astype(int)
        cls  = r.boxes.cls.cpu().numpy().astype(int)
        tid  = (r.boxes.id.cpu().numpy().astype(int)
                if r.boxes.id is not None else [-1] * len(xyxy))
        conf = r.boxes.conf.cpu().numpy()
        boxes = []
        for (x1, y1, x2, y2), c, t, p in zip(xyxy, cls, tid, conf):
            if int(c) not in COCO_KEEP: continue
            boxes.append(Box(int(x1), int(y1), int(x2), int(y2),
                             COCO_KEEP[int(c)], int(t), float(p)))
        frames.append(FrameBoxes(idx=i, boxes=boxes))

    save(BoxTrack(fps=fps, width=w, height=h, frames=frames), args.out)
    print(f"wrote {args.out}: {len(frames)} frames, "
          f"{sum(len(f.boxes) for f in frames)} boxes")

if __name__ == "__main__":
    main()