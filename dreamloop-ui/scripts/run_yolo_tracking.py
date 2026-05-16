"""
Run YOLOv8 + ByteTrack on DreamLoop demo videos and export JSON for the web UI.

Usage (from dreamloop-ui/):
  pip install -r scripts/requirements-yolo.txt
  python scripts/run_yolo_tracking.py
  python scripts/run_yolo_tracking.py --preview
  python scripts/run_yolo_tracking.py public/videos/dreamloop_sunny.mp4 --key waymo

Outputs:
  public/detections/{waymo,cosmos,helios}.json  — frame-synced boxes for App.jsx
  public/detections/previews/{key}_tracked.mp4  — optional annotated preview (--preview)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
from ultralytics import YOLO

# COCO indices for vehicles
VEHICLE_CLASSES = (2, 3, 5, 7)  # car, motorcycle, bus, truck

ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "public" / "videos"
OUT_DIR = ROOT / "public" / "detections"
PREVIEW_DIR = OUT_DIR / "previews"

DEFAULT_CLIPS = {
    "waymo": ("dreamloop_sunny", "Normal / Waymo"),
    "cosmos": ("dreamloop_waymo", "Rainy / Cosmos"),
    "helios": ("dreamloop_blizzard", "Blizzard / Helios"),
}


def resolve_video(stem: str) -> Path | None:
    for ext in (".mp4", ".avi", ".mov", ".mkv"):
        p = VIDEOS_DIR / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


def norm_box(xyxy, w: int, h: int) -> dict:
    x1, y1, x2, y2 = (float(v) for v in xyxy)
    return {
        "x": x1 / w,
        "y": y1 / h,
        "w": (x2 - x1) / w,
        "h": (y2 - y1) / h,
    }


def update_motion(history: dict[int, list[tuple[float, float]]], tid: int, cx: float, cy: float, max_hist: int = 24):
    pts = history[tid]
    pts.append((cx, cy))
    if len(pts) > max_hist:
        del pts[0 : len(pts) - max_hist]


def is_parked(history: dict[int, list[tuple[float, float]]], tid: int, thresh: float = 0.018) -> bool:
    pts = history.get(tid, [])
    if len(pts) < 8:
        return False
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    return span < thresh


def process_video(
    video_path: Path,
    key: str,
    model: YOLO,
    *,
    preview: bool,
    stride: int,
    conf: float,
    parked_thresh: float,
) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    writer = None
    if preview:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        preview_path = PREVIEW_DIR / f"{key}_tracked.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(preview_path), fourcc, fps, (width, height))
        print(f"  preview → {preview_path}")

    motion: dict[int, list[tuple[float, float]]] = defaultdict(list)
    parked_flags: dict[int, bool] = {}
    frames_out: list[dict] = []
    frame_idx = -1
    det_count = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        if stride > 1 and frame_idx % stride != 0:
            continue

        results = model.track(
            frame,
            persist=True,
            classes=VEHICLE_CLASSES,
            conf=conf,
            verbose=False,
        )
        r0 = results[0]
        cars = []

        if r0.boxes is not None and len(r0.boxes):
            boxes = r0.boxes
            xyxy = boxes.xyxy.cpu().numpy()
            confs = boxes.conf.cpu().numpy()
            clss = boxes.cls.cpu().numpy().astype(int)
            ids = boxes.id
            track_ids = ids.cpu().numpy().astype(int) if ids is not None else None

            names = r0.names
            for i in range(len(xyxy)):
                box = norm_box(xyxy[i], width, height)
                cx = box["x"] + box["w"] / 2
                cy = box["y"] + box["h"] / 2
                tid = int(track_ids[i]) if track_ids is not None else -(i + 1)
                update_motion(motion, tid, cx, cy)
                parked = is_parked(motion, tid, parked_thresh)
                parked_flags[tid] = parked
                label = names.get(int(clss[i]), "vehicle")
                cars.append({
                    "id": tid,
                    **box,
                    "conf": round(float(confs[i]), 3),
                    "label": label,
                    "parked": parked,
                })
                det_count += 1

        frames_out.append({
            "i": frame_idx,
            "t": round(frame_idx / fps, 4),
            "cars": cars,
        })

        if writer is not None and r0.plot is not None:
            writer.write(r0.plot())

        if total and frame_idx % 60 == 0:
            pct = 100.0 * frame_idx / total
            print(f"  frame {frame_idx}/{total} ({pct:.0f}%)", end="\r")

    cap.release()
    if writer is not None:
        writer.release()

    parked_tracks = sum(1 for v in parked_flags.values() if v)
    moving_tracks = sum(1 for v in parked_flags.values() if not v)
    print(
        f"  done: {len(frames_out)} frames, {det_count} box-writes, "
        f"tracks parked={parked_tracks} moving={moving_tracks}"
    )

    return {
        "key": key,
        "source": video_path.name,
        "fps": fps,
        "width": width,
        "height": height,
        "frameCount": frame_idx + 1,
        "stride": stride,
        "model": "yolov8n",
        "classes": list(VEHICLE_CLASSES),
        "frames": frames_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="YOLOv8 vehicle tracking for DreamLoop UI")
    parser.add_argument("videos", nargs="*", help="Video paths (default: all three weather clips)")
    parser.add_argument("--key", help="Output JSON key (waymo|cosmos|helios); required if one video passed")
    parser.add_argument("--model", default="yolov8n.pt", help="Ultralytics weights (default: yolov8n.pt)")
    parser.add_argument("--conf", type=float, default=0.35, help="Detection confidence threshold")
    parser.add_argument("--stride", type=int, default=1, help="Process every Nth frame (2 = half size JSON)")
    parser.add_argument("--parked-thresh", type=float, default=0.018, help="Normalized motion span below = parked")
    parser.add_argument("--preview", action="store_true", help="Write annotated MP4 under public/detections/previews/")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Loading {args.model} …")
    model = YOLO(args.model)

    jobs: list[tuple[str, Path]] = []

    if args.videos:
        if len(args.videos) == 1 and not args.key:
            raise SystemExit("Pass --key waymo|cosmos|helios when processing a single file")
        for i, v in enumerate(args.videos):
            p = Path(v)
            if not p.is_file():
                raise SystemExit(f"Missing file: {p}")
            k = args.key if len(args.videos) == 1 else (args.key or f"clip{i}")
            jobs.append((k, p))
    else:
        for key, (stem, _label) in DEFAULT_CLIPS.items():
            p = resolve_video(stem)
            if p is None:
                print(f"skip {key}: no file matching {stem}.({{mp4,avi,...}}) in {VIDEOS_DIR}", file=sys.stderr)
                continue
            jobs.append((key, p))

    if not jobs:
        raise SystemExit(
            f"No videos found in {VIDEOS_DIR}.\n"
            "Add dreamloop_sunny / dreamloop_waymo / dreamloop_blizzard clips, then re-run."
        )

    for key, path in jobs:
        print(f"\n[{key}] {path.name}")
        payload = process_video(
            path,
            key,
            model,
            preview=args.preview,
            stride=max(1, args.stride),
            conf=args.conf,
            parked_thresh=args.parked_thresh,
        )
        out_path = OUT_DIR / f"{key}.json"
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        print(f"  json  → {out_path} ({out_path.stat().st_size // 1024} KB)")

    print("\nRefresh the DreamLoop UI — tabs 2–3 will use real YOLO tracks when JSON is present.")


if __name__ == "__main__":
    main()
