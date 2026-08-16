# AutoSlice

> AutoSlice turns video into a semantic timeline, then lets an LLM plan the edit while FFmpeg executes it deterministically.

**Status: Alpha** — working MVP, APIs and schemas may still change.

Local-first CLI that turns one already-edited source video into multiple
topic-specific rough cuts for social platforms. The package name on PyPI is
still `video-matrix-cutter` for backwards compatibility; the console script is
`autoslice`.

```
source.mp4
  -> PySceneDetect  (physical shot boundaries)
  -> keyframes + optional Whisper transcript
  -> vision LLM     (MiniMax M3 — visual -> semantic scene map)
  -> scenes.json
  -> deterministic recipe planner OR LLM planner
  -> edit_plan.json
  -> FFmpegTool    (deterministic execution, hardware-accelerated when available)
  -> output.mp4
```

**Three-stage split:** segmentation (PySceneDetect) builds the *timeline*, an
LLM does the *planning* (segment IDs only), and FFmpeg does the *execution*
(deterministic, hardware-accelerated). The LLM never writes FFmpeg commands —
it only chooses validated segment IDs. Python compiles those IDs into exact
source time ranges, validates them, and calls FFmpeg with a fixed,
human-reviewable filter graph.

[![CI](https://github.com/Chang-the-one/autoslice/actions/workflows/ci.yml/badge.svg)](https://github.com/Chang-the-one/autoslice/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

## Model provider

AutoSlice currently uses **MiniMax M3** for multimodal scene analysis and
optional AI planning. The integration uses the OpenAI-compatible client
protocol internally, but other providers are **not** officially supported or
tested yet. A model-provider abstraction is a planned extension.

If you need to point at a different endpoint today, set `MINIMAX_BASE_URL` and
`MINIMAX_API_KEY` in `.env`. Treat it as unsupported — expect rough edges.

## When to use this

- You shoot one 5–15 minute raw video (Xiaohongshu cooking or garden clip,
  talk + B-roll, podcast with cuts).
- You want three or four different short cuts for different accounts
  (harvest short, cooking short, garden short, …).
- You want it local-first — segmentation and rendering run on your machine,
  while semantic analysis currently calls MiniMax M3 over HTTPS.
- The pipeline is reproducible and the final cut is human-reviewable.

This is **not** a polished-final-cut editor. It produces rough cuts — segment
selection, ordering, and duration tuning. You assemble the final piece in
iMovie, CapCut, Premiere, or DaVinci Resolve from the rough-cuts output.

## Install

```bash
git clone https://github.com/Chang-the-one/autoslice.git
cd autoslice
python3.12 -m venv .venv   # any Python 3.11+
source .venv/bin/activate

pip install -e ".[dev]"
# optional speech transcription:
# pip install -e ".[speech]"

cp .env.example .env
# edit .env and set MINIMAX_API_KEY
```

If `pip install -e` fails on macOS framework Python builds (some don't process
editable `.pth` files when the project path contains spaces):

```bash
pip install . --force-reinstall --no-deps
```

## Requirements

- Python 3.11+
- `ffmpeg` and `ffprobe` on `PATH` — install via Homebrew: `brew install ffmpeg`
- A MiniMax API key

> FFmpeg is **not** distributed with AutoSlice. Users install their own FFmpeg
> build.

`autoslice doctor` checks the local toolchain for you.

## Quick start

```bash
# 1. Analyze once. Cached by SHA-256 of the video. Re-running is free.
autoslice analyze /path/to/source.mp4

# 1b. With local speech transcription (Chinese, English, etc.):
autoslice analyze /path/to/source.mp4 --transcribe

# 2. Inspect what the model thinks each segment is
autoslice inspect /path/to/source.mp4

# 3. Generate a rough cut
autoslice render /path/to/source.mp4 cooking_short --planner rules
autoslice render /path/to/source.mp4 harvest_short --planner ai
```

Outputs land in `output/<source_stem>.<recipe>.mp4`.

> Tip: `video-matrix` is kept as an alias of `autoslice` in v0.1.x. Use either
> command interchangeably.

## CLI reference

### `analyze` — build semantic scene map

```bash
autoslice analyze SOURCE [--transcribe] [--force] \
                         [--threshold 27.0] [--batch-size 6] \
                         [--whisper-model small] [--quiet]
```

- **`--transcribe`** enable local Whisper (`faster-whisper`) to attach speech
  to each segment before sending to the vision model. Cached by video hash, so
  re-runs are free.
- **`--force`** re-analyze even if cached `scenes.json` exists (e.g. after
  changing `--threshold`).
- **`--threshold`** PySceneDetect sensitivity (lower = more cuts). Default 27.0.

### `render` — make a rough cut

```bash
autoslice render SOURCE RECIPE [--planner rules|ai] \
                               [--max-width 1080] \
                               [--encoder auto|h264_videotoolbox|hevc_videotoolbox|libx264] \
                               [--target-duration 50] [--max-duration 75] \
                               [--plan-only] [--output PATH]
```

- **`--max-width 1080`** caps the output width at 1080 px while preserving the
  source aspect ratio (FFmpeg `scale=1080:-2`). It does **not** force a 1080×1920
  vertical frame — use a separate tool if you need to re-frame to portrait.
- **`--encoder auto`** inspects the installed FFmpeg and prefers
  `h264_videotoolbox` when available (macOS), falling back to `libx264` on
  Linux and other platforms. Explicit requests fail loudly when the encoder is
  not present.
- **`--target-duration / --max-duration`** override the recipe's pacing for
  this one render — useful for tighter shorts without editing `recipes.yaml`.
- **`--plan-only`** write `edit_plan.<recipe>.<planner>.json` to the cache and
  stop. Inspect, then run without `--plan-only` to actually render.

### `inspect` — print scenes.json

```bash
autoslice inspect SOURCE
```

### `doctor` — verify ffmpeg/ffprobe reachable

```bash
autoslice doctor
```

## Architecture

```
                  source.mp4
                       |
                       v
        +-------+  PySceneDetect  +-------+
        |       +---------------->|       |
        | cache |                 | cache |
        |       |  extract 2 KFs  |       |
        |       |  /segment       |       |
        |       +---------------->|       |
        |       |                 |       |
        |       |  Whisper (opt)  |       |
        |       |  attach speech  |       |
        |       +---------------->|       |
        |       |                 |       |
        |       |  vision LLM     |       |
        |       |  classify batch |       |
        |       +---------------->|  sc   |
        |       |                 |  ene  |
        |       |  optional: LLM  |  s.   |
        |       |  planner OR     |  js   |
        |       |  rules_select   |  on   |
        |       +---------------->|       |
        +-------+                 +-------+
                       |
                       v
                 edit_plan.json
                       |
                       v
                  FFmpegTool
              (hardware encode)
                       |
                       v
                 output.mp4
```

The critical safety property: the LLM only emits segment IDs. Python then
(a) rejects unknown IDs, (b) drops duplicates, (c) re-applies recipe
include/exclude and quality filters, (d) re-resolves timestamps from
`scenes.json`, (e) hands a fixed filter graph to FFmpeg. There is no path by
which the model can inject arbitrary shell.

## Recipes

Recipes live in `recipes.yaml`. The included `harvest_short`, `cooking_short`,
and `garden_short` are **examples**, not architectural limitations — you can
freely add `podcast_highlights`, `product_demo`, `travel`, `sports_practice`,
`tutorial`, `talking_head`, or `broll_only` recipes without touching Python.

```yaml
harvest_short:
  include: [garden, harvest, picking, vegetable, fruit]
  exclude: [cooking, plating, talking]
  target_duration: 45
  max_duration: 75
  preserve_source_order: true
  min_keep_score: 0.45
  min_visual_quality: 0.35
  prompt: "Make the harvest itself the story..."
```

Write a new recipe by adding a key to `recipes.yaml`. Pass it as the `RECIPE`
argument to `render`.

The ten built-in `primary_category` values are: `garden`, `harvest`,
`washing`, `prep`, `cutting`, `cooking`, `plating`, `eating`, `talking`,
`other`. Secondary `labels` are open-ended (`tomato`, `luffa`, `basket`,
`closeup`, …) — see `cache/<sha>/scenes.json` for what your source produces.

## Cache layout

```text
cache/<video_sha256>/
  frames/                     # JPEG thumbnails (delete to free space; regenerable)
  segments.json               # raw scene detection + speech
  scenes.partial.json         # resumable Mid-batch state from the vision LLM
  scenes.json                 # final semantic scene map
  edit_plan.<recipe>.<planner>.json
  transcript.txt              # only when --transcribe was used

cache/aliases/<stem>.json     # symlink/iCloud-path to hash lookup
```

The cache key is the SHA-256 of the video file's bytes. A symlink whose
`.resolve()` filename differs from its link name is automatically resolved via
`cache/aliases/` so re-running `render` against a symlinked original works
after `analyze` ran on a proxy.

## Performance notes

- **Proxies**: For analysis of large 4K videos, build a 480p H.264 proxy first.
  Apple's `h264_videotoolbox` encoder does this in roughly real time:

  ```bash
  ffmpeg -hwaccel videotoolbox -i source.mp4 -vf "scale=480:-2" -an \
         -c:v h264_videotoolbox -b:v 800k proxy.mp4
  ```

  Then `analyze proxy.mp4`. The renderer can still target the original
  `source.mp4` because timestamps in `scenes.json` are in seconds, not frame
  indices.

- **Encoding**: `autoslice render` defaults to `auto`, which prefers Apple's
  `h264_videotoolbox` encoder on macOS for ~real-time 4K → 1080p encode, and
  falls back to `libx264` on Linux. Override with `--encoder libx264` if you
  need cross-platform reproducibility of the encode path itself.

- **Vision API cost**: Each scene costs roughly one image-classify call; a
  5-minute video at default settings lands around 25–35 segments × 6 per
  request = ~5 batches. Each batch is small (≈1–2k tokens).

## Testing

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

The test suite mocks the vision LLM and uses a synthetic 24-second test
source. It does not require a real API key. Encoder resolution is covered by
8 dedicated tests (auto-detect, fallback, explicit-pass-through, explicit-fail).

## Troubleshooting

| Problem | Fix |
|---|---|
| `No semantic analysis found` on render after `analyze` was on a proxy | the symlink name and the proxy name differ — run `analyze` once on the original OR ensure the proxy stem starts with the original stem so the alias resolver matches |
| `invalid literal for int() with base 10: 'SEGMENT 25'` | the vision LLM occasionally echoes the prompt's `id=` token back as a string; auto-handled now (client extracts the integer and retries) |
| `pip install -e` silently fails | use `pip install . --force-reinstall --no-deps` (path-with-spaces fix) |
| `Requested encoder 'h264_videotoolbox' is not available in the installed FFmpeg` | you're on Linux; use `--encoder libx264` or rely on `auto` (default) |
| Slow `analyze` on a 4K video | transcode to a 480p H.264 proxy first |
| Render takes too long on a 4K source | add `--max-width 1080` and rely on the default `auto` encoder |
| Local Whisper errors with `IndexError: tuple index out of range` | your proxy was created with `-an` (no audio); re-make the proxy with audio **or** point `analyze --transcribe` at the original |

## Safety boundary

The deterministic FFmpeg path is the program's trust boundary. Everything
before it — segmentation, classification, planning — is treated as untrusted
input. Specifically:

1. The LLM planner returns only segment IDs. Never timestamps, never file
   paths, never commands.
2. `compile_plan()` validates every ID against `scenes.json`, drops
   eligibility-violating clips, and rebuilds timestamps from the trusted cache.
3. `FFmpegTool` constructs the filter graph from validated timestamps only. It
   does not interpolate any string from the model into a shell command.

See `tests/test_core.py::test_ai_planner_cannot_inject_ffmpeg` for the
regression test.

## Contributing

Issues and pull requests welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md)
first. By participating you agree to the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Please do **not** file a public
issue for security problems — see [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE).
