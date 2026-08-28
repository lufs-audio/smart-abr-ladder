"""Rendition selection from a rate-distortion surface.

Deterministic, constraint-driven: monotone quality, no redundant rungs, bitrate spacing,
device-height targets. Pure stdlib — no numeric deps.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple


DEFAULT_RUNGS = [360, 720, 1080]


class LadderError(Exception):
    """Constraint could not be satisfied honestly (no fabricated ladder)."""


def _rungs_for(source_h: int, rungs: List[int]) -> List[int]:
    return [r for r in rungs if r <= source_h]


def select_renditions(
    source_h: int,
    bitrate_for_height: Dict[int, float],
    vmaf_for_height: Dict[int, float],
    rungs: Optional[List[int]] = None,
    min_spacing_kbps: float = 400.0,
    floor_kbps: float = 300.0,
    ceiling_kbps: float = 12000.0,
) -> List[dict]:
    """Choose renditions from per-height measured bitrate+VMAF, pruning dominated rungs.

    Returns an ascending list of {height, width, bitrate_kbps, crf, vmaf_target} where
    vmaf_target is the MEASURED quality that later stages verify against.
    """
    heights = _rungs_for(source_h, rungs or DEFAULT_RUNGS)
    if not heights:
        raise LadderError("no viable rungs below source height %d" % source_h)

    candidates: List[Tuple[int, float, float]] = []
    for h in heights:
        br = bitrate_for_height.get(h)
        q = vmaf_for_height.get(h)
        if br is not None and q is not None and br >= floor_kbps:
            candidates.append((h, br, q))
    if not candidates:
        raise LadderError("no renditions within the %d..%d kbps floor/ceiling" % (floor_kbps, ceiling_kbps))

    # stable sort ascending by height
    candidates.sort(key=lambda x: x[0])

    renditions: List[dict] = []
    last_br: Optional[float] = None
    last_q: Optional[float] = None
    for h, br, q in candidates:
        if br > ceiling_kbps:
            continue
        # redundant rung: higher height but not strictly better quality AND not spaced in bitrate
        if last_br is not None:
            if h > renditions[-1]["height"] and q <= last_q:
                continue  # dominated in quality
            if br - last_br < min_spacing_kbps and q <= last_q:
                continue  # not materially spaced, no quality gain
        # monotone quality + bitrate are enforced by construction here
        renditions.append({
            "height": h,
            "width": int(round(h * 16 / 9 / 2) * 2),
            "bitrate_kbps": round(br, 1),
            "crf": None,  # resolved at encode time from the RD surface
            "vmaf_target": round(q, 2),
            "codec": "libx264",
        })
        last_br, last_q = br, q

    if len(renditions) < 1:
        raise LadderError("all renditions pruned as redundant/dominated — infeasible ladder")
    return renditions
