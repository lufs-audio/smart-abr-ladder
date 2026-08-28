# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-08-28

### Added

- Initial implementation of the five-stage pipeline: `probe → shot-detect → rd-model →
  ladder-select → encode → verify`.
- `ffmpeg_tools.py` — `ffprobe`/`ffmpeg` wrappers (source probe, scene shots, VMAF, bitrate).
- `ladder.py` — deterministic rendition selection (monotone quality, dominated-rung pruning,
  bitrate spacing/floor/ceiling).
- `encoder.py` — deterministic `+bitexact` x264 encodes.
- `verifier.py` — the contract gate: decode, VMAF-vs-target, bitrate band, ladder monotonicity;
  `ContractViolation` on any gating miss.
- `cli.py` — argparse interface, bplate JSON envelope, exit-code floor 0/2/5, NDJSON progress,
  `--plan` dry-run.
- `tests/test_ladder.py` — red/green unit tests (selection + verifier), no external media.
