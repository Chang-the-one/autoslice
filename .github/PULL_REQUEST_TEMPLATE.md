## What

<!-- One short paragraph describing the change. -->

## Why

<!-- Motivation: link the issue, describe the use case, or explain the bug. -->

## How

<!-- Implementation notes worth flagging for the reviewer. -->

## Test plan

<!-- What did you run? Paste the exact commands and their output. -->

- [ ] `pytest -q` is green locally
- [ ] I added/updated tests for the change (or explained why not below)
- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] I confirmed no secrets, videos, or large caches are included (ran `git ls-files | grep -E '\.env$|input/[^/]+\.mp4$'` and it was empty)

### Commands run

```text
# paste exact commands + abbreviated output
```

## Risk / blast radius

<!-- What can break? Cache invalidation, API contract change, CLI behavior change, etc. -->

## Checklist

- [ ] Public CLI flags / recipes / config keys are documented in `README.md` or `recipes.yaml` comments
- [ ] No new path was added where LLM output reaches `FFmpegTool` without `compile_plan()` validation
