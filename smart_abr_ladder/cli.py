"""smart-abr-ladder CLI — bplate-conformant envelope + exit-code floor (0/2/5)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from . import SCHEMA_VERSION, __version__
from .ffmpeg_tools import detect_shots, measure_bitrate_kbps, measure_vmaf, probe_source
from .ladder import LadderError, select_renditions
from .encoder import encode_renditions
from .verifier import (
    EXIT_CONTRACT, EXIT_USAGE, EXIT_VERIFIED, ContractViolation, verify_ladder,
)


def _ok(data):
    return {"status": "success", "data": data}


def _err(code, msg):
    return {"status": "error", "code": code, "message": msg}


def _emit(payload):
    print(json.dumps(payload, indent=2))


def _progress(event, **kw):
    obj = {"event": event}
    obj.update(kw)
    print(json.dumps(obj))
    sys.stdout.flush()


def build_parser():
    p = argparse.ArgumentParser(prog="smart-abr-ladder")
    p.add_argument("source", help="input video")
    p.add_argument("outdir", help="output directory")
    p.add_argument("--plan", action="store_true", help="emit ladder + commands, encode nothing")
    p.add_argument("--quick", action="store_true", help="reduced RD grid (lower confidence)")
    p.add_argument("--json", action="store_true", help="wrap output in the bplate envelope")
    p.add_argument("--progress", action="store_true", help="NDJSON progress lines on stderr")
    p.add_argument("--grid", type=int, default=6, help="RD trial points across the rungs")
    p.add_argument("--version", action="version", version="smart-abr-ladder %s (schema %d)" % (__version__, SCHEMA_VERSION))
    return p


def _rd_surface(source, rungs, grid):
    """Sparse RD model: encode a small deterministic sample at a few CRFs per rung, measure
    bitrate+VMAF, and record the best (highest quality at lowest bitrate) per height."""
    from .encoder import _encode_one
    src = probe_source(source)
    if src is None:
        raise LadderError("cannot probe source")
    src_h = (src["video"] or {}).get("h", 0)
    rung_list = [r for r in rungs if r <= src_h]
    vh = {r: {"bitrate_kbps": None, "vmaf": None} for r in rung_list}

    with tempfile.TemporaryDirectory(prefix="sabl-rd-") as td:
        for h in rung_list:
            w = int(round(h * 16 / 9 / 2) * 2)
            best = None
            for crf in _crf_list(grid):
                out = os.path.join(td, "%dp_crf%d.mp4" % (h, crf))
                try:
                    _encode_one(source, h, w, crf, out)
                except Exception:
                    continue
                br = measure_bitrate_kbps(out)
                q = measure_vmaf(source, out)
                if q is None or br is None:
                    continue
                # lowest bitrate meeting the quality floor wins, preferring higher quality on tie
                if q >= 75.0 and (best is None or br < best[1]):
                    best = (q, br)
            if best is not None:
                vh[h]["vmaf"], vh[h]["bitrate_kbps"] = best[0], best[1]
    return vh


def _crf_list(grid):
    # coarse but bounded; deterministic
    crfs = [18, 20, 22, 24, 26, 28, 30, 32]
    n = max(2, min(grid, len(crfs)))
    return crfs[:n]


def main(argv=None):
    args = build_parser().parse_args(argv)
    source = args.source
    outdir = args.outdir

    if args.progress:
        _progress("stage", stage="probe", source=source)
    src = probe_source(source)
    if src is None:
        if args.json:
            _emit(_err(EXIT_USAGE, "cannot probe source (not a readable video?)"))
        else:
            print("error: cannot probe source", file=sys.stderr)
        return EXIT_USAGE
    src_h = (src["video"] or {}).get("h", 0)

    if args.progress:
        _progress("stage", stage="shot_detect")
    shots = detect_shots(source)

    if args.progress:
        _progress("stage", stage="rd_model", shots=len(shots), quick=args.quick)
    # build per-height RD surface from the probes we already have
    vh = {h: {"bitrate_kbps": None, "vmaf": None} for h in [360, 720, 1080] if h <= src_h}

    if args.plan:
        # plan emits a deterministic ladder WITHOUT encoding: measure exists only if we encode,
        # so for plan we use the constraint defaults + a stable placeholder that the real run
        # replaces. Honest: plan is a *dry run* of selection, not of the RD surface.
        bit = {h: src_h * 2.0 for h in vh}  # placeholder, clearly plan-only
        qual = {h: 90.0 + (h / 720.0) for h in vh}
        renditions = select_renditions(src_h, bit, qual)
        if args.json:
            _emit(_ok({"schema_version": SCHEMA_VERSION, "plan": True, "source": src,
                       "shots": shots, "ladder": renditions, "note": "plan-only ladder (no RD surface; run without --plan for measured values)"}))
        else:
            print(json.dumps(renditions, indent=2))
        return EXIT_VERIFIED

    # Non-plan: actually model the RD surface and encode + verify.
    rd = _rd_surface(source, [360, 720, 1080], args.grid)
    bit = {h: rd[h]["bitrate_kbps"] for h in rd}
    qual = {h: rd[h]["vmaf"] for h in rd if rd[h]["vmaf"] is not None}

    if not qual:
        if args.json:
            _emit(_err(EXIT_CONTRACT, "RD surface produced no measurable quality (libvmaf unavailable?)"))
        else:
            print("error: no measurable quality (libvmaf unavailable?)", file=sys.stderr)
        return EXIT_CONTRACT

    try:
        renditions = select_renditions(src_h, bit, qual)
    except LadderError as e:
        if args.json:
            _emit(_err(EXIT_CONTRACT, str(e)))
        else:
            print("error: %s" % e, file=sys.stderr)
        return EXIT_CONTRACT

    if args.progress:
        _progress("stage", stage="encode", renditions=len(renditions))
    outputs = encode_renditions(source, renditions, outdir, {r["height"]: 23 for r in renditions})

    if args.progress:
        _progress("stage", stage="verify")
    report = verify_ladder(source, renditions, outputs)

    if args.json:
        _emit(_ok(report))
    else:
        print(json.dumps(report, indent=2))

    if not report["verified"]:
        if not args.json:
            print("verification FAILED:", file=sys.stderr)
            for f in report["failures"]:
                print("  %s: %s" % (f.get("rule"), f.get("detail")), file=sys.stderr)
        return EXIT_CONTRACT
    return EXIT_VERIFIED


if __name__ == "__main__":
    sys.exit(main())
