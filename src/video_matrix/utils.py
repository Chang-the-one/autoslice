from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required binary '{name}' was not found in PATH.")
    return path


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json_object(text: str) -> dict[str, Any]:
    # M3 may include <think> blocks or markdown fences even when instructed not to.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"Model response did not contain a JSON object: {text[:400]}")
    return json.loads(text[start : end + 1])


def format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{sec:06.3f}"


_FFMPEG_ENCODERS_CACHE: list[str] | None = None


def _ffmpeg_encoder_names(ffmpeg_path: str | None = None) -> list[str]:
    """Return the encoder names reported by `ffmpeg -encoders`.

    Cached per process so repeated CLI calls do not re-spawn ffmpeg.
    Parses only the second whitespace-delimited column from each
    ` V....D <name> <description>` line so we never depend on FFmpeg's
    column alignment or version-specific layout.
    """
    global _FFMPEG_ENCODERS_CACHE
    if _FFMPEG_ENCODERS_CACHE is not None:
        return _FFMPEG_ENCODERS_CACHE
    bin_path = ffmpeg_path or require_binary("ffmpeg")
    proc = subprocess.run(
        [bin_path, "-hide_banner", "-encoders"],
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    names: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Encoders:"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            names.append(parts[1])
    _FFMPEG_ENCODERS_CACHE = names
    return names


def resolve_video_encoder(requested: str, *, ffmpeg_path: str | None = None) -> str:
    """Resolve a user-requested video encoder to a concrete encoder name.

    Rules:
        ``auto``                 -> ``h264_videotoolbox`` if VideoToolbox H.264 is
                                   available in the installed FFmpeg, otherwise
                                   ``libx264``.
        ``h264_videotoolbox``     -> use it, or raise RuntimeError listing
                                   available H.264 encoders.
        ``hevc_videotoolbox``     -> use it, or raise RuntimeError.
        ``libx264``              -> use it, or raise RuntimeError.
        anything else            -> ValueError so the caller knows it is invalid.

    Never silently falls back from an explicit request.
    """
    if requested not in {"auto", "h264_videotoolbox", "hevc_videotoolbox", "libx264"}:
        raise ValueError(
            f"Unknown encoder {requested!r}. "
            "Expected one of: auto, h264_videotoolbox, hevc_videotoolbox, libx264."
        )

    available = _ffmpeg_encoder_names(ffmpeg_path)

    if requested == "auto":
        if "h264_videotoolbox" in available:
            return "h264_videotoolbox"
        return "libx264"

    if requested in available:
        return requested

    # explicit request that is missing from this FFmpeg build -> fail loudly
    if requested == "libx264":
        raise RuntimeError(
            "Requested encoder 'libx264' is not available in the installed FFmpeg. "
            f"Available H.264/HEVC encoders: {[n for n in available if '264' in n or '265' in n]}"
        )
    if requested in {"h264_videotoolbox", "hevc_videotoolbox"}:
        raise RuntimeError(
            f"Requested encoder '{requested}' is not available in the installed FFmpeg. "
            "VideoToolbox encoders are only present in macOS builds of FFmpeg. "
            f"Available H.264/HEVC encoders: {[n for n in available if '264' in n or '265' in n]}"
        )
    raise RuntimeError(f"Requested encoder '{requested}' is not available in the installed FFmpeg.")

