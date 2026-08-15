from __future__ import annotations

from pathlib import Path
import yaml

from .ffmpeg_tool import FFmpegTool
from .frames import extract_keyframes
from .minimax_client import MiniMaxClient
from .models import EditPlan, Recipe, SceneAnalysis, SceneSemantic, Segment
from .planner import compile_plan, rules_select
from .scene_detect import detect_segments
from .transcribe import attach_transcript, transcribe
from .utils import read_json, sha256_file, write_json


class Pipeline:
    def __init__(self, cache_root: Path = Path("cache")) -> None:
        self.cache_root = cache_root

    def cache_dir(self, video: Path) -> tuple[str, Path]:
        digest = sha256_file(video)
        return digest, self.cache_root / digest

    def analyze(
        self,
        video: Path,
        *,
        force: bool = False,
        do_transcribe: bool = False,
        whisper_model: str = "small",
        threshold: float = 27.0,
        batch_size: int = 6,
        show_progress: bool = False,
    ) -> Path:
        digest, cache = self.cache_dir(video)
        analysis_path = cache / "scenes.json"
        if analysis_path.exists() and not force:
            return analysis_path

        cache.mkdir(parents=True, exist_ok=True)
        raw_path = cache / "segments.json"
        if raw_path.exists() and not force:
            segments = [Segment.model_validate(x) for x in read_json(raw_path)]
            if do_transcribe and not any(s.speech for s in segments):
                spans = transcribe(video, whisper_model)
                segments = attach_transcript(segments, spans)
                write_json(raw_path, [s.model_dump() for s in segments])
        else:
            segments = detect_segments(
                video, threshold=threshold, show_progress=show_progress,
            )
            if not segments:
                raise RuntimeError(
                    "No segments detected. Try a lower --threshold or check the video."
                )
            if do_transcribe:
                spans = transcribe(video, whisper_model)
                segments = attach_transcript(segments, spans)
            segments = extract_keyframes(video, segments, cache / "frames")
            write_json(raw_path, [s.model_dump() for s in segments])

        client = MiniMaxClient()
        semantics: list[SceneSemantic] = []
        partial_path = cache / "scenes.partial.json"
        done: dict[int, SceneSemantic] = {}
        if partial_path.exists() and not force:
            for row in read_json(partial_path).get("scenes", []):
                scene = SceneSemantic.model_validate(row)
                done[scene.segment_id] = scene

        pending = [s for s in segments if s.segment_id not in done]
        semantics.extend(done.values())
        if pending:
            print(f"Classifying {len(pending)} segments via MiniMax (resumable)...")
        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            result = client.classify_batch(batch)
            semantics.extend(result)
            semantics.sort(key=lambda x: x.segment_id)
            write_json(partial_path, {"scenes": [s.model_dump() for s in semantics]})

        analysis = SceneAnalysis(
            source_video=str(video.resolve()),
            source_hash=digest,
            scenes=sorted(semantics, key=lambda x: x.segment_id),
        )
        write_json(analysis_path, analysis.model_dump())
        return analysis_path

    def load_analysis(self, video: Path) -> tuple[Path, SceneAnalysis]:
        _, cache = self.cache_dir(video)
        path = cache / "scenes.json"
        if not path.exists():
            raise FileNotFoundError(f"No semantic analysis found. Run: video-matrix analyze {video}")
        return path, SceneAnalysis.model_validate(read_json(path))

    @staticmethod
    def load_recipe(recipes_path: Path, recipe_name: str) -> Recipe:
        data = yaml.safe_load(recipes_path.read_text(encoding="utf-8")) or {}
        if recipe_name not in data:
            raise KeyError(f"Recipe '{recipe_name}' not found in {recipes_path}")
        return Recipe.model_validate(data[recipe_name])

    def make_plan(
        self,
        video: Path,
        recipe_name: str,
        recipes_path: Path,
        planner: str,
    ) -> tuple[EditPlan, Path]:
        _, analysis = self.load_analysis(video)
        recipe = self.load_recipe(recipes_path, recipe_name)
        if planner == "ai":
            ids = MiniMaxClient().plan(analysis.scenes, recipe_name, recipe)
        elif planner == "rules":
            ids = rules_select(analysis.scenes, recipe)
        else:
            raise ValueError("planner must be 'ai' or 'rules'")

        plan = compile_plan(
            analysis.scenes, recipe_name, recipe, ids,
            planner=planner,
        )
        _, cache = self.cache_dir(video)
        plan_path = cache / f"edit_plan.{recipe_name}.{planner}.json"
        write_json(plan_path, plan.model_dump())
        return plan, plan_path

    def render(self, video: Path, plan: EditPlan, output: Path) -> None:
        FFmpegTool().render(video, plan, output)
