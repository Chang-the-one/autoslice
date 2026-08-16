# Changelog

All notable changes to `AutoSlice` (PyPI distribution: `video-matrix-cutter`)
are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-alpha] - 2026-08-15

First **public alpha** open-source release. Working MVP — APIs and schemas
may still change before 0.1.0 stable.

### What's in this release

- **Semantic scene map generation** — PySceneDetect (ContentDetector) splits
  the source video into physical shot boundaries; two JPEG keyframes per scene
  are extracted for downstream classification.
- **MiniMax M3 visual classification** — every scene is labelled with one of
  ten `primary_category` values plus open-ended secondary `labels`, using the
  MiniMax M3 multimodal model at `https://api.minimax.io/v1`. The client uses
  OpenAI's chat-completions protocol; **other providers are not officially
  supported or tested yet**.
- **Resumable / cached analysis** — every analysis is keyed by SHA-256 of the
  source video bytes. A `cache/aliases/<stem>.json` mechanism resolves
  symlink/iCloud-path naming mismatches. Mid-batch state is checkpointed to
  `scenes.partial.json` so an interrupted vision-LLM run resumes without
  re-spending tokens.
- **Optional faster-whisper transcript** — local speech transcription attaches
  spoken text to each scene before classification, improving accuracy when the
  speech mentions ingredients or subjects not visible in the sampled
  keyframes.
- **Recipe planner** — deterministic, no-API planner driven by `recipes.yaml`
  include/exclude lists, score thresholds, and per-recipe pacing.
- **Optional AI planner** — LLM-driven planner that returns only validated
  segment IDs. The model never emits timestamps, file paths, or shell
  commands.
- **Deterministic, validated FFmpeg execution** — `compile_plan()` validates
  every AI-suggested ID against `scenes.json`, drops duplicates, re-applies
  recipe filters, and re-resolves timestamps from the trusted cache. The
  resulting `FFmpegTool` filter graph is fixed and human-reviewable.
- **VideoToolbox acceleration on supported macOS systems** — `autoslice render
  --encoder auto` inspects the installed FFmpeg build and uses
  `h264_videotoolbox` when present.
- **`libx264` fallback on Linux / unsupported systems** — `auto` falls back to
  `libx264` when VideoToolbox is absent. Explicit `--encoder
  h264_videotoolbox` requests fail loudly with a clear error message rather
  than silently degrading.
- **Cross-platform CI** — GitHub Actions runs the test suite on Ubuntu for
  Python 3.11 and 3.12 with system FFmpeg installed. The speech extra is
  intentionally excluded from CI to keep the dependency download under ~1 GB.

### Notes for v0.1.0-alpha users

- Public project name is **AutoSlice**; the PyPI distribution remains
  `video-matrix-cutter` for v0.1.x. The console script is `autoslice`;
  `video-matrix` is kept as a backwards-compatible alias.
- Model provider is MiniMax-only in this release. Provider abstraction is a
  planned extension and is explicitly **not** promised in this alpha.
- The architecture (`scenes.json → planner → validated plan → FFmpeg`) is
  stable; individual CLI flags and config keys may still move before 0.1.0
  stable.

### Migration from pre-release local builds

- The cache layout changed: scenes are now under `cache/<sha256>/scenes.json`
  (previously a flat `cache/scenes.<stem>.json`). Delete `cache/` once to
  migrate.
- `recipes.yaml` keys are unchanged; the new `--target-duration` /
  `--max-duration` flags are an additive override.
- The Python import package is still `video_matrix`; do not import
  `autoslice` from Python.

[0.1.0-alpha]: https://github.com/Chang-the-one/autoslice/releases/tag/v0.1.0-alpha
