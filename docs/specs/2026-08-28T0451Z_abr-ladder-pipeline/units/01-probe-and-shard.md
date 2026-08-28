# Unit 01 — probe-and-shard

## Objective

Produce a normalized, JSON-serializable source model and shot/segment list from a single
input video, using FFmpeg only (no decode-to-disk of full frames).

## Context

- New chain component at `components/probe/` and `components/shot-detect/` (or one
  combined `components/source-model/` — your call, keep it a single owned unit).
- Workchain engine conventions: `engine/workchain-engine.sh` `process_step` calls each
  component's `run.sh`; `lib/workchain_yaml.py` parses `step.yaml`.
- The downstream seams: Unit 02 (`rd-model`) consumes this unit's source model and shot
  list; Units 04/05 consume the same model for encode + verify. See this phase's
  `SPEC.md` for the chain (probe → shot-detect → rd-model → ladder-select → encode →
  verify) and ecosystem references.

## Acceptance criteria

- [ ] `probe` emits a source model with, at minimum: container, codec (video + audio, if
      present), pixel format/color info, width×height, frame rate (num/den), duration
      (s + frame count), SAR/DAR, and audio channel/sample-rate when an audio stream exists.
- [ ] `shot-detect` emits an ordered list of shots: each `{index,start_frame,end_frame,
      start_time_s,end_time_s}` where times derive from the frame rate (deterministic,
      not wall-clock).
- [ ] Per-shot complexity is computed: spatial (SI) and temporal (TI) via FFmpeg's
      `signalstats` filter (or equivalent), stored per shot as floats.
- [ ] Output is strict JSON on stdout when `--json` is set; human-readable otherwise.
      Includes a `schema_version`.
- [ ] Deterministic: two runs on the same file produce byte-identical JSON.
- [ ] A single-segment source (no scene cuts) still yields exactly one shot, covering
      the whole file.

## Interface contract

Emitted JSON schema (the single source of truth for Units 02/04/05):

```json
{
  "schema_version": 1,
  "source": {
    "sha256": "<content hash>",
    "container": "mp4",
    "duration_s": 120.5,
    "frames": 3615,
    "video": { "codec": "h264", "w": 1920, "h": 1080, "fps_num": 30000, "fps_den": 1001,
               "pix_fmt": "yuv420p", "sar": "1:1", "dar": "16:9" },
    "audio": { "codec": "aac", "channels": 2, "sample_rate": 48000 } | null
  },
  "shots": [
    { "index": 0, "start_frame": 0, "end_frame": 500, "start_time_s": 0.0, "end_time_s": 16.68,
      "si": 24.1, "ti": 11.3 }
  ]
}
```

Field names above are stable. Add fields, never rename existing ones within a
`schema_version`.

## Boundaries — do NOT touch

- `components/rd-model/`, `components/ladder-select/`, `components/encode/`,
  `components/verify/` — other units own these.
- `lib/workchain_verify.py` and `lib/workchain_yaml.py` — Workchain-owned; read, don't
  modify (video-asset primitives are a *separate* workchain change, see the phase
  `SPEC.md` ecosystem references, not this unit).

## Output

- `components/probe/` (+ `components/shot-detect/` if split) each with `step.yaml`,
  `run.sh`, `README.md`.
- Fixtures: a script under `tests/fixtures/` that synthesizes a small deterministic test
  clip (e.g. `testsrc2`/`sine` via FFmpeg) rather than committing binary media.
- `pytest` tests asserting the acceptance criteria above.

## Verification

- `python3 -m pytest tests/ -k probe` green.
- Run the probe+shot-detect on the fixture twice; `diff` the JSON — byte-identical.
- `schema_version`, `shots[].start_time_s/end_time_s` arithmetic checked against known
  frame counts in a test.
