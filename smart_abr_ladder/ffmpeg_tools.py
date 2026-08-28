"""Thin, deterministic wrappers over ffprobe / ffmpeg.

Everything here is stdlib (subprocess + json) against the host's ffmpeg/ffprobe on PATH —
the same light path LUFS Workchain itself relies on. No numpy, no scipy, no venv.

All helpers are None-safe: they return None on any error rather than raising, so a caller
can turn "couldn't measure" into a NAMED failure instead of a fabricated value.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple


def _run(argv, timeout=600):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def probe_source(path: str) -> Optional[dict]:
    """Normalized source model from a single ffprobe call."""
    if not path or not os.path.exists(path):
        return None
    try:
        out = _run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size,format_name:"
                              "stream=codec_type,codec_name,width,height,avg_frame_rate,"
                              "sample_rate,channels,pix_fmt",
            "-of", "json", path,
        ])
        data = json.loads(out.stdout or "{}")
    except Exception:
        return None
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not v:
        return None
    fps_num = fps_den = None
    fr = v.get("avg_frame_rate")
    if isinstance(fr, str) and "/" in fr:
        try:
            fps_num, fps_den = (int(x) for x in fr.split("/"))
        except Exception:
            pass
    return {
        "schema_version": 1,
        "container": fmt.get("format_name", "").split(",")[0],
        "duration_s": float(fmt.get("duration") or 0.0),
        "size_bytes": int(fmt.get("size") or 0),
        "video": {
            "codec": v.get("codec_name"), "w": int(v.get("width") or 0),
            "h": int(v.get("height") or 0), "fps_num": fps_num, "fps_den": fps_den,
            "pix_fmt": v.get("pix_fmt"),
        },
        "audio": {
            "codec": a.get("codec_name"), "channels": int(a.get("channels") or 0),
            "sample_rate": int(a.get("sample_rate") or 0),
        } if a else None,
    }


def detect_shots(path: str) -> List[dict]:
    """Shot list via ffmpeg's scene-detection filter, as an ordered, deterministic list."""
    if not path or not os.path.exists(path):
        return []
    shots: List[dict] = []
    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-i", path,
             "-vf", "select='gt(scene,0.3)',showinfo",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=600,
        )
        blob = proc.stderr or ""
    except Exception:
        return []
    pts = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", blob)]
    if not pts:
        # single shot covering the whole source
        src = probe_source(path)
        dur = (src or {}).get("duration_s") or 0.0
        return [{"index": 0, "start": 0.0, "end": dur}] if dur > 0 else []
    bounds = [0.0] + pts
    if src := (probe_source(path) or {}).get("duration_s"):
        bounds.append(src)
    shots = []
    for i in range(len(bounds) - 1):
        shots.append({"index": i, "start": bounds[i], "end": bounds[i + 1]})
    return shots


def measure_vmaf(reference: str, distorted: str, model: str = "version=vmaf_v0.6.1") -> Optional[float]:
    """Mean VMAF of `distorted` scored against `reference`. None on any failure — never fabricate."""
    if not reference or not os.path.exists(reference) or not distorted or not os.path.exists(distorted):
        return None

    def run(fspec):
        return _run(["ffmpeg", "-nostdin", "-hide_banner",
                     "-i", reference, "-i", distorted, "-lavfi", fspec, "-f", "null", "-"])

    try:
        proc = run("libvmaf=%s:log_fmt=json" % model)
        blob = (proc.stdout or "") + (proc.stderr or "")
        try:
            data = json.loads((proc.stdout or "").strip() or "{}")
        except Exception:
            data = None
        if data is not None:
            mean = (data.get("pooled_metrics") or {}).get("vmaf") or {}
            if mean.get("mean") is not None:
                return float(mean["mean"])
        m = re.search(r'"VMAF score"\s*:\s*([0-9.]+)|VMAF score:\s*([0-9.]+)', blob)
        if m:
            return float(m.group(1) or m.group(2))
    except Exception:
        pass
    try:
        proc = run("libvmaf")
        m = re.search(r"VMAF score:\s*([0-9.]+)", (proc.stdout or "") + (proc.stderr or ""))
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return None


def measure_bitrate_kbps(path: str) -> Optional[float]:
    try:
        out = _run(["ffprobe", "-v", "error",
                    "-show_entries", "format=bit_rate,duration,size", "-of", "json", path])
        fmt = (json.loads(out.stdout or "{}").get("format") or {})
        if fmt.get("bit_rate"):
            return float(fmt["bit_rate"]) / 1000.0
        dur, size = float(fmt.get("duration") or 0.0), float(fmt.get("size") or 0.0)
        if dur > 0 and size > 0:
            return size * 8.0 / dur / 1000.0
    except Exception:
        pass
    return None
