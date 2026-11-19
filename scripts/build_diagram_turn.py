#!/usr/bin/env python3
"""8 diagram poses, frozen body, warp-only in-betweens (no crossfade)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from process_assets import (  # noqa: E402
    ANCHORS,
    CONTACT,
    FRAME_SIZE,
    IDLE_OUT,
    SPRITESHEET,
    TRANSPARENT_DIR,
    chroma_key_bgra,
    make_tray_icon,
    process_idle,
    write_png,
)

EXTRACTED = ROOT / "assets/extracted-frames"
# ffmpeg 1-based names matching the 8 diagram directions.
KEY_FILES = ["001.png", "027.png", "053.png", "080.png", "106.png", "132.png", "159.png", "185.png"]
LABELS = ["up", "up-right", "right", "down-right", "down", "down-left", "left", "up-left"]
STEPS = 12  # 8 * 12 = 96 frames
COLS = 12
ROWS = 8


def load_key(name: str) -> np.ndarray:
    img = cv2.imread(str(EXTRACTED / name), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"missing {EXTRACTED / name}")
    img = cv2.resize(img, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)
    return chroma_key_bgra(img)


def body_lock(frame: np.ndarray, plate: np.ndarray) -> np.ndarray:
    h = plate.shape[0]
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    # Keep chest/legs/tail from plate; take only the head from the pose.
    mask = np.clip((0.56 - ys) / 0.08, 0.0, 1.0)
    mask = np.repeat(mask[:, :, None], 4, axis=2)
    out = plate.astype(np.float32) * (1.0 - mask) + frame.astype(np.float32) * mask
    return np.clip(out, 0, 255).astype(np.uint8)


def rgb_for_flow(bgra: np.ndarray) -> np.ndarray:
    a = bgra[:, :, 3:4].astype(np.float32) / 255.0
    return np.clip(bgra[:, :, :3].astype(np.float32) * a, 0, 255).astype(np.uint8)


def compute_flow(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    g1 = cv2.cvtColor(rgb_for_flow(a), cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(rgb_for_flow(b), cv2.COLOR_BGR2GRAY)
    return cv2.calcOpticalFlowFarneback(
        g1, g2, None, 0.5, 5, 25, 4, 7, 1.5, 0
    )


def warp_flow(img: np.ndarray, flow: np.ndarray) -> np.ndarray:
    h, w = flow.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    map_x = (grid_x + flow[:, :, 0]).astype(np.float32)
    map_y = (grid_y + flow[:, :, 1]).astype(np.float32)
    return cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def make_contact(frames: list[np.ndarray]) -> None:
    thumb, label_h = 72, 18
    cell_w, cell_h = thumb, thumb + label_h
    sheet = np.full((ROWS * cell_h, COLS * cell_w, 3), 40, dtype=np.uint8)
    for i, fr in enumerate(frames):
        r, c = divmod(i, COLS)
        rgb = cv2.cvtColor(fr, cv2.COLOR_BGRA2BGR)
        th = cv2.resize(rgb, (thumb, thumb), interpolation=cv2.INTER_AREA)
        y, x = r * cell_h, c * cell_w
        sheet[y : y + thumb, x : x + thumb] = th
        cv2.putText(
            sheet, str(i), (x + 3, y + thumb + 13),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 220), 1, cv2.LINE_AA,
        )
    cv2.imwrite(str(CONTACT), sheet)


def make_sheet(frames: list[np.ndarray]) -> None:
    w = h = FRAME_SIZE
    sheet = np.zeros((ROWS * h, COLS * w, 4), dtype=np.uint8)
    for i, fr in enumerate(frames):
        r, c = divmod(i, COLS)
        sheet[r * h : r * h + h, c * w : c * w + w] = fr
    write_png(SPRITESHEET, sheet)


def write_anchors(n: int) -> None:
    anchors = []
    for i, label in enumerate(LABELS):
        anchors.append({"frame": i * STEPS, "angle": i * 45, "label": label})
    data = {
        "version": 5,
        "mode": "frames",
        "frameCount": n,
        "framesDir": "assets/transparent-frames",
        "spritesheet": {
            "url": "assets/spritesheet.png",
            "cols": COLS,
            "rows": ROWS,
            "frameWidth": FRAME_SIZE,
            "frameHeight": FRAME_SIZE,
        },
        "idle": "assets/idle.png",
        "head": {"cx": 0.50, "cy": 0.30, "rx": 0.20, "ry": 0.16},
        "contactSheet": {"thumb": 72, "labelH": 18, "cols": COLS, "rows": ROWS},
        "motion": {"idleFollow": 10, "maxFramesPerSec": 180},
        "anchors": anchors,
        "notes": "Diagram cycle: up→right→down→left→up. Warp-only, no crossfade. Body locked.",
    }
    ANCHORS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    keys = [load_key(name) for name in KEY_FILES]
    plate = keys[0]
    keys = [body_lock(k, plate) for k in keys]
    dest = ROOT / "assets/source/diagram-keys"
    dest.mkdir(parents=True, exist_ok=True)
    for i, k in enumerate(keys):
        write_png(dest / f"{i:02d}-{LABELS[i]}.png", k)

    flows = [compute_flow(keys[i], keys[(i + 1) % 8]) for i in range(8)]

    TRANSPARENT_DIR.mkdir(parents=True, exist_ok=True)
    for old in TRANSPARENT_DIR.glob("*"):
        old.unlink()

    frames = []
    idx = 0
    for seg in range(8):
        a = keys[seg]
        b = keys[(seg + 1) % 8]
        flow = flows[seg]
        for s in range(STEPS):
            t = s / STEPS
            if s == 0:
                fr = a
            else:
                # Warp pose A toward B. Do NOT blend B in — that was the fade.
                fr = warp_flow(a, flow * t)
            frames.append(fr)
            write_png(TRANSPARENT_DIR / f"{idx:03d}.png", fr)
            idx += 1
        print(f"segment {seg + 1}/8 {LABELS[seg]}")

    n = len(frames)
    make_contact(frames)
    make_sheet(frames)
    idle = process_idle()
    write_png(IDLE_OUT, idle)
    write_png(ROOT / "assets/tray-icon.png", make_tray_icon(idle))
    write_anchors(n)
    print(f"wrote {n} frames (warp-only, frozen body)")


if __name__ == "__main__":
    main()
