from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .models import EditPlan
from .utils import require_binary, resolve_video_encoder


def has_audio(video: Path) -> bool:
    ffprobe = require_binary("ffprobe")
    proc = subprocess.run(
        [
            ffprobe, "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=index", "-of", "json", str(video),
        ],
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return bool(json.loads(proc.stdout).get("streams"))


class FFmpegTool:
    """Deterministic execution tool: edit plan in, MP4 out. No LLM decisions here."""

    def render(
        self,
        source: Path,
        plan: EditPlan,
        output: Path,
        *,
        max_width: int = 0,
        encoder: str = "auto",
    ) -> None:
        if not plan.clips:
            raise ValueError("Edit plan has no clips to render")
        ffmpeg = require_binary("ffmpeg")
        audio = has_audio(source)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Build filter graph: trim per clip, concat, then optional scale.
        chains: list[str] = []
        for i, clip in enumerate(plan.clips):
            chains.append(
                f"[0:v]trim=start={clip.source_start:.3f}:end={clip.source_end:.3f},"
                f"setpts=PTS-STARTPTS[v{i}]"
            )
            if audio:
                chains.append(
                    f"[0:a]atrim=start={clip.source_start:.3f}:end={clip.source_end:.3f},"
                    f"asetpts=PTS-STARTPTS[a{i}]"
                )
        # ffmpeg concat input order is INTERLEAVED per segment: [v0][a0][v1][a1]...[vN][aN]
        labels = "".join(f"[v{i}][a{i}]" for i in range(len(plan.clips))) if audio else                   "".join(f"[v{i}]" for i in range(len(plan.clips)))
        if audio:
            chains.append(f"{labels}concat=n={len(plan.clips)}:v=1:a=1[cv][ca]")
        else:
            chains.append(f"{labels}concat=n={len(plan.clips)}:v=1:a=0[cv]")
        if max_width and max_width > 0:
            chains.append(f"[cv]scale={max_width}:-2,setsar=1[outv]")
        else:
            chains.append("[cv]copy[outv]")

        graph = ";\n".join(chains)

        # Build encoder pipeline. ``auto`` prefers VideoToolbox for speed.
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
            "-hwaccel", "auto",
            "-i", str(source),
            "-filter_complex", graph,
            "-map", "[outv]",
        ]
        if audio:
            cmd += ["-map", "[ca]", "-ac", "2"]

        encoder = resolve_video_encoder(encoder, ffmpeg_path=ffmpeg)
        if encoder == "h264_videotoolbox":
            cmd += ["-c:v", "h264_videotoolbox", "-b:v", "8000k", "-pix_fmt", "yuv420p"]
        elif encoder == "hevc_videotoolbox":
            cmd += ["-c:v", "hevc_videotoolbox", "-b:v", "6000k", "-tag:v", "hvc1", "-pix_fmt", "yuv420p"]
        else:  # libx264 or any other resolved encoder -> software path
            cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-movflags", "+faststart", str(output)]
        subprocess.run(cmd, check=True)
