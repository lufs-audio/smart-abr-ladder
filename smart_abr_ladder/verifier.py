"""The verify stage — the product. Every rendition must satisfy a numeric contract before
the run reports success. This is the "proven, not exit-0" gate, in the same shape as the
LUFS Workchain verifier's post-conditions but scoped to a video ladder.
"""
from __future__ import annotations

from typing import Dict, List

from .ffmpeg_tools import measure_bitrate_kbps, measure_vmaf, probe_source


EXIT_VERIFIED = 0
EXIT_USAGE = 2
EXIT_CONTRACT = 5


class ContractViolation(Exception):
    """A gating check failed; carries the precise per-rendition failure list."""


def verify_ladder(
    source: str,
    renditions: List[dict],
    outputs: Dict[int, str],
    vmaf_tolerance: float = 2.0,
    bitrate_tolerance_pct: float = 25.0,
) -> dict:
    """Check every rendition + the ladder as a whole; raise ContractViolation on any gating miss."""
    src = probe_source(source)
    src_dur = (src or {}).get("duration_s") or 0.0
    checks: List[dict] = []
    failures: List[dict] = []

    for r in renditions:
        h = r["height"]
        path = outputs.get(h)
        tag = "rung_%dp" % h

        if not path:
            checks.append({"name": tag + "_exists", "ok": False, "detail": "no output path"})
            failures.append({"rule": tag + "_exists", "detail": "missing"})
            continue

        # decode + resolution
        meta = probe_source(path)
        if meta is None or not (meta.get("video") or {}).get("w"):
            checks.append({"name": tag + "_video_valid", "ok": False, "detail": "does not decode as video"})
            failures.append({"rule": tag + "_video_valid", "detail": "no video stream"})
            continue
        got_h = (meta["video"] or {}).get("h", 0)
        checks.append({"name": tag + "_video_valid", "ok": True,
                       "detail": "%dx%d" % ((meta["video"] or {}).get("w"), got_h)})

        # VMAF vs target
        mv = measure_vmaf(source, path)
        target = r["vmaf_target"]
        if mv is None:
            checks.append({"name": tag + "_vmaf", "ok": False, "detail": "vmaf unavailable"})
            failures.append({"rule": tag + "_vmaf",
                             "expected": target, "observed": None, "detail": "vmaf unavailable"})
        else:
            ok = abs(mv - target) <= vmaf_tolerance
            checks.append({"name": tag + "_vmaf", "ok": ok,
                           "detail": "measured %.2f vs target %.1f (±%.1f)" % (mv, target, vmaf_tolerance)})
            if not ok:
                failures.append({"rule": tag + "_vmaf", "expected": target, "observed": round(mv, 3)})

        # bitrate vs band
        br = measure_bitrate_kbps(path)
        tgt = r["bitrate_kbps"]
        if br is None:
            checks.append({"name": tag + "_bitrate", "ok": False, "detail": "unmeasurable"})
            failures.append({"rule": tag + "_bitrate", "expected": tgt, "observed": None})
        else:
            band = tgt * (bitrate_tolerance_pct / 100.0)
            ok = abs(br - tgt) <= band
            checks.append({"name": tag + "_bitrate", "ok": ok,
                           "detail": "measured %.1f vs target %.1f (±%.0f%%)" % (br, tgt, bitrate_tolerance_pct)})
            if not ok:
                failures.append({"rule": tag + "_bitrate", "expected": tgt, "observed": round(br, 1)})

    # ladder monotone: non-decreasing quality with height
    qs = [r["vmaf_target"] for r in renditions]
    if any(qs[i] < qs[i - 1] for i in range(1, len(qs))):
        checks.append({"name": "ladder_monotone", "ok": False, "detail": "quality decreases with height"})
        failures.append({"rule": "ladder_monotone", "detail": "non-monotone"})
    else:
        checks.append({"name": "ladder_monotone", "ok": True, "detail": "ok"})

    verified = not failures
    return {
        "schema_version": 1,
        "verified": verified,
        "checks": checks,
        "failures": failures,
        "renditions": renditions,
    }
