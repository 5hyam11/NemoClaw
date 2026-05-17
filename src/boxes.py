"""Bounding box format used across the DreamLoop pipeline.

Same schema regardless of source (Cosmos / Waymo labels / YOLO).
Lets the trained and untrained renderers stay source-agnostic.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class Box:
    x1: int
    y1: int
    x2: int
    y2: int
    label: str
    track_id: int = -1
    confidence: float = 1.0

@dataclass
class FrameBoxes:
    idx: int
    boxes: list[Box]

@dataclass
class BoxTrack:
    fps: float
    width: int
    height: int
    frames: list[FrameBoxes]

    def by_frame(self) -> dict[int, list[Box]]:
        return {f.idx: f.boxes for f in self.frames}

def save(track: BoxTrack, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fps": track.fps,
        "width": track.width,
        "height": track.height,
        "frames": [
            {"idx": f.idx, "boxes": [asdict(b) for b in f.boxes]}
            for f in track.frames
        ],
    }
    Path(path).write_text(json.dumps(payload))

def load(path: str | Path) -> BoxTrack:
    p = json.loads(Path(path).read_text())
    frames = [
        FrameBoxes(idx=f["idx"], boxes=[Box(**b) for b in f["boxes"]])
        for f in p["frames"]
    ]
    return BoxTrack(fps=p["fps"], width=p["width"], height=p["height"], frames=frames)