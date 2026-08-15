from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .pipeline import Pipeline
from .utils import format_time, require_binary


def _video(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise argparse.ArgumentTypeError(f"Video not found: {path}")
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="video-matrix", description="Semantic video matrix rough-cutter")
    p.add_argument("--cache", type=Path, default=Path("cache"), help="Cache root (default: ./cache)")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Build cached semantic scene map")
    a.add_argument("video", type=_video)
    a.add_argument("--force", action="store_true")
    a.add_argument("--transcribe", action="store_true", help="Optional local Whisper transcription")
    a.add_argument("--whisper-model", default="small")
    a.add_argument("--threshold", type=float, default=27.0)
    a.add_argument("--batch-size", type=int, default=6)
    a.add_argument("--quiet", action="store_true", help="Suppress progress bars")

    r = sub.add_parser("render", help="Plan and render a recipe")
    r.add_argument("video", type=_video)
    r.add_argument("recipe")
    r.add_argument("--recipes", type=Path, default=Path("recipes.yaml"))
    r.add_argument("--planner", choices=["ai", "rules"], default="ai")
    r.add_argument("--output", type=Path)
    r.add_argument("--plan-only", action="store_true")

    i = sub.add_parser("inspect", help="Print cached semantic scene map")
    i.add_argument("video", type=_video)

    sub.add_parser("doctor", help="Check local runtime dependencies")
    return p


def main() -> None:
    args = build_parser().parse_args()
    pipe = Pipeline(args.cache)

    if args.command == "doctor":
        print(f"ffmpeg:  {shutil.which('ffmpeg') or 'MISSING'}")
        print(f"ffprobe: {shutil.which('ffprobe') or 'MISSING'}")
        try:
            require_binary("ffmpeg")
            require_binary("ffprobe")
            print("local video toolchain: OK")
        except RuntimeError as exc:
            print(exc)
            sys.exit(2)
        return

    if args.command == "analyze":
        path = pipe.analyze(
            args.video,
            force=args.force,
            do_transcribe=args.transcribe,
            whisper_model=args.whisper_model,
            threshold=args.threshold,
            batch_size=args.batch_size,
            show_progress=not args.quiet,
        )
        print(f"semantic scene map: {path}")
        return

    if args.command == "inspect":
        path, analysis = pipe.load_analysis(args.video)
        print(f"scene map: {path}\n")
        for s in analysis.scenes:
            labels = ", ".join(s.labels[:6])
            speech = f" | speech: {s.speech[:70]}" if s.speech else ""
            print(
                f"#{s.segment_id:03d} {format_time(s.start)}-{format_time(s.end)} "
                f"{s.primary_category:<8} keep={s.keep_score:.2f} quality={s.visual_quality:.2f} "
                f"| {s.description} | {labels}{speech}"
            )
        return

    if args.command == "render":
        plan, plan_path = pipe.make_plan(args.video, args.recipe, args.recipes, args.planner)
        print(f"edit plan: {plan_path}")
        print(f"clips: {len(plan.clips)} | duration: {plan.estimated_duration:.1f}s")
        for clip in plan.clips:
            print(f"  #{clip.segment_id:03d} {format_time(clip.source_start)}-{format_time(clip.source_end)} | {clip.reason}")
        if args.plan_only:
            return
        output = args.output or Path("output") / f"{args.video.stem}.{args.recipe}.mp4"
        pipe.render(args.video, plan, output)
        print(f"rendered: {output}")
        return


if __name__ == "__main__":
    main()
