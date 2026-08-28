# Unit 04 — encode

## Objective

Execute the selected ladder deterministically: produce one output file per rendition
(plus the per-shot schedule when present), with reproducible output and no wall-clock
dependence.

## Context

- Consumes Unit 03's ladder spec (see
  `docs/specs/2026-08-28T0451Z_abr-ladder-pipeline/units/03-ladder-select.md`).
- New component `components/encode/`.
- FFmpeg subprocess per rendition. Output is an intermediate representation suitable for
  the `verify` stage; final CMAF/segment packaging is out of scope (see phase `SPEC.md`).

## Acceptance criteria

- [ ] One output file per rendition, named deterministically (content-derived, e.g.
      `<height>p_<bitrate>.mp4`), written to a per-run output dir.
- [ ] Deterministic encode: inject `-fflags +bitexact` and a fixed `-g`/keyframe cadence
      where the encoder allows; record `-version` and encoder/library versions into the
      run's recipe (consumed by Unit 05).
- [ ] Outputs carry no wall-clock timestamps that would break byte-reproducibility
      (assert by encoding twice and comparing, tolerant only of documented frame-accuracy
      metadata).
- [ ] `--dry` / `--plan` path: emit the *commands* (and the ladder) without executing —
      this is the CLI-facing piece but lives here so `encode` owns its own plan.
- [ ] Per-shot schedule (when Unit 03 emits one) is applied via per-shot encode and
      concat (deterministic), or flagged honestly as unapplied if the codec/path can't
      honor it.
- [ ] Any rendition that fails to encode fails the component (no partial "success").

## Interface contract

Produces (for Unit 05) a run directory manifest:

```json
{
  "schema_version": 1,
  "recipe": { "source_sha256": "<...>", "cmd_matrix": { "ffmpeg": "7.1", "libx264": "..." }, "flags": ["+bitexact"] },
  "outputs": [
    { "height": 360,  "path": "out/360p_800.mp4",  "target_vmaf": 90.0, "target_bitrate_kbps": 800 },
    { "height": 720,  "path": "out/720p_2500.mp4", "target_vmaf": 93.0, "target_bitrate_kbps": 2500 },
    { "height": 1080, "path": "out/1080p_5000.mp4","target_vmaf": 95.0, "target_bitrate_kbps": 5000 }
  ]
}
```

`recipe` + per-output `target_*` are what Unit 05 verifies and hashes.

## Boundaries — do NOT touch

- `components/ladder-select/` (Unit 03), `components/verify/` (Unit 05),
  `components/rd-model/` (Unit 02).
- Final packaging/manifest *verification* is Unit 05's job; here we only produce the
  rendition files + this run manifest.

## Output

- `components/encode/` with `step.yaml`, `run.sh`, `README.md`.
- `tests/` covering: deterministic double-encode, plan-only emission, per-shot
  application-or-honest-flag, and failure propagation.

## Verification

- `python3 -m pytest tests/ -k encode` green.
- Encode the fixture twice; assert the two output sets are bit-identical (or, where a
  codec forbids it, assert the documented frame-accuracy deviation is the *only* diff).
- `--plan` produces the command matrix without writing any `.mp4`.
