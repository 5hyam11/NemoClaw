"""Renderers for the perception comparison.

render_clean    -> perception_trained.mp4
render_glitchy  -> perception_untrained.mp4

Glitch is seeded per frame so runs are reproducible across re-renders.
"""
from __future__ import annotations
import cv2, random
from typing import Iterable
from src.boxes import Box

CLEAN_COLOR  = (0, 200, 80)
GHOST_COLOR  = (0, 80, 200)
JITTER_MAX   = 15
DROPOUT      = 0.40
GHOST_PROB   = 0.07
LABEL_SHOW   = 0.75
MISLABEL     = 0.08
GHOST_LABELS = ("car", "ped", "truck", "cyclist")

def _draw_rounded_box(img, x1, y1, x2, y2, color, thickness=3, r=8):
    cv2.line(img, (x1+r, y1), (x2-r, y1), color, thickness)
    cv2.line(img, (x1+r, y2), (x2-r, y2), color, thickness)
    cv2.line(img, (x1, y1+r), (x1, y2-r), color, thickness)
    cv2.line(img, (x2, y1+r), (x2, y2-r), color, thickness)
    cv2.ellipse(img, (x1+r, y1+r), (r, r), 180, 0, 90, color, thickness)
    cv2.ellipse(img, (x2-r, y1+r), (r, r), 270, 0, 90, color, thickness)
    cv2.ellipse(img, (x1+r, y2-r), (r, r),  90, 0, 90, color, thickness)
    cv2.ellipse(img, (x2-r, y2-r), (r, r),   0, 0, 90, color, thickness)

def _draw_label(img, x1, y1, text, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    y_top = max(0, y1 - th - 8)
    cv2.rectangle(img, (x1, y_top), (x1 + tw + 8, y1), color, -1)
    cv2.putText(img, text, (x1 + 4, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

def render_clean(frame, boxes: Iterable[Box]):
    out = frame.copy()
    for b in boxes:
        _draw_rounded_box(out, b.x1, b.y1, b.x2, b.y2, CLEAN_COLOR)
        _draw_label(out, b.x1, b.y1, b.label, CLEAN_COLOR)
    return out

def render_glitchy(frame, boxes: Iterable[Box], frame_idx: int):
    rng = random.Random(frame_idx * 9973 + 17)
    h, w = frame.shape[:2]
    out = frame.copy()
    for b in boxes:
        if rng.random() < DROPOUT:
            continue
        jx1 = b.x1 + rng.randint(-JITTER_MAX, JITTER_MAX)
        jy1 = b.y1 + rng.randint(-JITTER_MAX, JITTER_MAX)
        jx2 = b.x2 + rng.randint(-JITTER_MAX, JITTER_MAX)
        jy2 = b.y2 + rng.randint(-JITTER_MAX, JITTER_MAX)
        cv2.rectangle(out, (jx1, jy1), (jx2, jy2), CLEAN_COLOR, 2)
        if rng.random() < LABEL_SHOW:
            shown = b.label if rng.random() > MISLABEL else rng.choice(GHOST_LABELS)
            _draw_label(out, jx1, jy1, shown, CLEAN_COLOR)
    while rng.random() < GHOST_PROB:
        gw = rng.randint(40, 120); gh = rng.randint(40, 100)
        gx = rng.randint(0, max(1, w - gw))
        gy = rng.randint(h // 3, max(h // 3 + 1, h - gh))
        cv2.rectangle(out, (gx, gy), (gx + gw, gy + gh), GHOST_COLOR, 2)
        _draw_label(out, gx, gy, "car", GHOST_COLOR)
    return out