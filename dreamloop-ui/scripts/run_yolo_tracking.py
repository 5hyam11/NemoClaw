"""
Run YOLOv8 + ByteTrack/BoT-SORT on DreamLoop videos; export JSON with parked scores.

Usage (from dreamloop-ui/):
  python scripts/run_yolo_tracking.py
  python scripts/run_yolo_tracking.py --stride 2          # every other frame (~2× faster)
  python scripts/run_yolo_tracking.py --config scripts/yolo_tracking_config.yaml --preview

Outputs: public/detections/{waymo,cosmos,helios}.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import yaml
from ultralytics import YOLO

VEHICLE_CLASSES = (2, 3, 5, 7)

ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "public" / "videos"
OUT_DIR = ROOT / "public" / "detections"
PREVIEW_DIR = OUT_DIR / "previews"

DEFAULT_CLIPS = {
    "waymo": ("dreamloop_sunny", "Normal / Waymo"),
    "cosmos": ("dreamloop_waymo", "Rainy / Cosmos"),
    "helios": ("dreamloop_blizzard", "Blizzard / Helios"),
    "sim": ("blizzard_5s", "Sim · blizzard 5s"),
}


@dataclass
class ParkedConfig:
    history_frames: int = 45
    min_track_frames: int = 20
    displacement_thresh: float = 0.022
    speed_thresh: float = 0.006
    score_threshold: float = 0.55
    roadside_x_margin: float = 0.22
    roadside_boost: float = 0.15


@dataclass
class InferConfig:
    model: str = "yolov8s.pt"
    imgsz: int = 1280
    conf: float = 0.28
    iou: float = 0.45
    max_det: int = 80
    device: str = ""
    half: bool = False
    tracker: str = "botsort.yaml"
    stride: int = 1
    parked: ParkedConfig = field(default_factory=ParkedConfig)
    preview: bool = False


@dataclass
class TrackSample:
    frame_i: int
    t: float
    cx: float
    cy: float
    w: float
    h: float
    conf: float
    label: str
    box: dict


class TrackAccumulator:
    """Collect per-track samples, then score parked vs moving for the whole clip."""

    def __init__(self, cfg: ParkedConfig, fps: float):
        self.cfg = cfg
        self.fps = fps
        self.samples: dict[int, list[TrackSample]] = defaultdict(list)

    def add(self, tid: int, sample: TrackSample) -> None:
        self.samples[tid].append(sample)
        max_n = self.cfg.history_frames
        if len(self.samples[tid]) > max_n:
            self.samples[tid] = self.samples[tid][-max_n:]

    def score_track(self, tid: int) -> tuple[bool, float]:
        pts = self.samples.get(tid, [])
        cfg = self.cfg
        if len(pts) < cfg.min_track_frames:
            return False, 0.0

        xs = [p.cx for p in pts]
        ys = [p.cy for p in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys))

        dt = max((pts[-1].t - pts[0].t), 1.0 / self.fps)
        dx = pts[-1].cx - pts[0].cx
        dy = pts[-1].cy - pts[0].cy
        speed = math.hypot(dx, dy) / dt

        score = 0.0
        if span < cfg.displacement_thresh:
            score += 0.45
        if speed < cfg.speed_thresh:
            score += 0.4

        mean_cx = sum(xs) / len(xs)
        if abs(mean_cx - 0.5) > (0.5 - cfg.roadside_x_margin):
            score += cfg.roadside_boost

        # Stable box size often = parked at curb
        ws = [p.w for p in pts]
        hs = [p.h for p in pts]
        size_var = (max(ws) - min(ws)) + (max(hs) - min(hs))
        if size_var < 0.02:
            score += 0.1

        score = min(1.0, score)
        parked = score >= cfg.score_threshold
        return parked, round(score, 3)


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


def load_infer_config(path: Path | None) -> InferConfig:
    if path is None or not path.is_file():
        return InferConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parked_raw = data.pop("parked", {}) or {}
    parked = ParkedConfig(**{k: parked_raw[k] for k in parked_raw if hasattr(ParkedConfig, k)})
    fields = {k: data[k] for k in data if hasattr(InferConfig, k) and k != "parked"}
    return InferConfig(parked=parked, **fields)


def merge_cli(cfg: InferConfig, args: argparse.Namespace) -> InferConfig:
    if args.model:
        cfg.model = args.model
    if args.imgsz:
        cfg.imgsz = args.imgsz
    if args.conf is not None:
        cfg.conf = args.conf
    if args.iou is not None:
        cfg.iou = args.iou
    if args.max_det:
        cfg.max_det = args.max_det
    if args.device is not None:
        cfg.device = args.device
    if args.half:
        cfg.half = True
    if args.tracker:
        cfg.tracker = args.tracker
    if args.stride:
        cfg.stride = max(1, args.stride)
    if args.parked_thresh is not None:
        cfg.parked.displacement_thresh = args.parked_thresh
    if args.parked_score is not None:
        cfg.parked.score_threshold = args.parked_score
    if args.preview:
        cfg.preview = True
    return cfg


def process_video(video_path: Path, key: str, model: YOLO, cfg: InferConfig) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    writer = None
    if cfg.preview:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        preview_path = PREVIEW_DIR / f"{key}_tracked.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(preview_path), fourcc, fps, (width, height))
        print(f"  preview → {preview_path}")

    # Parked heuristics use wall-clock time; scale sample counts when striding
    parked_cfg = cfg.parked
    if cfg.stride > 1:
        parked_cfg = ParkedConfig(
            history_frames=max(20, cfg.parked.history_frames // cfg.stride),
            min_track_frames=max(10, cfg.parked.min_track_frames // cfg.stride),
            displacement_thresh=cfg.parked.displacement_thresh,
            speed_thresh=cfg.parked.speed_thresh,
            score_threshold=cfg.parked.score_threshold,
            roadside_x_margin=cfg.parked.roadside_x_margin,
            roadside_boost=cfg.parked.roadside_boost,
        )
    tracks = TrackAccumulator(parked_cfg, fps)
    frames_out: list[dict] = []
    frame_idx = -1
    det_count = 0

    track_kwargs = {
        "persist": True,
        "classes": VEHICLE_CLASSES,
        "conf": cfg.conf,
        "iou": cfg.iou,
        "max_det": cfg.max_det,
        "imgsz": cfg.imgsz,
        "verbose": False,
        "tracker": cfg.tracker,
    }
    if cfg.device:
        track_kwargs["device"] = cfg.device
    if cfg.half:
        track_kwargs["half"] = True

    while True:
        frame_idx += 1
        # Skip decode on non-processed frames (~2× faster at stride 2)
        if cfg.stride > 1 and frame_idx % cfg.stride != 0:
            if not cap.grab():
                break
            continue

        ok, frame = cap.read()
        if not ok:
            break

        results = model.track(frame, **track_kwargs)
        r0 = results[0]
        cars = []
        t_sec = frame_idx / fps

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
                label = names.get(int(clss[i]), "vehicle")
                conf = round(float(confs[i]), 3)

                tracks.add(
                    tid,
                    TrackSample(
                        frame_i=frame_idx,
                        t=t_sec,
                        cx=cx,
                        cy=cy,
                        w=box["w"],
                        h=box["h"],
                        conf=conf,
                        label=label,
                        box=box,
                    ),
                )
                parked, parked_score = tracks.score_track(tid)
                cars.append({
                    "id": tid,
                    **box,
                    "conf": conf,
                    "label": label,
                    "parked": parked,
                    "parkedScore": parked_score,
                })
                det_count += 1

        frames_out.append({"i": frame_idx, "t": round(t_sec, 4), "cars": cars})

        if writer is not None and r0.plot is not None:
            writer.write(r0.plot())

        if total and frame_idx % 60 == 0:
            print(f"  frame {frame_idx}/{total} ({100.0 * frame_idx / total:.0f}%)", end="\r")

    cap.release()
    if writer is not None:
        writer.release()

    # Second pass: stable per-track parked labels from full track history
    track_parked: dict[int, tuple[bool, float]] = {
        tid: tracks.score_track(tid) for tid in tracks.samples
    }
    parked_n = sum(1 for p, _ in track_parked.values() if p)
    for fr in frames_out:
        for car in fr["cars"]:
            tid = car["id"]
            if tid in track_parked:
                parked, score = track_parked[tid]
                car["parked"] = parked
                car["parkedScore"] = score

    print(
        f"  done: {len(frames_out)} frames, {det_count} detections, "
        f"tracks={len(track_parked)} parked={parked_n} moving={len(track_parked) - parked_n}"
    )

    return {
        "key": key,
        "source": video_path.name,
        "fps": fps,
        "width": width,
        "height": height,
        "frameCount": frame_idx + 1,
        "stride": cfg.stride,
        "model": cfg.model,
        "imgsz": cfg.imgsz,
        "conf": cfg.conf,
        "iou": cfg.iou,
        "tracker": cfg.tracker,
        "classes": list(VEHICLE_CLASSES),
        "parkedConfig": {
            "scoreThreshold": cfg.parked.score_threshold,
            "displacementThresh": cfg.parked.displacement_thresh,
            "speedThresh": cfg.parked.speed_thresh,
        },
        "frames": frames_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="YOLOv8 vehicle tracking for DreamLoop UI")
    parser.add_argument("videos", nargs="*", help="Video paths (default: all three weather clips)")
    parser.add_argument("--config", type=Path, help="YAML config (see scripts/yolo_tracking_config.yaml)")
    parser.add_argument("--key", help="Output key when processing one file")
    parser.add_argument("--model", default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--iou", type=float, default=None)
    parser.add_argument("--max-det", type=int, default=None)
    parser.add_argument("--device", default=None, help='e.g. "0" or "cpu"')
    parser.add_argument("--half", action="store_true", help="FP16 inference on GPU")
    parser.add_argument("--tracker", default=None, help="botsort.yaml or bytetrack.yaml")
    parser.add_argument("--stride", type=int, default=None)
    parser.add_argument("--parked-thresh", type=float, default=None, help="Max center displacement for parked")
    parser.add_argument("--parked-score", type=float, default=None, help="Score >= this → parked (tab 3)")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    cfg = load_infer_config(args.config)
    cfg = merge_cli(cfg, args)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"Model {cfg.model} | imgsz={cfg.imgsz} conf={cfg.conf} iou={cfg.iou} "
        f"tracker={cfg.tracker} | parked score>={cfg.parked.score_threshold}"
    )
    model = YOLO(cfg.model)

    jobs: list[tuple[str, Path]] = []
    if args.videos:
        if len(args.videos) == 1 and not args.key:
            raise SystemExit("Pass --key waymo|cosmos|helios|sim when processing a single file")
        for i, v in enumerate(args.videos):
            p = Path(v)
            if not p.is_file():
                raise SystemExit(f"Missing: {p}")
            k = args.key if len(args.videos) == 1 else (args.key or f"clip{i}")
            jobs.append((k, p))
    else:
        for key, (stem, _) in DEFAULT_CLIPS.items():
            p = resolve_video(stem)
            if p is None:
                print(f"skip {key}: no {stem}.* in {VIDEOS_DIR}", file=sys.stderr)
                continue
            jobs.append((key, p))

    if not jobs:
        raise SystemExit(f"No videos in {VIDEOS_DIR}")

    for key, path in jobs:
        print(f"\n[{key}] {path.name}")
        payload = process_video(path, key, model, cfg)
        out_path = OUT_DIR / f"{key}.json"
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        print(f"  json → {out_path} ({out_path.stat().st_size // 1024} KB)")

    print("\nReload UI → tab 3 uses parked / parkedScore from JSON.")


if __name__ == "__main__":
    main()
