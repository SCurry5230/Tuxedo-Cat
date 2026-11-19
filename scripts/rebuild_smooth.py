#!/usr/bin/env python3
"""Build a 192-frame body-locked, zero-crossfade optical-flow spritesheet."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import process_assets as pa  # noqa: E402
from process_assets import ANCHORS, CONTACT, FRAME_SIZE, IDLE_OUT, write_png  # noqa: E402

POSES_DIR = ROOT / "assets/poses"
SHEET_OUT = POSES_DIR / "sheet.png"

# Monotonic 32-grid slots. Slots 18 and 31 mirror clean symmetric poses (14 and 1)
# to keep every gap <= 22.5 deg without using out-of-order chin-buried stills.
KEY_SPECS: list[tuple[int, int, bool]] = [
    (0, 0, False),
    (1, 1, False),
    (2, 2, False),
    (3, 3, False),
    (4, 4, False),
    (6, 6, False),
    (8, 8, False),
    (9, 9, False),
    (10, 10, False),
    (12, 12, False),
    (14, 14, False),
    (16, 16, False),
    (18, 14, True),
    (20, 20, False),
    (21, 21, False),
    (22, 22, False),
    (23, 23, False),
    (24, 24, False),
    (25, 25, False),
    (26, 26, False),
    (27, 27, False),
    (28, 28, False),
    (30, 30, False),
]
STEPS_PER_UNIT = 6  # 32 units * 6 = 192 frames (1.875 deg/frame)
SHEET_COLS = 16
SHEET_ROWS = 12

CARDINAL_LABELS = {
    0: "up",
    4: "up-right",
    8: "right",
    12: "down-right",
    16: "down",
    20: "down-left",
    24: "left",
    28: "up-left",
}


def load_pose(idx: int) -> np.ndarray:
    path = POSES_DIR / f"{idx:02d}.png"
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"failed to read {path}")
    if img.shape[:2] != (FRAME_SIZE, FRAME_SIZE):
        img = cv2.resize(img, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)
    return img


def body_lock_bgra(frame: np.ndarray, plate: np.ndarray) -> np.ndarray:
    h = plate.shape[0]
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    # Lock shoulders/chest/paws/tail below y=0.50 with smooth neck blend above y=0.42.
    mask = np.clip((0.50 - ys) / 0.08, 0.0, 1.0)
    mask = np.repeat(mask[:, :, None], 4, axis=2)
    blended = plate.astype(np.float32) * (1.0 - mask) + frame.astype(np.float32) * mask
    return np.clip(blended, 0, 255).astype(np.uint8)


def flow_signal(bgra: np.ndarray) -> np.ndarray:
    a = bgra[:, :, 3:4].astype(np.float32) / 255.0
    comp = bgra[:, :, :3].astype(np.float32) * a + 160.0 * (1.0 - a)
    return cv2.cvtColor(np.clip(comp, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY)


def invert_flow_at_t(flow_ab: np.ndarray, flow_ba: np.ndarray, t: float) -> np.ndarray:
    h, w = flow_ab.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    u = 0.5 * (flow_ab - flow_ba)
    for _ in range(8):
        fa = cv2.remap(flow_ab, np.clip(gx - t * u[:, :, 0], 0, w - 1), np.clip(gy - t * u[:, :, 1], 0, h - 1), cv2.INTER_LINEAR)
        fb = cv2.remap(flow_ba, np.clip(gx + (1.0 - t) * u[:, :, 0], 0, w - 1), np.clip(gy + (1.0 - t) * u[:, :, 1], 0, h - 1), cv2.INTER_LINEAR)
        u = (1.0 - t) * fa + t * (-fb)
    return u


def warp_back(img: np.ndarray, disp: np.ndarray) -> np.ndarray:
    h, w = disp.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    a = img[:, :, 3:4].astype(np.float32) / 255.0
    pre = np.concatenate([img[:, :, :3].astype(np.float32) * a, img[:, :, 3:4].astype(np.float32)], axis=2)
    wpre = cv2.remap(
        pre,
        (gx + disp[:, :, 0]).astype(np.float32),
        (gy + disp[:, :, 1]).astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    wa = wpre[:, :, 3:4] / 255.0
    rgb = np.where(wa > 1e-4, wpre[:, :, :3] / np.maximum(wa, 1e-4), 0.0)
    return np.concatenate([np.clip(rgb, 0, 255), np.clip(wpre[:, :, 3:4], 0, 255)], axis=2).astype(np.uint8)


def write_anchors(anchors: list[dict], frame_count: int) -> None:
    data = {
        "version": 12,
        "mode": "sheet",
        "frameCount": frame_count,
        "spritesheet": {
            "url": "assets/poses/sheet.png",
            "cols": SHEET_COLS,
            "rows": SHEET_ROWS,
            "frameWidth": FRAME_SIZE,
            "frameHeight": FRAME_SIZE,
        },
        "idle": "assets/idle.png",
        "head": {"cx": 0.50, "cy": 0.28, "rx": 0.20, "ry": 0.16},
        "contactSheet": {"thumb": 64, "labelH": 18, "cols": SHEET_COLS, "rows": SHEET_ROWS},
        "motion": {"follow": 18, "maxDegPerSec": 720},
        "anchors": anchors,
        "notes": "192 zero-crossfade warped frames, body-locked below y=0.48.",
    }
    ANCHORS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    idle = cv2.imread(str(IDLE_OUT), cv2.IMREAD_UNCHANGED)
    if idle is None:
        idle = pa.process_idle()
        write_png(IDLE_OUT, idle)
    elif idle.shape[:2] != (FRAME_SIZE, FRAME_SIZE):
        idle = cv2.resize(idle, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)

    keys = []
    for _slot, src_idx, flipped in KEY_SPECS:
        im = load_pose(src_idx)
        if flipped:
            im = cv2.flip(im, 1)
        keys.append(body_lock_bgra(im, idle))
    sigs = [flow_signal(k) for k in keys]

    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setFinestScale(0)
    dis.setPatchSize(12)
    dis.setPatchStride(2)
    dis.setGradientDescentIterations(24)
    dis.setVariationalRefinementIterations(5)

    frames: list[np.ndarray] = []
    anchors: list[dict] = []
    n_keys = len(KEY_SPECS)

    for seg in range(n_keys):
        ia = KEY_SPECS[seg][0]
        ib = KEY_SPECS[(seg + 1) % n_keys][0]
        unit_gap = (ib - ia) % 32 or 32
        steps = unit_gap * STEPS_PER_UNIT

        anchors.append({
            "frame": len(frames),
            "angle": round(ia * 11.25, 4),
            "label": CARDINAL_LABELS.get(ia, f"{ia * 11.25:g}"),
        })

        a, b = keys[seg], keys[(seg + 1) % n_keys]
        fab = dis.calc(sigs[seg], sigs[(seg + 1) % n_keys], None)
        fba = dis.calc(sigs[(seg + 1) % n_keys], sigs[seg], None)

        frames.append(a)
        ys = np.linspace(0, 1, FRAME_SIZE, dtype=np.float32)[:, None, None]
        head_flow_mask = np.clip((0.54 - ys) / 0.08, 0.0, 1.0)
        for s in range(1, steps):
            t = s / steps
            u = invert_flow_at_t(fab, fba, t) * head_flow_mask
            # Single-source warp only: never alpha-blend A and B so ghosting/double-exposure cannot occur.
            fr = warp_back(a, -t * u) if t < 0.5 else warp_back(b, (1.0 - t) * u)
            frames.append(fr)
        print(f"segment {seg + 1}/{n_keys} ({ia}->{ib}, {steps} frames)")

    pa.SHEET_COLS = SHEET_COLS
    pa.SHEET_ROWS = SHEET_ROWS
    pa.CONTACT_THUMB = 64
    write_png(SHEET_OUT, pa.make_spritesheet(frames))
    cv2.imwrite(str(CONTACT), pa.make_contact_sheet(frames))
    write_anchors(anchors, len(frames))
    print(f"wrote {len(frames)} frames to {SHEET_OUT} and {ANCHORS}")


if __name__ == "__main__":
    main()
