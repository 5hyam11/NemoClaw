"""Thin OpenCV wrappers so scripts don't deal with VideoCapture/Writer plumbing."""
from __future__ import annotations
import cv2
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator, Tuple
import numpy as np

def video_meta(path: str | Path) -> tuple[int, int, float, int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return w, h, fps, n

def read_frames(path: str | Path) -> Iterator[Tuple[int, np.ndarray]]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {path}")
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                return
            yield idx, frame
            idx += 1
    finally:
        cap.release()

@contextmanager
def write_video(path: str | Path, w: int, h: int, fps: float):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")   # re-encoded to h264 in script 07
    writer = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open writer for {path}")
    try:
        yield writer
    finally:
        writer.release()