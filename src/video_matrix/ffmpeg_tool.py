from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .models import EditPlan
from .utils import require_binary


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

    def render(self, source: Path, plan: EditPlan, output: Path) -> None:
        if not plan.clips:
            raise ValueError("Edit plan has no clips to render")
        ffmpeg = require_binary("ffmpeg")
        audio = has_audio(source)
        output.parent.mkdir(parents=True, exist_ok=True)

        chains: list[str] = []
        concat_inputs: list[str] = []
        for i, clip in enumerate(plan.clips):
            chains.append(
                f"[0:v]trim=start={clip.source_start:.3f}:end={clip.source_end:.3f},"
                f"setpts=PTS-STARTPTS[v{i}]"
            )
            concat_inputs.append(f"[v{i}]")
            if audio:
                chains.append(
                    f"[0:a]atrim=start={clip.source_start:.3f}:end={clip.source_end:.3f},"
                    f"asetpts=PTS-STARTPTS[a{i}]"
                )
                concat_inputs.append(f"[a{i}]")

        if audio:
            chains.append("".join(concat_inputs) + f"concat=n={len(plan.clips)}:v=1:a=1[outv][outa]")
        else:
            chains.append("".join(concat_inputs) + f"concat=n={len(plan.clips)}:v=1:a=0[outv]")

        # Inline filter graph: avoids -filter_complex_script, which is not in
        # every ffmpeg build (e.g. some homebrew 9.x builds).
        graph = ";\n".join(chains)

        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
            "-i", str(source),
            "-filter_complex", graph,
            "-map", "[outv]",
        ]
        if audio:
            cmd += ["-map", "[outa]"]
        cmd += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
        ]
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-movflags", "+faststart", str(output)]
        subprocess.run(cmd, check=True)
