#!/usr/bin/env python3
"""Extract video frames, chroma-key to alpha, build contact sheet + spritesheet."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE_VIDEO = ROOT / "assets/source/cat-head-turn-7s.mp4"
IDLE_SOURCE = ROOT / "assets/source/idle-source.png"
RAW_DIR = ROOT / "assets/extracted-frames"
TRANSPARENT_DIR = ROOT / "assets/transparent-frames"
CONTACT = ROOT / "assets/contactsheet.png"
SPRITESHEET = ROOT / "assets/spritesheet.png"
IDLE_OUT = ROOT / "assets/idle.png"
TRAY_OUT = ROOT / "assets/tray-icon.png"
ANCHORS = ROOT / "assets/angle-anchors.json"

FRAME_SIZE = 256
CONTACT_THUMB = 96
SHEET_COLS = 15
SHEET_ROWS = 14
EXPECTED_FRAMES = 210


def chroma_key_bgra(bgr: np.ndarray) -> np.ndarray:
    """Key #00FF00-ish screen to alpha. Keep white/gray fur (low saturation)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    v = hsv[:, :, 2].astype(np.float32)

    hue_dist = np.abs(h - 60.0)
    hue_dist = np.minimum(hue_dist, 180.0 - hue_dist)

    # Screen score: green hue + high saturation + reasonably bright.
    hue_w = np.clip(1.0 - hue_dist / 28.0, 0.0, 1.0)
    sat_w = np.clip((s - 45.0) / 70.0, 0.0, 1.0)
    val_w = np.clip((v - 35.0) / 50.0, 0.0, 1.0)
    screen = hue_w * sat_w * val_w

    alpha = 1.0 - np.clip((screen - 0.18) / 0.42, 0.0, 1.0)

    img = bgr.astype(np.float32)
    b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    # Despill: pull green toward red/blue average on remaining pixels.
    avg = (r + b) * 0.5
    g2 = np.minimum(g, avg + 10.0)
    spill = (g > avg + 6.0) & (alpha > 0.05)
    g = np.where(spill, g * 0.35 + g2 * 0.65, g)

    # Fully transparent pixels become pure black (clean composite).
    a8 = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    out = np.dstack(
        [
            np.clip(b, 0, 255).astype(np.uint8),
            np.clip(g, 0, 255).astype(np.uint8),
            np.clip(r, 0, 255).astype(np.uint8),
            a8,
        ]
    )
    out[a8 < 8] = (0, 0, 0, 0)
    return out


def extract_raw_frames() -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for old in RAW_DIR.glob("*"):
        old.unlink()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    pattern = str(RAW_DIR / "%03d.png")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(SOURCE_VIDEO),
        "-vsync",
        "0",
        pattern,
    ]
    print("ffmpeg", " ".join(cmd[1:4]), "...")
    subprocess.check_call(cmd)
    frames = sorted(RAW_DIR.glob("*.png"))
    print(f"extracted {len(frames)} raw frames")
    return frames


def process_frame(path: Path, size: int) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError(f"failed to read {path}")
    bgra = chroma_key_bgra(bgr)
    if bgra.shape[0] != size or bgra.shape[1] != size:
        bgra = cv2.resize(bgra, (size, size), interpolation=cv2.INTER_AREA)
    return bgra


def write_png(path: Path, bgra: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), bgra)


def make_contact_sheet(frames: list[np.ndarray]) -> np.ndarray:
    thumb = CONTACT_THUMB
    cols, rows = SHEET_COLS, SHEET_ROWS
    label_h = 18
    cell_w, cell_h = thumb, thumb + label_h
    sheet = np.full((rows * cell_h, cols * cell_w, 3), 40, dtype=np.uint8)
    for i, fr in enumerate(frames):
        r, c = divmod(i, cols)
        if r >= rows:
            break
        rgb = cv2.cvtColor(fr, cv2.COLOR_BGRA2BGR)
        th = cv2.resize(rgb, (thumb, thumb), interpolation=cv2.INTER_AREA)
        y, x = r * cell_h, c * cell_w
        sheet[y : y + thumb, x : x + thumb] = th
        cv2.putText(
            sheet,
            str(i),
            (x + 4, y + thumb + 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )
    return sheet


def make_spritesheet(frames: list[np.ndarray]) -> np.ndarray:
    w = h = FRAME_SIZE
    cols, rows = SHEET_COLS, SHEET_ROWS
    sheet = np.zeros((rows * h, cols * w, 4), dtype=np.uint8)
    for i, fr in enumerate(frames):
        r, c = divmod(i, cols)
        if r >= rows:
            break
        y, x = r * h, c * w
        sheet[y : y + h, x : x + w] = fr
    return sheet


def process_idle() -> np.ndarray:
    bgr = cv2.imread(str(IDLE_SOURCE), cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError("idle source missing")
    bgra = chroma_key_bgra(bgr)
    return cv2.resize(bgra, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)


def make_tray_icon(idle: np.ndarray) -> np.ndarray:
    # Crop around the head (upper-middle) then scale to 64px.
    h, w = idle.shape[:2]
    y0, y1 = int(h * 0.08), int(h * 0.55)
    x0, x1 = int(w * 0.28), int(w * 0.72)
    crop = idle[y0:y1, x0:x1]
    return cv2.resize(crop, (64, 64), interpolation=cv2.INTER_AREA)


def write_default_anchors(frame_count: int) -> None:
    # Seed only — calibrator is the source of truth. 8 equal time splits
    # match how the source video was built, NOT a claim of uniform 360°.
    labels = [
        (0, "up"),
        (45, "up-right"),
        (90, "right"),
        (135, "down-right"),
        (180, "down"),
        (225, "down-left"),
        (270, "left"),
        (315, "up-left"),
    ]
    anchors = []
    for i, (angle, label) in enumerate(labels):
        frame = int(round(i * frame_count / 8.0)) % frame_count
        anchors.append({"frame": frame, "angle": angle, "label": label})
    data = {
        "version": 1,
        "mode": "frames",
        "frameCount": frame_count,
        "framesDir": "assets/transparent-frames",
        "spritesheet": {
            "url": "assets/spritesheet.png",
            "cols": SHEET_COLS,
            "rows": SHEET_ROWS,
            "frameWidth": FRAME_SIZE,
            "frameHeight": FRAME_SIZE,
        },
        "idle": "assets/idle.png",
        "head": {"cx": 0.50, "cy": 0.28, "rx": 0.20, "ry": 0.16},
        "contactSheet": {"thumb": 96, "labelH": 18, "cols": SHEET_COLS, "rows": SHEET_ROWS},
        "motion": {"maxFramesPerSec": 720},
        "anchors": anchors,
        "notes": (
            "Seed anchors from 8 equal time segments of the source clip. "
            "Recalibrate in renderer/calibrate.html. Angle 0 = up, clockwise."
        ),
    }
    ANCHORS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    if not SOURCE_VIDEO.exists():
        sys.exit(f"missing {SOURCE_VIDEO}")
    raw_paths = extract_raw_frames()
    TRANSPARENT_DIR.mkdir(parents=True, exist_ok=True)
    for old in TRANSPARENT_DIR.glob("*"):
        old.unlink()

    keyed = []
    for i, p in enumerate(raw_paths):
        fr = process_frame(p, FRAME_SIZE)
        keyed.append(fr)
        write_png(TRANSPARENT_DIR / f"{i:03d}.png", fr)
        if i % 30 == 0:
            print(f"keyed {i}/{len(raw_paths)}")

    n = len(keyed)
    print(f"transparent frames: {n}")
    write_png(CONTACT, cv2.cvtColor(make_contact_sheet(keyed), cv2.COLOR_BGR2BGRA))
    # contact sheet is opaque preview; write as BGR png
    cv2.imwrite(str(CONTACT), make_contact_sheet(keyed))
    write_png(SPRITESHEET, make_spritesheet(keyed))
    idle = process_idle()
    write_png(IDLE_OUT, idle)
    write_png(TRAY_OUT, make_tray_icon(idle))
    write_default_anchors(n)
    print("wrote", CONTACT)
    print("wrote", SPRITESHEET)
    print("wrote", IDLE_OUT)
    print("wrote", ANCHORS)
    if n != EXPECTED_FRAMES:
        print(f"warning: expected {EXPECTED_FRAMES} frames, got {n}")


if __name__ == "__main__":
    main()
