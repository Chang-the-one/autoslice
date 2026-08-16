# Changelog

All notable changes to `video-matrix-cutter` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-15

Initial public release. Semantic rough-cut pipeline that turns one already-edited
source video into multiple topic-specific short clips.

### Added

- **Scene detection** via PySceneDetect (ContentDetector). Per-scene keyframe
  extraction (two frames per scene: middle + end).
- **Optional local speech transcription** via `faster-whisper`. Whisper output is
  attached to each scene so the vision model receives both visual and spoken
  context (improves classification accuracy for cooking/garden clips where the
  speech mentions ingredients that are not visible in the sampled frames).
- **Vision LLM classification** (any OpenAI-chat-compatible endpoint; default
  `MiniMax-M3` at `https://api.minimax.io/v1`). Batched keyframe requests with
  resumable partial-state cache so a crash mid-batch does not lose prior work.
- **Two planners**:
  - `rules` — deterministic include/exclude + score filter from `recipes.yaml`.
    No API calls.
  - `ai` — LLM-driven planner that returns only validated segment IDs.
    The model never emits timestamps, paths, or shell commands.
- **FFmpeg rendering** with a fixed, human-reviewable filter graph. Hardware
  acceleration on macOS (`h264_videotoolbox` / `hevc_videotoolbox`); falls back
  to `libx264` on other platforms. Vertical 1080p output by default.
- **Content-hash cache** keyed by SHA-256 of the source video bytes. A
  `cache/aliases/<stem>.json` mechanism resolves symlink/iCloud-path naming
  mismatches, so re-running `render` against a symlinked original works after
  `analyze` was performed on a proxy.
- **Per-invocation overrides**: `--target-duration` and `--max-duration` on
  `render` override the recipe's pacing without editing `recipes.yaml`.
- **CLI**: `analyze`, `render`, `inspect`, `doctor`. `--plan-only` writes
  `edit_plan.<recipe>.<planner>.json` and stops.
- **Safety boundary**: LLM output cannot reach `FFmpegTool` without passing
  through `compile_plan()` validation (unknown-ID rejection, duplicate drop,
  include/exclude re-check, timestamp rebuild from trusted cache). A regression
  test in `tests/test_core.py::test_ai_planner_cannot_inject_ffmpeg` enforces
  this contract.
- **Test suite**: 9 tests, no real API key required (synthetic 24-second fixture).

### Notes for users upgrading from pre-release local builds

- The cache layout changed: scenes are now under `cache/<sha256>/scenes.json`
  (previously a flat `cache/scenes.<stem>.json`). Delete `cache/` once to
  migrate.
- `recipes.yaml` keys are unchanged; the new `--target-duration` /
  `--max-duration` flags are an additive override.
- `MINIMAX_*` environment variables are no longer read directly; the client now
  uses `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`, `MINIMAX_MODEL` with sensible
  defaults.

[0.1.0]: https://github.com/Chang-the-one/autoslice/releases/tag/v0.1.0
