# Security Policy

## Supported versions

`video-matrix-cutter` is a personal/local-first tool currently shipping version
`0.1.0`. Security fixes will be backported to the latest release only. There is
no LTS branch.

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a vulnerability

**Please do not file a public GitHub issue for security problems.**

The LLM planner in this project is treated as untrusted input — see the
"Safety boundary" section of [README.md](README.md) for the trust model — so
prompt-injection-style issues against the planner are *not* security
vulnerabilities of the tool itself (the model output cannot reach `FFmpegTool`
without passing through `compile_plan()` validation). What *is* in scope:

- Anything that lets untrusted input reach `FFmpegTool` without validation.
- Anything that lets a malicious `cache/<sha>/scenes.json` (written by a
  non-owner) influence subsequent renders.
- Anything that leaks `MINIMAX_API_KEY` to logs, error messages, or the
  filesystem outside `.env`.
- Local privilege escalation via crafted input filenames passed through
  PySceneDetect or FFmpeg (e.g. option injection).

To report privately, use **GitHub private vulnerability reporting**:

1. Go to <https://github.com/Chang-the-one/autoslice/security/advisories/new>
2. Fill in the affected version, summary, and reproduction steps.
3. Submit. Maintainers are notified by email.

If GitHub private reporting is unavailable, open a regular issue titled
`security: triage request` with **no details** — a maintainer will reply
privately to coordinate disclosure.

Please include:

- The affected commit SHA or release tag.
- A minimal reproduction (command + sanitized input filename).
- The observed vs expected behavior.

## Disclosure timeline

- **Acknowledge** within 7 days.
- **Patch or documented mitigation** within 30 days for high-severity issues,
  longer for complex ones — we will keep you posted.
- **Coordinated disclosure**: we prefer to publish a fix and CVE together. If
  you need to disclose earlier, please coordinate first.

## Scope notes

- The vision LLM endpoint (`MINIMAX_BASE_URL` / `MINIMAX_MODEL`) is a
  third-party service. Issues with that endpoint itself should be reported to
  its provider, not to this project.
- `faster-whisper` and `PySceneDetect` are upstream dependencies. Report their
  issues upstream.
