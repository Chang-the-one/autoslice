# AutoSlice

> **Analyze once. Cut many ways.**

```text
One source video
      ↓
Analyze once
      ↓
Semantic timeline
      ↓
 ┌────┼───────────────┐
 ↓    ↓               ↓
Harvest cut     Cooking cut     Garden cut
 ↓    ↓               ↓
FFmpeg renders each deterministically
```

AutoSlice turns one source video into a **reusable semantic timeline**, then
uses that timeline to create different rough cuts for different topics,
accounts, or formats — **without asking a vision model to watch the video
again every time.**

[![CI](https://github.com/Chang-the-one/autoslice/actions/workflows/ci.yml/badge.svg)](https://github.com/Chang-the-one/autoslice/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

---

## The three ideas behind AutoSlice

### 1. Analyze once. Cut many ways.

Most "AI video editors" still follow this shape:

```text
video → prompt → AI watches everything again → cut
```

AutoSlice separates the problem into a one-time perception step and many
editing decisions that work from the perception result:

```text
video
  ↓
semantic understanding        ← expensive, runs once
  ↓
reusable scenes.json          ← persistent, cached, inspectable
  ↓
editing decisions             ← cheap, repeatable
  ↓
validated timeline
  ↓
deterministic rendering       ← no model in the loop
```

That separation is the main idea.

### 2. Video understanding becomes a reusable asset, not temporary model context.

AutoSlice does not treat model understanding as throwaway context. It
persists what the model understood into `scenes.json`:

```json
{
  "segment_id": 12,
  "start": 42.1,
  "end": 47.8,
  "primary_category": "harvest",
  "labels": ["tomato", "picking", "garden", "closeup"],
  "description": "Picking ripe tomatoes directly from the vine.",
  "visual_quality": 0.91,
  "keep_score": 0.94
}
```

Think of it as **semantic subtitles for the video**. Instead of only knowing
`42.1s → 47.8s`, AutoSlice knows `42.1s → 47.8s — picking ripe tomatoes in
the garden, good close-up, strong candidate for a harvest edit`.

That semantic map is a persistent artifact. You can inspect it, cache it,
reuse it across recipes, build new workflows on top of it, or feed it into
entirely different editing systems later.

### 3. The LLM plans. Python validates. FFmpeg executes.

AutoSlice deliberately does **not** give an LLM arbitrary control over FFmpeg
or the shell.

The model can say:

```json
{ "segment_ids": [3, 12, 27, 31] }
```

It cannot say:

```bash
ffmpeg ...
```

The execution boundary is:

```text
LLM
 ↓
segment IDs             ← untrusted
 ↓
Python validation       ← rejects unknowns, drops duplicates,
                          re-applies recipe filters, rebuilds timestamps
 ↓
trusted timeline
 ↓
fixed FFmpeg pipeline   ← filter graph is built from validated timestamps only
 ↓
MP4
```

**AI decides what. Deterministic code decides how.**

---

## Why AutoSlice exists

A single 7-minute video may contain several useful stories: harvesting
vegetables, garden B-roll, washing ingredients, cooking, plating, talking to
camera. The full version may belong on one account. But a second account may
only need the harvesting footage, another may need the cooking sequence, and
a third may need a 30-second garden cut.

The useful shots are often scattered across the entire source video, so
simply cutting one continuous section does not work.

```text
7-minute source
      ↓
AutoSlice analyze
      ↓
scenes.json
      ↓
├── harvest_short
├── cooking_short
├── garden_short
└── your own recipe
```

The expensive visual-understanding step happens once. Everything after that
works from the semantic timeline.

---

## What AutoSlice is not

AutoSlice is **not** trying to replace DaVinci Resolve, Premiere Pro, Final
Cut, CapCut, or any full non-linear editor. It is a **semantic rough-cut
engine**. Its job is to answer:

> Which parts of this video belong in this version?

and then reliably create that version. You can use the result directly or
continue editing it in your normal NLE.

---

## Model provider

AutoSlice currently uses **MiniMax M3** for multimodal scene analysis and
optional AI planning. The integration uses the OpenAI-compatible client
protocol internally, but other providers are **not** officially supported or
tested yet. A model-provider abstraction is a planned extension.

If you need to point at a different endpoint today, set `MINIMAX_BASE_URL`
and `MINIMAX_API_KEY` in `.env`. Treat it as unsupported — expect rough
edges.

## Status

**v0.1.0-alpha.** Working MVP, APIs and schemas may still change.

---

## Quick start

### Requirements

- Python 3.11+
- FFmpeg + ffprobe
- A MiniMax API key

macOS:

```bash
brew install ffmpeg
```

### Install

```bash
git clone https://github.com/Chang-the-one/autoslice.git
cd autoslice
python3.11 -m venv .venv   # any Python 3.11+
source .venv/bin/activate
pip install -e ".[dev]"
# optional local speech transcription:
# pip install -e ".[speech]"
```

If `pip install -e` fails on macOS framework Python builds (some don't
process editable `.pth` files when the project path contains spaces):

```bash
pip install . --force-reinstall --no-deps
```

### Configure

```bash
cp .env.example .env
# edit .env and set MINIMAX_API_KEY
```

### Verify

```bash
autoslice doctor
```

### 1. Analyze once

```bash
autoslice analyze /path/to/source.mp4
```

With local speech transcription (Chinese, English, etc.):

```bash
autoslice analyze /path/to/source.mp4 --transcribe
```

This creates and caches the semantic timeline. Re-running is free.

### 2. Inspect what AutoSlice understood

```bash
autoslice inspect /path/to/source.mp4
```

Example output:

```text
#012 00:42.100–00:47.800 harvest   keep=0.94 quality=0.91
  Picking ripe tomatoes directly from the vine.
  labels: tomato, picking, garden, closeup
```

If the model misunderstood the video, you can see it before rendering.

### 3. Generate different cuts

```bash
autoslice render /path/to/source.mp4 harvest_short --planner rules
autoslice render /path/to/source.mp4 cooking_short --planner ai
autoslice render /path/to/source.mp4 garden_short
```

These do not require the vision model to watch the source video again.

> Tip: `video-matrix` is kept as an alias of `autoslice` in v0.1.x. Use either
> command interchangeably.

Outputs land in `output/<source_stem>.<recipe>.mp4`.

---

## Recipes

Recipes describe **what kind of story you want**, not how FFmpeg should
operate. The included `harvest_short`, `cooking_short`, and `garden_short`
are **examples**, not architectural limitations — you can freely add
`podcast_highlights`, `product_demo`, `travel`, `sports_practice`,
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

The ten built-in `primary_category` values are: `garden`, `harvest`,
`washing`, `prep`, `cutting`, `cooking`, `plating`, `eating`, `talking`,
`other`. Secondary `labels` are open-ended (`tomato`, `luffa`, `basket`,
`closeup`, …) — see `cache/<sha>/scenes.json` for what your source
produces.

---

## Two planners

### Rules planner (deterministic, no API call)

```bash
autoslice render source.mp4 harvest_short --planner rules
```

Useful when you want repeatability, no additional LLM planning call, or
simple include/exclude selection.

### AI planner

```bash
autoslice render source.mp4 harvest_short --planner ai
```

The planner sees only the semantic scene map. It does **not** see the
video again. It can reason about redundancy, pacing, story progression,
visual quality, and target duration — but its output is still limited to
validated segment IDs.

---

## Architecture

```text
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
        |       |  MiniMax M3     |       |
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
              (hardware encode when available)
                       |
                       v
                 output.mp4
```

The critical safety property: the LLM only emits segment IDs. Python then
(a) rejects unknown IDs, (b) drops duplicates, (c) re-applies recipe
include/exclude and quality filters, (d) re-resolves timestamps from
`scenes.json`, (e) hands a fixed filter graph to FFmpeg. There is no path by
which the model can inject arbitrary shell.

AutoSlice is **local-first** in the parts that matter for cost, privacy,
and reproducibility:

- scene detection runs locally
- frame extraction runs locally
- optional Whisper transcription runs locally
- planning data and caches stay local
- FFmpeg rendering runs locally
- only the semantic vision analysis currently calls MiniMax M3 over HTTPS

---

## Why `scenes.json` matters

`scenes.json` is intentionally a first-class output rather than an internal
temporary file. It creates a clean boundary between perception and editing.
That means future systems can swap the perception side
(`MiniMax → another vision model`) without changing the renderer, or swap the
rendering side (`FFmpeg → OpenTimelineIO / DaVinci / Premiere`) without
changing video understanding.

This separation is what makes AutoSlice more than a one-off AI editing
script.

---

## CLI reference

### `analyze` — build semantic scene map

```bash
autoslice analyze SOURCE [--transcribe] [--force] \
                         [--threshold 27.0] [--batch-size 6] \
                         [--whisper-model small] [--quiet]
```

- **`--transcribe`** enable local Whisper (`faster-whisper`) to attach speech
  to each segment before sending to the vision model. Cached by video hash,
  so re-runs are free.
- **`--force`** re-analyze even if cached `scenes.json` exists (e.g. after
  changing `--threshold`).
- **`--threshold`** PySceneDetect sensitivity (lower = more cuts). Default
  27.0.

### `render` — make a rough cut

```bash
autoslice render SOURCE RECIPE [--planner rules|ai] \
                               [--max-width 1080] \
                               [--encoder auto|h264_videotoolbox|hevc_videotoolbox|libx264] \
                               [--target-duration 50] [--max-duration 75] \
                               [--plan-only] [--output PATH]
```

- **`--max-width 1080`** caps the output width at 1080 px while preserving
  the source aspect ratio (FFmpeg `scale=1080:-2`). It does **not** force a
  1080×1920 vertical frame — use a separate tool if you need to re-frame to
  portrait.
- **`--encoder auto`** inspects the installed FFmpeg and prefers
  `h264_videotoolbox` when available (macOS), falling back to `libx264` on
  Linux and other platforms. Explicit requests fail loudly when the encoder
  is not present.
- **`--target-duration / --max-duration`** override the recipe's pacing for
  this one render — useful for tighter shorts without editing `recipes.yaml`.
- **`--plan-only`** write `edit_plan.<recipe>.<planner>.json` to the cache
  and stop. Inspect, then run without `--plan-only` to actually render.

### `inspect` — print scenes.json

```bash
autoslice inspect SOURCE
```

### `doctor` — verify ffmpeg/ffprobe reachable

```bash
autoslice doctor
```

---

## Cache layout

```text
cache/<video_sha256>/
  frames/                     # JPEG thumbnails (delete to free space; regenerable)
  segments.json               # raw scene detection + speech
  scenes.partial.json         # resumable mid-batch state from the vision LLM
  scenes.json                 # final semantic scene map
  edit_plan.<recipe>.<planner>.json
  transcript.txt              # only when --transcribe was used

cache/aliases/<stem>.json     # symlink/iCloud-path to hash lookup
```

The cache key is the SHA-256 of the video file's bytes. A symlink whose
`.resolve()` filename differs from its link name is automatically resolved
via `cache/aliases/` so re-running `render` against a symlinked original
works after `analyze` ran on a proxy.

---

## Performance notes

- **Proxies**: For analysis of large 4K videos, build a 480p H.264 proxy
  first. Apple's `h264_videotoolbox` encoder does this in roughly real
  time:

  ```bash
  ffmpeg -hwaccel videotoolbox -i source.mp4 -vf "scale=480:-2" -an \
         -c:v h264_videotoolbox -b:v 800k proxy.mp4
  ```

  Then `analyze proxy.mp4`. The renderer can still target the original
  `source.mp4` because timestamps in `scenes.json` are in seconds, not
  frame indices.

- **Encoding**: `autoslice render` defaults to `auto`, which prefers
  Apple's `h264_videotoolbox` encoder on macOS for ~real-time 4K → 1080p
  encode, and falls back to `libx264` on Linux. Override with `--encoder
  libx264` if you need cross-platform reproducibility of the encode path
  itself.

- **Vision API cost**: Each scene costs roughly one image-classify call; a
  5-minute video at default settings lands around 25–35 segments × 6 per
  request = ~5 batches. Each batch is small (≈1–2k tokens).

---

## Safety boundary

Everything before `FFmpegTool` is treated as untrusted input. Specifically:

1. The LLM planner returns only segment IDs. Never timestamps, never file
   paths, never commands.
2. `compile_plan()` validates every ID against `scenes.json`, drops
   eligibility-violating clips, and rebuilds timestamps from the trusted
   cache.
3. `FFmpegTool` constructs the filter graph from validated timestamps only.
   It does not interpolate any string from the model into a shell command.

```text
LLM output
    ↓
untrusted
    ↓
validator
    ↓
trusted timeline
    ↓
FFmpeg
```

See `tests/test_core.py::test_ai_planner_cannot_inject_ffmpeg` for the
regression test.

---

## Testing

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

The test suite mocks the vision LLM and uses a synthetic 24-second test
source. It does not require a real API key. Encoder resolution is covered
by 9 dedicated tests (auto-prefer, fallback, explicit-pass-through,
explicit-fail, missing-libx264-fail, invalid-value).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No semantic analysis found` on render after `analyze` was on a proxy | the symlink name and the proxy name differ — run `analyze` once on the original OR ensure the proxy stem starts with the original stem so the alias resolver matches |
| `invalid literal for int() with base 10: 'SEGMENT 25'` | the vision LLM occasionally echoes the prompt's `id=` token back as a string; auto-handled now (client extracts the integer and retries) |
| `pip install -e` silently fails | use `pip install . --force-reinstall --no-deps` (path-with-spaces fix) |
| `Requested encoder 'h264_videotoolbox' is not available in the installed FFmpeg` | you're on Linux; use `--encoder libx264` or rely on `auto` (default) |
| `No suitable H.264 encoder found in the installed FFmpeg` | your FFmpeg build lacks both VideoToolbox and libx264 — install libx264 or rebuild FFmpeg |
| Slow `analyze` on a 4K video | transcode to a 480p H.264 proxy first |
| Render takes too long on a 4K source | add `--max-width 1080` and rely on the default `auto` encoder |
| Local Whisper errors with `IndexError: tuple index out of range` | your proxy was created with `-an` (no audio); re-make the proxy with audio **or** point `analyze --transcribe` at the original |

## Contributing

Issues and pull requests welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md)
first. By participating you agree to the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Please do **not** file a public
issue for security problems — see [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE).
