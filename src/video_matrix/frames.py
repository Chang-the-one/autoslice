from __future__ import annotations

import subprocess
from pathlib import Path
from PIL import Image

from .models import Segment
from .utils import require_binary


def _extract_frame(video: Path, timestamp: float, out_path: Path, max_side: int = 960) -> None:
    ffmpeg = require_binary("ffmpeg")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{timestamp:.3f}", "-i", str(video),
            "-frames:v", "1", "-q:v", "3", str(out_path),
        ],
        check=True,
    )
    with Image.open(out_path) as img:
        img.thumbnail((max_side, max_side * 2), Image.Resampling.LANCZOS)
        img.convert("RGB").save(out_path, format="JPEG", quality=84, optimize=True)


def extract_keyframes(video: Path, segments: list[Segment], frames_dir: Path) -> list[Segment]:
    for seg in segments:
        duration = seg.duration
        positions = [seg.start + duration * 0.35, seg.start + duration * 0.70]
        paths: list[str] = []
        for idx, ts in enumerate(positions, start=1):
            out = frames_dir / f"seg_{seg.segment_id:04d}_{idx}.jpg"
            if not out.exists():
                _extract_frame(video, ts, out)
            paths.append(str(out))
        seg.frame_paths = paths
    return segments
