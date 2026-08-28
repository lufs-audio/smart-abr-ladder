# AGENTS.md — smart-abr-ladder

Machine-facing operating contract for this repository. Authoritative for agents; a human
README should not contradict it.

## What this is

Per-title / per-shot adaptive bitrate ladder generation, **contract-verified**. The verify
stage is the product: a rendition that decodes but misses its VMAF target or bitrate band
fails the run (exit 5) — "proven correct, not merely exited 0."

## Prime directive

**Never report a ladder as correct unless the verify stage checked it.** A green encode is
not evidence. The only success signal is `verify_ladder(...)` returning `verified: true`.

## Layout

- `smart_abr_ladder/ffmpeg_tools.py` — `ffprobe`/`ffmpeg` wrappers (probe, shots, VMAF, bitrate).
  All `None`-safe; never fabricate a measured value.
- `smart_abr_ladder/ladder.py` — deterministic rendition selection (monotone, prune dominated,
  spacing/floor/ceiling). Raises `LadderError` when infeasible.
- `smart_abr_ladder/encoder.py` — `+bitexact` deterministic x264 encodes.
- `smart_abr_ladder/verifier.py` — the gate: `verify_ladder` + `ContractViolation`, exit codes.
- `smart_abr_ladder/cli.py` — argparse CLI, bplate envelope, exit-code floor 0/2/5, NDJSON progress.
- `tests/` — red/green unit tests (selection + verifier), no external media required.

## Contracts

- **Exit codes**: `0` verified, `2` usage, `5` contract violation. Never exit `1` for a usage
  or verification outcome.
- **JSON envelope** (bplate): `{"status":"success","data":…}` / `{"status":"error","code":N,"message":…}`.
- **Determinism**: encodes are `+bitexact` + fixed CRF; no wall-clock timestamps in output.
- **Honest failure**: a missing `libvmaf` is `vmaf unavailable`, not a fallback score.

## Prove the test can fail

Every added check must have a corresponding test that first fails (broken case) then passes.
`tests/test_ladder.py` carries the selection + verifier red/green pairs. A check nobody has
seen fail is decoration.

## Boundaries

- This repo depends on the LUFS Workchain verifier's *video/manifest primitives*
  (`video_valid`, `video_vmaf_within`, …) conceptually — it re-implements the small video
  verify surface here until that upstream extension is consumed directly. Do not drift the
  two out of sync.
- No new runtime dependency: stdlib + ffmpeg/ffprobe only (the light path).

## Related

- KB suite `verifiable-media-stack` (motivation + landscape).
- `lufs-audio/llhls-certify`, `lufs-audio/serverless-transcode` (siblings).
- `lufs-audio/bplate` exit-code/envelope floor.
