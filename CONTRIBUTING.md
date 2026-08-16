# Contributing to video-matrix-cutter

Thanks for your interest in the project! `video-matrix-cutter` is a local-first
CLI that turns one source video into multiple topic-specific rough cuts. Most
contributions fall into one of three buckets: bug reports, recipe additions,
and pipeline improvements.

By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Please **do not** file public issues for
security problems — see [SECURITY.md](SECURITY.md) for the private disclosure
path.

## Quick orientation

```
source.mp4
  -> PySceneDetect  (physical shot boundaries)
  -> keyframes + optional Whisper transcript
  -> vision LLM     (visual -> semantic scene map)
  -> scenes.json
  -> deterministic recipe planner OR LLM planner
  -> edit_plan.json
  -> FFmpegTool    (deterministic execution, hardware-accelerated when available)
  -> output.mp4
```

Read the **Architecture** section of [README.md](README.md) for a full diagram
and the **Safety boundary** section for the trust model. The LLM planner only
emits segment IDs; `compile_plan()` validates them and `FFmpegTool` is the trust
boundary.

## Development setup

Requires Python 3.11+ and `ffmpeg`/`ffprobe` on `PATH`.

```bash
git clone https://github.com/Chang-the-one/autoslice.git
cd autoslice
python3.12 -m venv .venv
source .venv/bin/activate

# editable install for local dev. If this silently fails on macOS framework
# Python when the path contains spaces, fall back to the non-editable install
# documented in README.md:
pip install -e ".[dev,speech]"

cp .env.example .env   # add MINIMAX_API_KEY only if you intend to hit the real API

# Verify everything works without an API key
pytest -q
```

The test suite uses a synthetic 24-second source (`input/synthetic.mp4`) and
mocks the vision LLM — it should be green out of the box.

## Project layout

```
src/video_matrix/
  cli.py              argparse entry points: analyze, render, inspect, doctor
  pipeline.py         orchestrates the full analyze/render flow
  scene_detect.py     PySceneDetect wrapper + keyframe extraction
  frames.py           JPEG keyframe writer (Pillow)
  transcribe.py       optional faster-whisper wrapper
  minimax_client.py   OpenAI-chat-compatible client (default MiniMax-M3)
  planner.py          rules planner + ai planner + compile_plan() validator
  ffmpeg_tool.py      fixed filter graph -> FFmpeg subprocess
  models.py           Pydantic models: Scene, Segment, EditPlan
  utils.py            hashing, symlink/alias resolution, paths

tests/
  test_core.py        end-to-end pipeline + safety regression
  conftest.py         synthetic fixture
```

## How to contribute

### Bug reports

Open an issue with:

- `video-matrix doctor` output (toolchain state).
- The exact `video-matrix analyze` / `video-matrix render` command line.
- The `cache/<sha>/scenes.json` (or a redacted summary if the cache is large).
- A redacted excerpt of the LLM reply if the bug involves the planner.

Do **not** paste your API key.

### Recipe additions

New recipes live in `recipes.yaml`. Open a PR with:

- A short rationale (1–2 paragraphs).
- The new recipe block.
- One example run output (rough-cut MP4 size, total duration, segments used).
- The `cache/<sha>/scenes.json` excerpt that produced it (or any example
  `scenes.json` that would exercise the include/exclude logic).

Recipes are pure data; no Python change required.

### Pipeline improvements

Open an issue first if the change touches:

- The `compile_plan()` validation contract.
- The `FFmpegTool` filter graph.
- Cache keying (`cache/<sha>/`) — anything that would invalidate existing caches.

Smaller, well-scoped changes (CLI flags, new optional features behind flags,
docstring fixes) can go straight to a PR.

## Pull request checklist

- [ ] `pytest -q` is green locally.
- [ ] New behavior is covered by a test (or has an obvious reason for not being).
- [ ] Public CLI flags / recipes / config keys are documented in `README.md` or
      `recipes.yaml` comments.
- [ ] No new shell interpolation paths were added between LLM output and
      `FFmpegTool`. If unsure, see `tests/test_core.py::test_ai_planner_cannot_inject_ffmpeg`.
- [ ] No secrets, video files, or large cache directories are committed. Verify
      with:
      ```bash
      git ls-files | grep -E '\.env$|\.pem$|\.key$|credential|input/[^/]+\.mp4$' || echo "clean"
      ```

## Style

- Python: standard library + minimal deps. Format with the project's existing
  4-space indentation; no formatter is enforced yet — match surrounding style.
- Comments explain *why*, not *what*. The docstrings at the top of each module
  describe its contract.
- Keep changes minimal and focused. One PR per concern.

## Commit messages

We don't enforce a convention yet. Suggested: short imperative summary
(`fix:` / `feat:` / `docs:` / `chore:`), optional body explaining the
motivation, optional footer for issue references.

## Release process (maintainers)

- Bump `version` in `pyproject.toml`.
- Add a `## [X.Y.Z] - YYYY-MM-DD` entry to `CHANGELOG.md`.
- Tag `vX.Y.Z` and push. GitHub Actions builds and uploads the sdist/wheel.

## License

By contributing, you agree that your contributions will be licensed under the
project's [MIT License](LICENSE).
