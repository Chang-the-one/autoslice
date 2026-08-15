# video-matrix-cutter

Local semantic rough-cut pipeline for turning one already-edited source video into multiple topic-specific social cuts.

## Mental model

```text
source.mp4
  -> PySceneDetect (physical shot boundaries)
  -> keyframes + optional Whisper transcript
  -> MiniMax-M3 (visual -> semantic scene map)
  -> scenes.json
  -> MiniMax planner OR deterministic recipe planner
  -> edit_plan.json
  -> FFmpegTool (deterministic execution)
  -> output.mp4
```

FFmpeg is deliberately **not** controlled with arbitrary model-generated shell commands. The model only chooses validated segment IDs. Python compiles those IDs into exact source time ranges, validates them, and calls FFmpeg with a fixed filter graph.

## Requirements

- Python 3.11+
- `ffmpeg` and `ffprobe` available on PATH
- MiniMax API key

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
cp .env.example .env
```

If `pip install -e` does not pick up the package (some framework Python builds on macOS do not process editable `.pth` files when the project path contains spaces), install non-editable:

```bash
pip install . --force-reinstall --no-deps
```

Put your MiniMax key in `.env`:

```env
MINIMAX_API_KEY=...
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_MODEL=MiniMax-M3
```

Optional local speech transcription:

```bash
pip install -e '.[speech]'
```

## Check runtime

```bash
video-matrix doctor
```

## 1. Analyze once

```bash
video-matrix analyze /path/to/source.mp4
```

Optional speech layer:

```bash
video-matrix analyze /path/to/source.mp4 --transcribe
```

Analysis is cached by SHA-256 of the source video. Re-running without `--force` reuses `scenes.json` and does not make new vision calls.

## 2. Inspect semantic scene map

```bash
video-matrix inspect /path/to/source.mp4
```

## 3. Create a rough cut

AI semantic planner:

```bash
video-matrix render /path/to/source.mp4 harvest_short
```

No-LLM deterministic planner:

```bash
video-matrix render /path/to/source.mp4 harvest_short --planner rules
```

Plan only, no render:

```bash
video-matrix render /path/to/source.mp4 harvest_short --plan-only
```

Outputs default to:

```text
output/source.harvest_short.mp4
```

## Files created in cache

```text
cache/<video_sha256>/
  frames/
  segments.json
  scenes.partial.json
  scenes.json
  edit_plan.harvest_short.ai.json
```

`scenes.json` is the reusable semantic map. It contains source timestamps plus visual meaning. `edit_plan.*.json` is the bridge between semantic decisions and deterministic FFmpeg execution.

## MVP categories

- garden
- harvest
- washing
- prep
- cutting
- cooking
- plating
- eating
- talking
- other

Secondary labels are open-ended, so the model can add `tomato`, `luffa`, `fig`, `closeup`, `basket`, etc.

## Safety / determinism boundary

The MiniMax planner never writes or executes FFmpeg commands. It returns segment IDs only. The program then:

1. rejects unknown IDs;
2. removes duplicates;
3. reapplies recipe include/exclude and quality thresholds;
4. enforces maximum duration;
5. translates IDs to trusted timestamps from `scenes.json`;
6. invokes `FFmpegTool.render()` with a fixed argument structure.

This is the semantic-to-hardcoded bridge.
