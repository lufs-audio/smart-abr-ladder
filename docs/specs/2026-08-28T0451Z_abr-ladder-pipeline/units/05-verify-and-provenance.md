# Unit 05 — verify-and-provenance

## Objective

Gate every rendition and the ladder-as-a-whole against a machine-checked numeric
contract, and emit a provenance record binding each output to source hash + recipe hash.
This is the "proven, not exit-0" stage.

## Context

- Consumes Unit 04's run manifest + outputs (see
  `docs/specs/2026-08-28T0451Z_abr-ladder-pipeline/units/04-encode.md`).
- New component `components/verify/`.
- This is where the Workchain verifier is *extended* from audio to video. The assertion
  primitives (`video_valid`, the numeric post-condition, decode check) are listed in
  phase `SPEC.md` ecosystem references as the shared `workchain` change; this unit
  *declares and consumes* them, and fails honestly (exit 5) if a required primitive is
  absent rather than fabricating one.

## Acceptance criteria

- [ ] For each output rendition: exists, non-empty, `video_valid` (decodes, non-zero
      frames, expected resolution), and satisfies its numeric contract:
      - measured VMAF >= `target_vmaf - tolerance`;
      - measured bitrate within `target_bitrate_kbps ± tolerance`.
- [ ] Ladder-level contract: renditions monotone in quality; no redundant rung (re-check
      at encode result, not just at selection).
- [ ] Cross-output duration consistency: all renditions' durations match the source
      within a small frame tolerance.
- [ ] Provenance record written: content-addressed — each output's SHA-256, the source
      SHA-256, and a recipe hash over the encode command + encoder/library versions.
- [ ] Any contract violation → step fails with exit 5 and a precise per-check failure
      list (which rung, which metric, measured vs. target). Never a silent green.
- [ ] Idempotent: re-running verify on an already-verified directory is a no-op success.

## Interface contract

Emits (consumed by Unit 06's JSON output and by anything downstream):

```json
{
  "schema_version": 1,
  "verified": true,
  "checks": [
    { "name": "rung_1080p_vmaf", "ok": true, "measured": 95.4, "target": 95.0, "tol": 1.0, "gating": true },
    { "name": "rung_1080p_bitrate", "ok": true, "measured": 4950, "target": 5000, "tol_pct": 15, "gating": true },
    { "name": "ladder_monotone", "ok": true, "gating": true }
  ],
  "provenance": {
    "source_sha256": "<...>",
    "recipe_hash": "<...>",
    "outputs": [ { "path": "out/1080p_5000.mp4", "sha256": "<...>" } ]
  }
}
```

`verified: false` + a non-empty failed-check list is the honest-failure contract.

## Boundaries — do NOT touch

- `components/encode/` (Unit 04) — verify reads, never mutates, the outputs.
- `lib/workchain_verify.py` extension: this unit *consumes* the `video_valid` primitive;
  the primitive itself is authored as the shared workchain change (phase `SPEC.md`
  ecosystem references), not re-implemented inline here.

## Output

- `components/verify/` with `step.yaml`, `run.sh`, `README.md`.
- `tests/` covering: pass on a good ladder, fail (exit 5) on each of (bad VMAF, bad
  bitrate, non-monotone, missing file, mismatched duration), and idempotent re-run.

## Verification

- `python3 -m pytest tests/ -k verify` green.
- Construct a deliberately-bad ladder (e.g. lower a rung's bitrate below target) and
  assert verify returns exit 5 with that rung named in the failure list.
