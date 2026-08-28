# Unit 06 — cli-envelope

## Objective

Expose the full chain behind a conformant CLI: `--json`, `--plan` dry-run, the bplate
JSON envelope, the exit-code floor (0/2/5), and NDJSON progress for agent-driven runs.

## Context

- Wraps the chain (Units 01–05). See phase `SPEC.md` and
  `docs/specs/2026-08-28T0451Z_abr-ladder-pipeline/units/*`.
- Conformance targets (see phase `SPEC.md` ecosystem references): `lufs-audio/bplate`
  exit-code floor + JSON envelope `{"status":"success","data":…}` /
  `{"status":"error","code":N,"message":…}`.
- This is the human/agent facing surface; it owns no media logic.

## Acceptance criteria

- [ ] `smart-abr-ladder <source> <outdir>` runs the chain end-to-end.
- [ ] `--json` wraps all output in the bplate envelope; `data` carries the verify
      result + provenance.
- [ ] `--plan` emits the selected ladder + command matrix as JSON and exits 0 *without*
      encoding or verifying (dry-run).
- [ ] `--quick` passes through to the RD model's reduced grid (Unit 02) and is reported.
- [ ] Exit codes: `0` success (verified), `2` usage error (bad args/unknown flag),
      `5` contract violation (verify failed). No exit-`1` usage.
- [ ] NDJSON progress lines (`{"event":"stage","stage":"encode","rendition":720,…}`) on
      stdout when `--progress` is set, so an agent can observe.
- [ ] `--version` prints `schema_version` + pinned FFmpeg/libvmaf expectation.

## Interface contract

CLI contract (stable):

```
smart-abr-ladder SOURCE OUTDIR [--plan] [--quick] [--json] [--progress] [--grid N] [--profile P]
```

Exit codes: `0` verified, `2` usage, `5` contract. JSON envelope exactly as above.

## Boundaries — do NOT touch

- Component internals (`components/*/run.sh`, `step.yaml`) — other units own them.
- Do not bypass the verifier: `--json` success may only be reported after Unit 05's
  `verified: true`.

## Output

- `smart_abr_ladder/cli.py` (argparse or click; no new heavyweight deps), entrypoint
  `smart-abr-ladder`.
- `tests/` covering: end-to-end on fixture, `--plan` no-encode, exit-code matrix
  (0/2/5), JSON envelope shape, NDJSON line shape.

## Verification

- `python3 -m pytest tests/ -k cli` green.
- `smart-abr-ladder --plan fixtures/clip.mp4 out/ --json` exits 0 and emits a valid
  ladder with no `.mp4` written.
- A forced-contract-violation fixture run exits 5 with `status:error` and `code:5`.
