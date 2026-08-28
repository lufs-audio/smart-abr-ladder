"""Deterministic rendition encoding. One ffmpeg call per rung; bitexact, fixed seed,
reproducible output. Plan-only mode emits the command matrix without executing."""
from __future__ import annotations

import os
import subprocess
from typing import Dict, List, Optional, Tuple


def _encode_one(source: str, height: int, width: int, crf: int, out: str) -> None:
    """Single deterministic x264 encode at (width, height, crf). Raises on non-zero exit."""
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-y",
        "-i", source, "-vf", "scale=%d:%d" % (width, height),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-fflags", "+bitexact", "-flags", "+bitexact", "-an", out,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError("encode failed: %s\n%s" % (" ".join(cmd), proc.stderr[-500:]))


def encode_renditions(
    source: str,
    renditions: List[dict],
    outdir: str,
    crf_by_height: Dict[int, int],
    plan_only: bool = False,
) -> Dict[int, str]:
    """Encode each rendition. Returns {height: output_path}. Bit-exact runs for reproducibility."""
    os.makedirs(outdir, exist_ok=True)
    commands: List[List[str]] = []
    paths: Dict[int, str] = {}
    for r in renditions:
        h = r["height"]
        w = r["width"]
        out = os.path.join(outdir, "%dp_%dkbps.mp4" % (h, int(r["bitrate_kbps"])))
        paths[h] = out
        crf = crf_by_height.get(h, 23)
        cmd = [
            "ffmpeg", "-nostdin", "-hide_banner", "-y",
            "-i", source,
            "-vf", "scale=%d:%d" % (w, h),
            "-c:v", "libx264", "-preset", "medium",
            "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-fflags", "+bitexact", "-flags", "+bitexact",
            "-an",
            out,
        ]
        commands.append(cmd)

    if plan_only:
        return paths

    for r in renditions:
        h = r["height"]
        out = paths[h]
        _encode_one(source, h, r["width"], crf_by_height.get(h, 23), out)
    return paths
