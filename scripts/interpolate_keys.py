#!/usr/bin/env python3
"""Motion-compensated in-betweens so adjacent frames actually connect."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import imageio_ffmpeg
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

KEYS_DIR = ROOT / "assets/source/keys"
STEPS_PER_SEG = 24
KEY_COUNT = 16
FRAME_COUNT = KEY_COUNT * STEPS_PER_SEG  # 384
SHEET_COLS = 24
SHEET_ROWS = 16
IN_FPS = 8
OUT_FPS = IN_FPS * STEPS_PER_SEG  # 192


def load_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"failed to read {path}")
    return cv2.resize(img, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)


def run_minterpolate(keys: list[np.ndarray], out_dir: Path) -> list[Path]:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        for i, img in enumerate(keys, start=1):
            cv2.imwrite(str(src / f"{i:04d}.png"), img)
        cv2.imwrite(str(src / f"{len(keys) + 1:04d}.png"), keys[0])

        vf = (
            f"fps={IN_FPS},"
            f"format=yuv444p,"
            f"minterpolate=fps={OUT_FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            str(IN_FPS),
            "-i",
            str(src / "%04d.png"),
            "-vf",
            vf,
            "-t",
            str(KEY_COUNT / IN_FPS),
            str(dst / "%04d.png"),
        ]
        print("ffmpeg minterpolate...")
        subprocess.check_call(cmd)
        frames = sorted(dst.glob("*.png"))
        if len(frames) < KEY_COUNT * 8:
            raise RuntimeError(f"minterpolate produced {len(frames)} frames")
        out_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        for i, src_f in enumerate(frames):
            dest = out_dir / f"{i:03d}.png"
            shutil.copy(src_f, dest)
            copied.append(dest)
        print(f"minterpolate frames: {len(copied)}")
        return copied


def write_anchors(frame_count: int, cols: int, rows: int) -> None:
    anchors = []
    labels = {
        0: "up",
        2: "up-right",
        4: "right",
        6: "down-right",
        8: "down",
        10: "down-left",
        12: "left",
        14: "up-left",
    }
    for i in range(KEY_COUNT):
        anchors.append(
            {
                "frame": int(round(i * frame_count / KEY_COUNT)) % frame_count,
                "angle": i * 22.5,
                "label": labels.get(i, f"{i * 22.5:g}"),
            }
        )
    data = {
        "version": 3,
        "frameCount": frame_count,
        "framesDir": "assets/transparent-frames",
        "spritesheet": {
            "url": "assets/spritesheet.png",
            "cols": cols,
            "rows": rows,
            "frameWidth": FRAME_SIZE,
            "frameHeight": FRAME_SIZE,
        },
        "idle": "assets/idle.png",
        "head": {"cx": 0.50, "cy": 0.28, "rx": 0.18, "ry": 0.14},
        "contactSheet": {"thumb": 64, "labelH": 18, "cols": cols, "rows": rows},
        "motion": {"follow": 16, "idleFollow": 6, "maxFramesPerSec": 60},
        "anchors": anchors,
        "notes": "16 keys with ffmpeg MCI in-betweens. Play adjacent frames; do not skip.",
    }
    ANCHORS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_contact(frames: list[np.ndarray], cols: int, rows: int) -> None:
    thumb, label_h = 64, 18
    cols, rows = cols, rows
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
            (x + 2, y + thumb + 13),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(CONTACT), sheet)


def make_sheet(frames: list[np.ndarray], cols: int, rows: int) -> None:
    w = h = FRAME_SIZE
    sheet = np.zeros((rows * h, cols * w, 4), dtype=np.uint8)
    for i, fr in enumerate(frames):
        r, c = divmod(i, cols)
        if r >= rows:
            break
        sheet[r * h : r * h + h, c * w : c * w + w] = fr
    write_png(SPRITESHEET, sheet)


def main() -> None:
    paths = sorted(KEYS_DIR.glob("k*.png"))
    if len(paths) != KEY_COUNT:
        sys.exit(f"expected {KEY_COUNT} keys, got {len(paths)}")
    keys = [load_bgr(p) for p in paths]
    raw_dir = ROOT / "assets/source/interpolated-raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_files = run_minterpolate(keys, raw_dir)

    TRANSPARENT_DIR.mkdir(parents=True, exist_ok=True)
    for old in TRANSPARENT_DIR.glob("*"):
        old.unlink()
    keyed = []
    for i, path in enumerate(raw_files):
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        bgra = chroma_key_bgra(bgr)
        keyed.append(bgra)
        write_png(TRANSPARENT_DIR / f"{i:03d}.png", bgra)
        if i % 48 == 0:
            print(f"keyed {i}/{len(raw_files)}")

    n = len(keyed)
    cols = 24
    rows = int(np.ceil(n / cols))
    make_contact(keyed, cols, rows)
    make_sheet(keyed, cols, rows)
    idle = process_idle()
    write_png(IDLE_OUT, idle)
    write_png(ROOT / "assets/tray-icon.png", make_tray_icon(idle))
    write_anchors(n, cols, rows)
    print(f"wrote {n} continuous frames")


if __name__ == "__main__":
    main()
