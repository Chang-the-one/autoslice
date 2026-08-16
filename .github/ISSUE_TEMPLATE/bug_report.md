---
name: Bug report
about: Something in the analyze/render pipeline isn't behaving as documented.
title: "[bug] "
labels: bug
---

## Describe the bug

<!-- One short paragraph. -->

## To reproduce

```bash
# the exact command(s)
video-matrix analyze /path/to/source.mp4 --transcribe
video-matrix render /path/to/source.mp4 cooking_short --planner ai
```

## Expected

<!-- What you expected to happen. -->

## Actual

<!-- What actually happened. Paste the relevant error or output. -->

## Environment

- OS / version: <!-- e.g. macOS 14.4, Ubuntu 22.04 -->
- Python: `python3 --version` → <!-- ... -->
- FFmpeg: `ffmpeg -version | head -n 1` → <!-- ... -->
- `video-matrix doctor` output:
  ```text
  # paste here
  ```
- `video-matrix --version` (or commit SHA if running from source): <!-- ... -->

## Logs / cache

If applicable, attach:

- The relevant `cache/<sha>/scenes.json` (or a redacted excerpt).
- The `cache/<sha>/edit_plan.<recipe>.<planner>.json` if the bug is in rendering.

**Do not paste your API key.**
