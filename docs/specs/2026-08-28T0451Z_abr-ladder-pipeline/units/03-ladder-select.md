# Unit 03 — ladder-select

## Objective

Select the concrete renditions (resolution × bitrate × codec profile) that form the
ladder, from Unit 02's R-D surface, subject to explicit constraints, plus an optional
per-shot bit-allocation pass.

## Context

- Consumes Unit 02's surface (see
  `docs/specs/2026-08-28T0451Z_abr-ladder-pipeline/units/02-rd-model.md`) and Unit 01's
  shots for the per-shot pass.
- New component `components/ladder-select/`.
- The bitrate/rendition guidance targets Apple HLS authoring (see phase `SPEC.md`
  ecosystem references — Apple HLS Authoring Specification for Apple Devices).

## Acceptance criteria

- [ ] Choose a rendition set from the R-D surface such that, across rungs:
      - **monotone quality**: VMAF-lower-bound is non-decreasing as bitrate/resolution rises;
      - **no redundant rungs**: a rung whose lower-resolution neighbor both <= bitrate and
        >= quality is dropped;
      - **bitrate spacing**: consecutive rungs are separated by a configurable minimum
        step, within configurable floor/ceiling;
      - **device targets**: rungs map onto a standard resolution set ({360,480,720,1080}
        or height-only equivalents) unless overridden.
- [ ] Emit renditions as `[{height,width,bitrate_kbps,crf,vmaf_target,codec}]`, ordered
      ascending, each carrying the *target VMAF* it must later satisfy (consumed by
      Units 04 and 05).
- [ ] Per-shot pass (optional flag): given shots, allocate relative bitrate across shots
      within a rendition, output a per-shot `{shot_index, crf_delta, bitrate_kbps}`
      schedule; constrained so total is within the rendition's bitrate band.
- [ ] Deterministic given identical surface + config (fixed tie-breaking, stable sort).
- [ ] Constraint violation (e.g. only one viable rung, or infeasible bandwidth range)
      is an explicit error, not a silently-degraded ladder.

## Interface contract

Output JSON — the "ladder spec" Units 04/05 consume:

```json
{
  "schema_version": 1,
  "ladder": [
    { "height": 360,  "width": 640,  "bitrate_kbps": 800,  "crf": 28, "vmaf_target": 90.0, "codec": "libx264" },
    { "height": 720,  "width": 1280, "bitrate_kbps": 2500, "crf": 26, "vmaf_target": 93.0, "codec": "libx264" },
    { "height": 1080, "width": 1920, "bitrate_kbps": 5000, "crf": 24, "vmaf_target": 95.0, "codec": "libx264" }
  ],
  "per_shot": null,
  "constraints": { "target_vmaf_tolerance": 1.0, "bitrate_tolerance_pct": 15.0 }
}
```

`vmaf_target` + `constraints` are the numeric contract Unit 05 verifies against.

## Boundaries — do NOT touch

- `components/rd-model/` (Unit 02), `components/encode/` (Unit 04),
  `components/verify/` (Unit 05), `components/probe/` (Unit 01).
- This unit selects; it does not encode or verify.

## Output

- `components/ladder-select/` with `step.yaml`, `run.sh`, `README.md`.
- `tests/` covering monotonicity, redundant-rung pruning, spacing/floor-ceiling,
  determinism, and constraint-violation error.

## Verification

- `python3 -m pytest tests/ -k ladder_select` green.
- A test feeds a hand-built R-D surface where a redundant rung exists, and asserts it is
  pruned.
- A test asserts infeasible constraints produce a non-zero exit with a named error.
