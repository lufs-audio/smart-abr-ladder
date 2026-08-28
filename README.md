# smart-abr-ladder

Per-title / per-shot adaptive bitrate ladder generation, **contract-verified**. The verify
stage is the product: every rendition must decode, hit its target VMAF within tolerance,
hold its bitrate band, and leave the ladder monotone with no redundant rung — or the run
fails (exit 5) instead of reporting a silent green.

This is the Workchain verifier's "proven, not exit-0" doctrine pointed at *video* instead of
audio. See the KB suite `verifiable-media-stack` for the motivation and landscape.

## Install & run

```bash
# stdlib + ffmpeg/ffprobe only — no venv required to run
pip install -e ".[dev]"   # pytest/ruff for development
python3 -m smart_abr_ladder.cli INPUT.mp4 OUTDIR --json
python3 -m smart_abr_ladder.cli INPUT.mp4 OUTDIR --plan --json   # dry-run, encodes nothing
```

Runtime requirements: `ffmpeg` + `ffprobe` on PATH, with `libvmaf` and `libx264` compiled in
for the verify stage. A missing `libvmaf` produces an honest `vmaf unavailable` contract
failure, never a fabricated score.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | verified — ladder passed its contract |
| 2 | usage (bad input, unreadable source) |
| 5 | contract violation — a rendition or the ladder failed its numeric check |

## Pipeline

```
probe → shot-detect → rd-model → ladder-select → encode → verify
```

- **probe** — normalized source model (`ffprobe`).
- **shot-detect** — scene-cut boundaries (`ffmpeg` `select=gt(scene,0.3),showinfo`).
- **rd-model** — sparse CRF grid per rung; measures bitrate + VMAF; picks the lowest-bitrate
  variant meeting a quality floor.
- **ladder-select** — monotone quality, no dominated rungs, bitrate spacing/floor/ceiling.
- **encode** — one deterministic `libx264` pass per rung (`+bitexact`, reproducible).
- **verify** — decode, VMAF-vs-target, bitrate-band, ladder monotonicity; fails closed.

## Tests

```bash
python3 -m pytest
```

`tests/test_ladder.py` proves selection (monotone, redundant-rung pruning, infeasible-raise)
and the verifier (rejects low VMAF and non-monotone ladders) — red/green, no external media
required for the unit layer.
