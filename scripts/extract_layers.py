#!/usr/bin/env python3
"""Split idle cat into frozen body + head layers for continuous look-at."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from process_assets import FRAME_SIZE, chroma_key_bgra, write_png  # noqa: E402

IDLE_SRC = ROOT / "assets/source/idle-source.png"
HEAD_OUT = ROOT / "assets/head.png"
BODY_OUT = ROOT / "assets/body.png"
IDLE_OUT = ROOT / "assets/idle.png"
ANCHORS = ROOT / "assets/angle-anchors.json"

# Normalized ellipse of the head on the sitting cat.
HEAD = dict(cx=0.50, cy=0.28, rx=0.24, ry=0.30)


def ellipse_mask(h: int, w: int, cx: float, cy: float, rx: float, ry: float, feather: float) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xs / (w - 1) - cx) / rx
    ny = (ys / (h - 1) - cy) / ry
    d = np.sqrt(nx * nx + ny * ny)
    inner, outer = 1.0 - feather, 1.0 + feather
    mask = np.clip((outer - d) / max(outer - inner, 1e-6), 0, 1)
    return mask.astype(np.float32)


def main() -> None:
    bgr = cv2.imread(str(IDLE_SRC), cv2.IMREAD_COLOR)
    if bgr is None:
        sys.exit(f"missing {IDLE_SRC}")
    idle = chroma_key_bgra(bgr)
    idle = cv2.resize(idle, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)
    h, w = idle.shape[:2]
    m = ellipse_mask(h, w, HEAD["cx"], HEAD["cy"], HEAD["rx"], HEAD["ry"], 0.12)

    head = idle.copy()
    head[:, :, 3] = np.clip(head[:, :, 3].astype(np.float32) * m, 0, 255).astype(np.uint8)
    # Crop head tightly with padding.
    ys, xs = np.where(head[:, :, 3] > 12)
    y0, y1 = max(ys.min() - 8, 0), min(ys.max() + 8, h - 1)
    x0, x1 = max(xs.min() - 8, 0), min(xs.max() + 8, w - 1)
    head_crop = head[y0 : y1 + 1, x0 : x1 + 1]

    body = idle.copy()
    body[:, :, 3] = np.clip(body[:, :, 3].astype(np.float32) * (1.0 - m), 0, 255).astype(np.uint8)
    # Fill the neck hole so the body doesn't flash through.
    hole = (m > 0.35) & (idle[:, :, 3] > 12)
    if np.any(hole):
        rgb = cv2.inpaint(body[:, :, :3], hole.astype(np.uint8), 5, cv2.INPAINT_TELEA)
        body[:, :, :3] = rgb

    write_png(HEAD_OUT, head_crop)
    write_png(BODY_OUT, body)
    write_png(IDLE_OUT, idle)

    neck_x = HEAD["cx"]
    neck_y = HEAD["cy"] + HEAD["ry"] * 0.55
    # Head local anchor: neck point relative to crop.
    anchor_x = (neck_x * (w - 1) - x0) / max(head_crop.shape[1] - 1, 1)
    anchor_y = (neck_y * (h - 1) - y0) / max(head_crop.shape[0] - 1, 1)

    data = {
        "version": 4,
        "mode": "rig",
        "idle": "assets/idle.png",
        "body": "assets/body.png",
        "headSprite": "assets/head.png",
        "headBox": {
            "x0": x0 / w,
            "y0": y0 / h,
            "x1": (x1 + 1) / w,
            "y1": (y1 + 1) / h,
        },
        "neck": {"x": neck_x, "y": neck_y},
        "headAnchor": {"x": float(anchor_x), "y": float(anchor_y)},
        "look": {"maxYaw": 0.70, "maxPitch": 0.38, "follow": 24},
        "head": {"cx": 0.50, "cy": 0.30, "rx": 0.20, "ry": 0.18},
        "motion": {"idleFollow": 8},
        "notes": "Continuous rig: frozen body, yaw/pitch the head. No frame dissolves.",
    }
    ANCHORS.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"head crop {head_crop.shape} body {body.shape}")
    print(f"wrote {HEAD_OUT}, {BODY_OUT}, {ANCHORS}")


if __name__ == "__main__":
    main()
