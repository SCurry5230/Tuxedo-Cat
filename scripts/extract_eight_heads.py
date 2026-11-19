#!/usr/bin/env python3
"""32 full-body directional stills. Nearest pose only, no dissolve."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from process_assets import FRAME_SIZE, chroma_key_bgra, process_idle, write_png  # noqa: E402

GEN = Path("/Users/SEI/.cursor/projects/Users-SEI-Desktop-green-screen-cat/assets")
KEYS = ROOT / "assets/source/keys"
REAL = ROOT / "assets/source/real-keys"
OUT = ROOT / "assets/poses"
POSE_COUNT = 32

# Clockwise from up, 11.25° apart. Cardinals use the original 8 stills.
SOURCES = [
    REAL / "k00-up.png",
    GEN / "pose-011.png",
    KEYS / "k01-022.png",
    GEN / "pose-033.png",
    REAL / "k03-up-right.png",
    GEN / "pose-056.png",
    KEYS / "k03-067.png",
    GEN / "pose-078.png",
    REAL / "k06-right.png",
    GEN / "pose-101.png",
    KEYS / "k05-112.png",
    GEN / "pose-123.png",
    REAL / "k09-down-right.png",
    GEN / "pose-146.png",
    KEYS / "k07-157.png",
    GEN / "pose-168.png",
    REAL / "k12-down.png",
    GEN / "pose-191.png",
    KEYS / "k09-202.png",
    GEN / "pose-213.png",
    REAL / "k15-down-left.png",
    GEN / "pose-236.png",
    KEYS / "k11-247.png",
    GEN / "pose-258.png",
    REAL / "k18-left.png",
    GEN / "pose-281.png",
    KEYS / "k13-292.png",
    GEN / "pose-303.png",
    REAL / "k21-up-left.png",
    GEN / "pose-326.png",
    KEYS / "k15-337.png",
    GEN / "pose-348.png",
]


def load_pose(path: Path):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"missing {path}")
    img = cv2.resize(img, (FRAME_SIZE, FRAME_SIZE), interpolation=cv2.INTER_AREA)
    return chroma_key_bgra(img)


def main() -> None:
    if len(SOURCES) != POSE_COUNT:
        raise RuntimeError("expected 32 sources")
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    poses = []
    for i, src in enumerate(SOURCES):
        fr = load_pose(src)
        rel = f"assets/poses/{i:02d}.png"
        write_png(ROOT / rel, fr)
        poses.append(rel)

    idle = process_idle()
    write_png(ROOT / "assets/idle.png", idle)

    data = {
        "version": 10,
        "mode": "poses",
        "idle": "assets/idle.png",
        "poses": poses,
        "poseCount": POSE_COUNT,
        "head": {"cx": 0.50, "cy": 0.28, "rx": 0.20, "ry": 0.16},
        "notes": "32 full-body stills, nearest pose only, no dissolve.",
    }
    (ROOT / "assets/angle-anchors.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote {POSE_COUNT} full-body poses")


if __name__ == "__main__":
    main()
