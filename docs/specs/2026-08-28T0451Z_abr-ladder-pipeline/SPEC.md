# smart-abr-ladder — Per-Title / Per-Shot ABR Ladder, Verified

A Workchain-native tool that turns one source video into a *proven* adaptive-bitrate
ladder: probe → shot-detect → rate-distortion model → ladder selection → encode →
**verify**. The verification is the product.

## Problem

Content-aware (per-title / per-shot) ABR ladder generation is the highest-leverage
encoding optimization in media today, and it is almost entirely closed:

- **Commercial systems are black boxes.** Bitmovin's per-title encoding and AWS
  Elemental MediaConvert's "Automated ABR" (QVBR) choose renditions for you, but their
  decision logic is proprietary and unauditable. You cannot answer "why this rung at
  this bitrate?"
- **Open-source pieces are partial.** `ab-av1` does per-*file* CRF search (not a
  ladder); `ffmpeg-quality-metrics`/`libvmaf` *measure* but don't decide; the few ladder
  prototypes (`vmaf-enhanced-encoding`, `autovmaf`, `content-aware-abr-encoding`) are
  research code without provenance, reproducibility, or a correctness contract.
- **Nobody proves the output.** "FFmpeg exited 0" is treated as "the ladder is correct."
  Nobody verifies every rendition decodes, hits its target quality within tolerance,
  holds bitrate band, stays monotonic, and carries no redundant rungs.

This appears in the Apple Cloud Media Engineer JD (200678579-0836) as "explore and
prototype optimizations across encoding pipelines" and "how metadata and ML models can
enrich the media experience." Our answer: make the optimization **auditable**, in the
same "proven, not exit-0" sense the rest of the LUFS toolset already treats audio.

## Goals

1. Emit a per-title ABR ladder (renditions = resolution × bitrate × codec profile) whose
   selection is derived from measured rate-distortion data, not a fixed table.
2. Support per-shot refinement as a second pass: allocate bitrate across shots within a
   rendition, not just across the rendition set.
3. Make every decision **reproducible and auditable**: deterministic seeds, explicit
   recipe (encoder + library + model versions), content-addressed source identity.
4. **Verify the ladder** against a machine-checked contract before reporting success:
   decode-validity, target-VMAF-within-tolerance, bitrate in band, monotonicity,
   no-redundant-rungs, and a provenance record tying output slots back to source hash +
   recipe hash.
5. Be **agent-first**: `--json`, a `--plan` dry-run that emits the ladder without
   encoding, the bplate JSON envelope (`{"status":"success","data":…}` /
   `{"status":"error","code":N,"message":…}`), exit-code floor (0 success, 2 usage,
   5 contract-violated), and NDJSON progress so an agent can drive and observe it.

## Non-goals

- **Not** a live/real-time encoder. This is file-based VOD ladder generation.
- **Not** a video player or packager. Output is renditions + an HLS/DASH manifest
  *referenced for verification*; final CMAF/segment packaging is out of scope here and
  belongs to `llhls-certify`'s verification domain (see Ecosystem References).
- **Not** a replacement for libvmaf or an encoder. We orchestrate FFmpeg and consume
  libvmaf; we do not reimplement them.
- **Not** yet a certified curated component (per Workchain's *unverified → verified →
  certified* tiers). This phase targets "verified" — passes its own contract
  automatically. Signing/certification is a later tier.

## Design approach

`smart-abr-ladder` is a Workchain *chain*: a YAML composition of self-contained
components, each with a `step.yaml` schema + `run.sh` + README, parsed by the one
Workchain parser and gated by the one Workchain verifier. The chain is:

```
probe → shot-detect → rd-model → ladder-select → encode → verify
```

- **probe / shot-detect** produce a normalized source model (codec, resolution, fps,
  duration, frame count) plus shot boundaries with per-shot spatial/temporal complexity
  (SI/TI). These are FFmpeg filter outputs, captured as typed JSON.
- **rd-model** runs a small grid of trial encodes (a sparse sample of resolution × CRF
  points) through a constrained FFmpeg encode + libvmaf, then fits/interpolates a
  rate-distortion surface. This is the only compute-heavy stage; it is deliberately the
  one that scales.
- **ladder-select** chooses renditions from the RD surface subject to explicit
  constraints — device resolution rungs, bitrate spacing/step, monotonic quality,
  VBV/HRD caps, and a no-redundant-rung rule (drop a rung whose neighbor dominates it in
  both quality and bitrate). Per-shot is realized as a second-pass bit-allocation over
  the chosen rendition structure.
- **encode** executes the selected ladder deterministically (fixed seed, no wall-clock
  timestamps in output, pinned encoder/library versions recorded in the recipe).
- **verify** is the gate: the Workchain verifier checks every declared post-condition —
  per-output existence/non-empty/decode, plus numeric contract (VMAF floor per rung,
  bitrate band, monotone ladder, redundant-rung absence) — and turns "ran" into
  "proven". A failed contract fails the step, never silently.

### Why not a fixed ladder table

A fixed ladder (the "Netflix static" rungs) ignores content: an anime series and a
sports broadcast do not deserve the same bitrate at the same resolution. The RD model
recovers the actual content's difficulty curve and spends bits where they matter. This
is the whole point, and the reason the tool is *smart* rather than a shell script around
`-preset`.

### Verification is the differentiator

Every prior-art tool on this stack stops at "encoded." We add the contract that proves
it. This is the same class of correctness the Workchain verifier already enforces for
`normalization`/`audio_benchmark`: measure the achieved value, compare to the declared
target, fail honestly on violation. Generalized here from audio (`audio_valid`) to video
(`video_valid`).

## Ecosystem references

Non-project tools this phase's design depends on or hands off to — named once, here:

- **`lufs-audio/workchain`** — the engine, parser, and verifier this tool is built *as a
  chain inside*. Its `lib/workchain_verify.py` is the verifier; its `catalog` component
  (SHA-256 content-hash provenance) and `audio_benchmark` (multi-dimension QC) are the
  lineage this tool's `verify` stage generalizes from audio to video.
- **`danialrami/workchain`** (personal) — where the *video* assert primitives
  (`video_valid`, `manifest_valid`, and the numeric post-condition extension) are first
  written, before migrating upstream to `lufs-audio/workchain`. See `llhls-certify`.
- **`lufs-audio/lsbx`** — the "verified-in / verified-out" lifecycle idiom; `serverless-transcode`
  reuses the *provenance* half of this chain's design, and both share the recipe-hash
  discipline.
- **`lufs-audio/bplate`** — the Seven LUFS Tests, the exit-code floor (0/2/5) and the
  JSON envelope this CLI conforms to.
- **Apple HLS Authoring Specification for Apple Devices**
  (`developer.apple.com/documentation/http-live-streaming/hls-authoring-specification-for-apple-devices`)
  — the rendition/ladder and `EXT-X-VERSION`/CMAF guidance our ladder targets, so
  rendered rungs are Apple-device-deliverable.
- **Netflix VMAF** (`github.com/Netflix/vmaf`) — the perceptual metric; cited because our
  per-title/per-shot method is the open re-implementation of Netflix's proprietary
  Dynamic Optimizer, and VMAF is the metric the whole comparison is scored in.
- **Prior art** (differentiation targets): `alexheretic/ab-av1`,
  `alexanderkroh/vmaf-enhanced-encoding`, `Eyevinn/autovmaf`,
  `nimigeanu/content-aware-abr-encoding`, `slhck/ffmpeg-quality-metrics`.

## Language

**Python** (3.10+), matching Workchain's `lib/` so the verifier and chain-integration
surfaces are shared, not re-implemented. This is a deliberate deviation from the
rust-dev/Primitive default: `smart-abr-ladder`'s risk lives in *orchestration and
verification correctness*, which Workchain already owns in Python — there is no
safety-critical core here that a Rust type system would newly protect. FFmpeg + libvmaf
are native subprocess calls either way. Flagged; reversible if Daniel wants a Rust core.

## Units

1. `01-probe-and-shard` — normalized source model + shot/segment detection.
2. `02-rd-model` — trial encodes + VMAF → rate-distortion surface fit.
3. `03-ladder-select` — constrained renditions + rung selection (monotone, no-redundant).
4. `04-encode` — deterministic execution of the selected ladder.
5. `05-verify-and-provenance` — the verifier contract + content/recipe hashing.
6. `06-cli-envelope` — CLI, JSON envelope, dry-run plan, exit codes, NDJSON.

## Done criteria

- [ ] The full chain runs end-to-end via the Workchain engine (`process_step` + verifier).
- [ ] `--plan` emits a complete, deterministic ladder (JSON) without encoding a frame.
- [ ] `verify` fails the step (exit 5) on any contract violation — a provably-bad ladder
      is never reported as success.
- [ ] Every rendition in a verified ladder decodes, hits target VMAF within tolerance,
      holds bitrate band, and the ladder is monotone with no redundant rungs.
- [ ] Provenance record binds each output to source SHA-256 + recipe hash + encoder/library
      versions.
- [ ] `cargo`/test parity: `pytest` + fixtures + a checked-in example that re-runs deterministically.
- [ ] Conforms to bplate exit-code floor and JSON envelope; `--json` and NDJSON progress.
- [ ] Fixtures under `tests/fixtures/` (a small, checked-in, license-clean source clip).

See `units/` for the per-unit contracts. Each unit is self-contained and independently
dispatchable; the interface contracts below them are the seams the downstream units
(type `01`'s source model into `02`, `02`'s RD surface into `03`, `03`'s ladder spec
into `04`, `04`'s outputs into `05`) depend on.
