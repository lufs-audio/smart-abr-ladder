# Unit 02 — rd-model

## Objective

Run a sparse grid of trial encodes and VMAF measurements, then fit a rate-distortion
(R-D) surface that Unit 03 can query to select renditions.

## Context

- Consumes Unit 01's source model + shot list (see
  `docs/specs/2026-08-28T0451Z_abr-ladder-pipeline/units/01-probe-and-shard.md`).
- New component `components/rd-model/` (schema + run.sh + README).
- Uses FFmpeg (encode) + libvmaf (quality). libvmaf invoked via `ffmpeg`'s `libvmaf`
  filter; do **not** reimplement metric math.
- The R-D surface is the *only* compute-heavy stage; design it to be constrained and
  configurable (grid size) so `--plan`/`--quick` can shrink it.

## Acceptance criteria

- [ ] Given a source model, generate a trial set: a sparse grid of
      `(resolution, CRF)` points (default ~a small handful per resolution rung, e.g.
      {360,720,1080} × {24,28,32,…} capped), configurable via count.
- [ ] Each trial encodes a deterministic sample (fixed segment + fixed seed, no
      wall-clock timestamps) and measures bitrate + VMAF.
- [ ] Emit per-trial rows: `{resolution, width, height, crf, bitrate_kbps, vmaf_mean,
      vmaf_low, target_duration_s, encode_ms, model_versions}`.
- [ ] Fit an R-D surface object (monotone bitrate-vs-quality per resolution, interpolated)
      and serialize it; the fit is deterministic (same inputs → same surface).
- [ ] `--quick` mode reduces the grid and reports it as a *reduced-confidence* result
      (a flag in output), never silently as if full.
- [ ] Failure mode: if a trial encode exits non-zero or VMAF is unavailable, fail the
      component (do not fabricate a metric).

## Interface contract

Output JSON:

```json
{
  "schema_version": 1,
  "grid": { "resolutions": [360, 720, 1080], "crfs": [24, 28, 32] },
  "trials": [
    { "resolution": 360, "width": 640, "height": 360, "crf": 28,
      "bitrate_kbps": 812.4, "vmaf_mean": 91.2, "vmaf_low": 82.0, "encode_ms": 4120 }
  ],
  "surface": { "model": "pchip", "points": "...deterministic...", "quick": false },
  "model_versions": { "ffmpeg": "7.1", "libvmaf": "3.0.0", "encoder": "libx264" }
}
```

`schema_version`, field names, and `model_versions` are load-bearing for Unit 03 and
Unit 05 (provenance).

## Boundaries — do NOT touch

- `components/probe/`, `components/shot-detect/` (Unit 01), `components/ladder-select/`
  (Unit 03), `components/encode/` (Unit 04), `components/verify/` (Unit 05).
- Do not write final renditions here; trials are discarded scratch encodes in a temp dir.
- Do not modify `lib/workchain_verify.py`.

## Output

- `components/rd-model/` with `step.yaml`, `run.sh`, `README.md`.
- `tests/` covering: grid determinism, quick-mode flag, and honest failure on a bad
  trial encode (mocked/子process failure).

## Verification

- `python3 -m pytest tests/ -k rd_model` green.
- Re-run the component twice on the fixture; `diff` — byte-identical surface JSON.
- A test asserts VMAF unavailable → non-zero exit, no metric emitted.
